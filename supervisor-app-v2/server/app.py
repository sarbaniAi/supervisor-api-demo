"""FastAPI backend for Supervisor API Demo - Using REAL Supervisor API (responses.create)."""

import json
import os
import logging
from pathlib import Path
from typing import Optional

import httpx
from databricks.sdk import WorkspaceClient
from databricks_openai import DatabricksOpenAI
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Supervisor API Demo")

# ─── Config ────────────────────────────────────────────────────────────────────
w = WorkspaceClient()
HOST = w.config.host
LLM_MODEL = os.getenv("LLM_MODEL", "databricks-claude-sonnet-4-6")
UC_CATALOG = os.getenv("UC_CATALOG", "classic_stable_yh3b2z_catalog")
UC_SCHEMA = os.getenv("UC_SCHEMA", "supertvisor-api")
SQL_WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID", "25899ae5a5341c16")
WORKSPACE_URL = os.getenv("WORKSPACE_URL", HOST)
MCP_APP_URL = os.getenv("MCP_APP_URL", "https://mcp-ops-tools-7474660536314099.aws.databricksapps.com")
AGENT_APP_URL = os.getenv("AGENT_APP_URL", "https://agent-data-analyst-7474660536314099.aws.databricksapps.com")

# ─── Supervisor API Client ─────────────────────────────────────────────────────
supervisor_client = DatabricksOpenAI(use_ai_gateway=True)

# ─── Supervisor API Tool Definitions (exact format from docs) ──────────────────
SUPERVISOR_TOOLS = [
    # Custom MCP Server hosted on Databricks App
    {
        "type": "app",
        "app": {
            "name": "mcp-ops-tools",
            "description": "Custom MCP server with operations tools: get system metrics for any service, search the operations knowledge base for runbooks and troubleshooting guides, create incident tickets, and list all monitored services."
        }
    },
    # Custom Agent hosted on Databricks App
    {
        "type": "app",
        "app": {
            "name": "agent-data-analyst",
            "description": "A specialized data analyst agent that analyzes operational data including incident trends, service reliability metrics, SLA compliance, and cost analysis. Ask it questions about trends, patterns, reliability, uptime, costs, or general operational summaries."
        }
    },
    # UC Functions
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{UC_CATALOG}.{UC_SCHEMA}.classify_priority",
            "description": "Classifies incident priority (P1-P4) based on error rate percentage, P99 latency in milliseconds, and number of affected users."
        }
    },
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{UC_CATALOG}.{UC_SCHEMA}.calculate_sla_budget",
            "description": "Calculates remaining SLA error budget given current uptime, SLA target, period length, and days elapsed. Returns budget status and risk level."
        }
    },
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{UC_CATALOG}.{UC_SCHEMA}.format_incident_summary",
            "description": "Formats a professional incident summary report for stakeholder communication given service name, severity, error rate, latency, and description."
        }
    },
]

SUPERVISOR_INSTRUCTIONS = """You are an intelligent operations supervisor agent. You orchestrate multiple specialized tools:

**Custom MCP Server on Databricks Apps** (mcp-ops-tools):
- get_system_metrics: Real-time service metrics (CPU, memory, latency, error rate)
- search_knowledge_base: Operations runbooks and troubleshooting guides
- create_incident_ticket: Create and track incident tickets
- list_services: List all monitored services with status

**Custom Agent on Databricks Apps** (agent-data-analyst):
- Operational analytics: incident trends, service reliability, SLA compliance, cost analysis

**Unity Catalog Functions**:
- classify_priority: Classify incident severity (P1-P4) from metrics
- calculate_sla_budget: Calculate remaining SLA error budget
- format_incident_summary: Generate formatted stakeholder reports

When investigating issues:
1. Gather metrics with MCP tools
2. Analyze trends with the data analyst agent
3. Classify priority via UC function
4. Create tickets and generate reports as needed

Be thorough and show your reasoning. Format responses with clear markdown sections."""


# ─── Helper for auth (used by test-tool endpoint for direct tool testing) ──────
def get_auth():
    header = w.config._header_factory()
    if isinstance(header, dict):
        return header.get("Authorization", "")
    return f"Bearer {header}"


# ─── Direct tool execution (for interactive test panels only) ──────────────────
def execute_tool_direct(tool_type: str, tool_name: str, arguments: dict) -> str:
    """Direct tool execution for the interactive test panels (bypasses Supervisor API)."""
    auth = get_auth()
    try:
        if tool_type == "mcp":
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.post(f"{MCP_APP_URL}/api/tool", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"tool": tool_name, "arguments": arguments})
                if resp.status_code != 200:
                    return f"MCP Error HTTP {resp.status_code}: {resp.text[:300]}"
                return resp.json().get("result", json.dumps(resp.json()))

        elif tool_type == "agent":
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{AGENT_APP_URL}/chat", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"messages": [{"role": "user", "content": arguments.get("question", "")}]})
                if resp.status_code != 200:
                    return f"Agent Error HTTP {resp.status_code}: {resp.text[:300]}"
                choices = resp.json().get("choices", [])
                return choices[0]["message"]["content"] if choices else json.dumps(resp.json())

        elif tool_type == "uc":
            func = tool_name
            if func == "classify_priority":
                sql = f"SELECT {UC_CATALOG}.{UC_SCHEMA}.classify_priority({arguments['error_rate']}, {arguments['p99_latency_ms']}, {arguments['affected_users']})"
            elif func == "calculate_sla_budget":
                sql = f"SELECT {UC_CATALOG}.{UC_SCHEMA}.calculate_sla_budget({arguments['uptime_percent']}, {arguments['sla_target']}, {arguments['days_in_period']}, {arguments['days_elapsed']})"
            elif func == "format_incident_summary":
                svc = arguments['service_name'].replace("'", "''")
                sev = arguments['severity'].replace("'", "''")
                desc = arguments['description'].replace("'", "''")
                sql = f"SELECT {UC_CATALOG}.{UC_SCHEMA}.format_incident_summary('{svc}', '{sev}', {arguments['error_rate']}, {arguments['latency_ms']}, '{desc}')"
            else:
                return f"Unknown UC function: {func}"

            with httpx.Client(timeout=60) as client:
                resp = client.post(f"{HOST}/api/2.0/sql/statements", headers={"Authorization": auth, "Content-Type": "application/json"}, json={"statement": sql, "warehouse_id": SQL_WAREHOUSE_ID, "wait_timeout": "50s"})
                data = resp.json().get("result", {}).get("data_array", [])
                if data:
                    return data[0][0]
                return f"SQL Error: {resp.json().get('status', {}).get('error', {}).get('message', 'Unknown')}"
        else:
            return f"Unknown tool type: {tool_type}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


