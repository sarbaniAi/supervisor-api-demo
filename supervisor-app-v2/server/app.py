"""FastAPI backend for Supervisor API Demo."""

import json
import os
import logging
from pathlib import Path
from typing import Optional

import httpx
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Supervisor API Demo")

# ─── Config ────────────────────────────────────────────────────────────────────
w = WorkspaceClient()
HOST = w.config.host
MCP_APP_URL = os.getenv("MCP_APP_URL", "https://mcp-ops-tools-7474660536314099.aws.databricksapps.com")
AGENT_APP_URL = os.getenv("AGENT_APP_URL", "https://agent-data-analyst-7474660536314099.aws.databricksapps.com")
LLM_MODEL = os.getenv("LLM_MODEL", "databricks-claude-sonnet-4-6")
UC_CATALOG = os.getenv("UC_CATALOG", "classic_stable_yh3b2z_catalog")
UC_SCHEMA = os.getenv("UC_SCHEMA", "supertvisor-api")
SQL_WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID", "25899ae5a5341c16")
WORKSPACE_URL = os.getenv("WORKSPACE_URL", HOST)


def get_auth():
    header = w.config._header_factory()
    if isinstance(header, dict):
        return header.get("Authorization", "")
    return f"Bearer {header}"


def get_token():
    auth = get_auth()
    return auth.replace("Bearer ", "") if "Bearer" in auth else auth


def get_llm_client():
    return OpenAI(base_url=f"{HOST}/serving-endpoints", api_key=get_token())


# ─── Tool Definitions ─────────────────────────────────────────────────────────
TOOLS = [
    {"type": "function", "function": {"name": "mcp__get_system_metrics", "description": "Get real-time system metrics for a service. Powered by Custom MCP Server on Databricks Apps.", "parameters": {"type": "object", "properties": {"service_name": {"type": "string", "description": "Service name"}}, "required": ["service_name"]}}},
    {"type": "function", "function": {"name": "mcp__search_knowledge_base", "description": "Search ops knowledge base for runbooks. Powered by Custom MCP Server on Databricks Apps.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "mcp__create_incident_ticket", "description": "Create incident ticket. Powered by Custom MCP Server on Databricks Apps.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]}, "affected_service": {"type": "string"}}, "required": ["title", "description", "severity", "affected_service"]}}},
    {"type": "function", "function": {"name": "mcp__list_services", "description": "List all monitored services. Powered by Custom MCP Server on Databricks Apps.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "agent__data_analyst", "description": "Delegate analytics to Data Analyst Agent on Databricks Apps. Trends, reliability, costs, SLA.", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {"name": "uc__classify_priority", "description": "Classify incident priority (P1-P4). Unity Catalog SQL function.", "parameters": {"type": "object", "properties": {"error_rate": {"type": "number"}, "p99_latency_ms": {"type": "number"}, "affected_users": {"type": "integer"}}, "required": ["error_rate", "p99_latency_ms", "affected_users"]}}},
    {"type": "function", "function": {"name": "uc__calculate_sla_budget", "description": "Calculate SLA error budget. Unity Catalog SQL function.", "parameters": {"type": "object", "properties": {"uptime_percent": {"type": "number"}, "sla_target": {"type": "number"}, "days_in_period": {"type": "integer"}, "days_elapsed": {"type": "integer"}}, "required": ["uptime_percent", "sla_target", "days_in_period", "days_elapsed"]}}},
    {"type": "function", "function": {"name": "uc__format_incident_summary", "description": "Format incident report for stakeholders. Unity Catalog SQL function.", "parameters": {"type": "object", "properties": {"service_name": {"type": "string"}, "severity": {"type": "string"}, "error_rate": {"type": "number"}, "latency_ms": {"type": "number"}, "description": {"type": "string"}}, "required": ["service_name", "severity", "error_rate", "latency_ms", "description"]}}},
]

SYSTEM_PROMPT = """You are an intelligent operations supervisor agent. You orchestrate multiple specialized tools:

**Custom MCP Server on Databricks Apps** (mcp-ops-tools):
- mcp__get_system_metrics: Real-time service metrics
- mcp__search_knowledge_base: Operations runbooks and guides
- mcp__create_incident_ticket: Create incident tickets
- mcp__list_services: List all services

**Custom Agent on Databricks Apps** (agent-data-analyst):
- agent__data_analyst: Operational analytics (trends, reliability, costs)

**Unity Catalog Functions**:
- uc__classify_priority: Classify incident severity
- uc__calculate_sla_budget: Calculate SLA error budget
- uc__format_incident_summary: Generate stakeholder reports

Be thorough and show your reasoning. Format responses with clear markdown sections."""


# ─── Tool Execution ───────────────────────────────────────────────────────────
def execute_tool(tool_name: str, arguments: dict) -> str:
    auth = get_auth()
    try:
        if tool_name.startswith("mcp__"):
            mcp_tool = tool_name[5:]
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.post(f"{MCP_APP_URL}/api/tool", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"tool": mcp_tool, "arguments": arguments})
                if resp.status_code != 200:
                    return f"MCP Error HTTP {resp.status_code}: {resp.text[:300]}"
                return resp.json().get("result", json.dumps(resp.json()))

        elif tool_name.startswith("agent__"):
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{AGENT_APP_URL}/chat", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"messages": [{"role": "user", "content": arguments.get("question", "")}]})
                if resp.status_code != 200:
                    return f"Agent Error HTTP {resp.status_code}: {resp.text[:300]}"
                choices = resp.json().get("choices", [])
                return choices[0]["message"]["content"] if choices else json.dumps(resp.json())

        elif tool_name.startswith("uc__"):
            func = tool_name[4:]
            if func == "classify_priority":
                sql = f"SELECT `{UC_CATALOG}`.`{UC_SCHEMA}`.classify_priority({arguments['error_rate']}, {arguments['p99_latency_ms']}, {arguments['affected_users']})"
            elif func == "calculate_sla_budget":
                sql = f"SELECT `{UC_CATALOG}`.`{UC_SCHEMA}`.calculate_sla_budget({arguments['uptime_percent']}, {arguments['sla_target']}, {arguments['days_in_period']}, {arguments['days_elapsed']})"
            elif func == "format_incident_summary":
                svc = arguments['service_name'].replace("'", "''")
                sev = arguments['severity'].replace("'", "''")
                desc = arguments['description'].replace("'", "''")
                sql = f"SELECT `{UC_CATALOG}`.`{UC_SCHEMA}`.format_incident_summary('{svc}', '{sev}', {arguments['error_rate']}, {arguments['latency_ms']}, '{desc}')"
            else:
                return f"Unknown UC function: {func}"

            with httpx.Client(timeout=60) as client:
                resp = client.post(f"{HOST}/api/2.0/sql/statements", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"statement": sql, "warehouse_id": SQL_WAREHOUSE_ID, "wait_timeout": "50s"})
                data = resp.json().get("result", {}).get("data_array", [])
                if data:
                    return data[0][0]
                return f"SQL Error: {resp.json().get('status', {}).get('error', {}).get('message', 'Unknown')}"
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