# ─── API Routes ────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    scenario: Optional[str] = None


class ToolTestRequest(BaseModel):
    tool_type: str
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
    """Test individual tool directly - for the interactive demo sections."""
    result = execute_tool_direct(req.tool_type, req.tool_name, req.arguments)
    return {"tool": f"{req.tool_type}__{req.tool_name}", "result": result}


def parse_response_output(response):
    """Parse Supervisor API response output items."""
    response_text = ""
    tool_calls_log = []
    mcp_approvals = []

    output = getattr(response, 'output', []) or []
    for item in output:
        item_type = getattr(item, 'type', None)

        if item_type == 'message':
            for c in getattr(item, 'content', []):
                if getattr(c, 'type', None) == 'output_text':
                    response_text += getattr(c, 'text', '')
                elif hasattr(c, 'text'):
                    response_text += c.text

        elif item_type == 'function_call':
            name = getattr(item, 'name', 'unknown')
            args_str = getattr(item, 'arguments', '{}')
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except Exception:
                args = {"raw": str(args_str)}

            if name in ['get_system_metrics', 'search_knowledge_base', 'create_incident_ticket', 'list_services']:
                tool_type, icon = "Custom MCP Server (App)", "wrench"
            elif 'analyst' in name.lower() or 'agent' in name.lower():
                tool_type, icon = "Custom Agent (App)", "robot"
            elif any(k in name.lower() for k in ['classify', 'sla', 'format', 'budget', 'priority', 'incident']):
                tool_type, icon = "UC Function", "database"
            else:
                tool_type, icon = "Tool", "wrench"

            tool_calls_log.append({"name": name, "type": tool_type, "icon": icon, "args": args, "result": ""})

        elif item_type == 'function_call_output':
            output_val = getattr(item, 'output', '')
            if tool_calls_log:
                tool_calls_log[-1]["result"] = str(output_val)[:500]

        elif item_type == 'mcp_approval_request':
            # Auto-approve MCP tool calls
            mcp_approvals.append({
                "type": "mcp_approval_response",
                "approve": True,
                "approval_request_id": getattr(item, 'id', ''),
            })
            # Log it as a tool call
            name = getattr(item, 'name', 'unknown')
            args_str = getattr(item, 'arguments', '{}')
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except Exception:
                args = {}
            tool_calls_log.append({
                "name": name,
                "type": "Custom MCP Server (App)",
                "icon": "wrench",
                "args": args,
                "result": "(awaiting approval...)"
            })

        elif item_type == 'mcp_list_tools':
            pass  # Tool discovery - no action needed

    if not response_text and hasattr(response, 'output_text'):
        response_text = response.output_text or ""

    return response_text, tool_calls_log, mcp_approvals


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Run the Supervisor API with MCP approval loop."""
    all_tool_calls = []

    try:
        # Initial Supervisor API call
        input_items = [{"type": "message", "role": "user", "content": req.message}]

        max_rounds = 5
        for round_num in range(max_rounds):
            response = supervisor_client.responses.create(
                model=LLM_MODEL,
                input=input_items,
                tools=SUPERVISOR_TOOLS,
                instructions=SUPERVISOR_INSTRUCTIONS,
                stream=False,
                extra_body={
                    "trace_destination": {
                        "catalog_name": UC_CATALOG,
                        "schema_name": UC_SCHEMA,
                        "table_prefix": "supervisor_traces"
                    }
                }
            )

            response_text, tool_calls, mcp_approvals = parse_response_output(response)
            all_tool_calls.extend(tool_calls)

            if not mcp_approvals:
                # No pending approvals - we're done
                return {"response": response_text, "tool_calls": all_tool_calls}

            # Auto-approve MCP calls and continue
            logger.info(f"Round {round_num+1}: Auto-approving {len(mcp_approvals)} MCP tool calls")
            input_items = []
            for item in getattr(response, 'output', []):
                input_items.append(item)
            for approval in mcp_approvals:
                input_items.append(approval)

        return {"response": response_text or "Max approval rounds reached.", "tool_calls": all_tool_calls}

    except Exception as e:
        logger.error(f"Supervisor API error: {e}", exc_info=True)
        return {
            "response": f"Supervisor API Error: {type(e).__name__}: {str(e)}",
            "tool_calls": all_tool_calls
        }


@app.get("/api/health")
async def health():
    return {"status": "healthy", "model": LLM_MODEL, "tools": len(SUPERVISOR_TOOLS), "api": "Supervisor API (responses.create)"}


# ─── Serve Frontend ───────────────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    html_path = Path(__file__).parent.parent / "client" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Supervisor API Demo</h1><p>Frontend not found</p>")