# ─── API Routes ────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    scenario: Optional[str] = None


class ToolTestRequest(BaseModel):
    tool_type: str  # "mcp", "agent", "uc"
    tool_name: str
    arguments: dict


@app.get("/api/config")
async def get_config():
    return {
        "workspace_url": WORKSPACE_URL,
        "mcp_app_url": MCP_APP_URL,
        "agent_app_url": AGENT_APP_URL,
        "model": LLM_MODEL,
        "catalog": UC_CATALOG,
        "schema": UC_SCHEMA,
        "notebook_setup": os.getenv("NOTEBOOK_SETUP_URL", ""),
        "notebook_demo": os.getenv("NOTEBOOK_DEMO_URL", ""),
    }


@app.post("/api/test-tool")
async def test_tool(req: ToolTestRequest):
    """Test individual tool - for the interactive demo sections."""
    full_name = f"{req.tool_type}__{req.tool_name}" if not req.tool_name.startswith(f"{req.tool_type}__") else req.tool_name
    result = execute_tool(full_name, req.arguments)
    return {"tool": full_name, "result": result}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Run the supervisor agent loop."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message},
    ]
    tool_calls_log = []
    max_iter = 10

    for _ in range(max_iter):
        client = get_llm_client()
        response = client.chat.completions.create(model=LLM_MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
        choice = response.choices[0]

        if choice.message.tool_calls:
            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if tc.function.name.startswith("mcp__"):
                    tool_type, icon = "Custom MCP Server (App)", "wrench"
                elif tc.function.name.startswith("agent__"):
                    tool_type, icon = "Custom Agent (App)", "robot"
                elif tc.function.name.startswith("uc__"):
                    tool_type, icon = "UC Function", "database"
                else:
                    tool_type, icon = "Unknown", "help-circle"

                result = execute_tool(tc.function.name, args)
                tool_calls_log.append({"name": tc.function.name, "type": tool_type, "icon": icon, "args": args, "result": result[:500]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            return {"response": choice.message.content or "", "tool_calls": tool_calls_log}

    return {"response": "Max iterations reached.", "tool_calls": tool_calls_log}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "model": LLM_MODEL, "tools": len(TOOLS)}


# ─── Serve Frontend ───────────────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    html_path = Path(__file__).parent.parent / "client" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Supervisor API Demo</h1><p>Frontend not found</p>")
