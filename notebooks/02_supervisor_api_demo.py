# Databricks notebook source
# MAGIC %md
# MAGIC # Supervisor API Demo: New Tool Types
# MAGIC
# MAGIC This notebook demonstrates the **Supervisor API** with the newly supported tool types:
# MAGIC
# MAGIC | Tool Type | What It Does | How We Use It |
# MAGIC |-----------|-------------|---------------|
# MAGIC | **`app` (Custom MCP Server)** | Custom MCP server hosted on Databricks Apps | `mcp-ops-tools` - system metrics, knowledge base, incident tickets |
# MAGIC | **`app` (Custom Agent)** | Custom agent hosted on Databricks Apps | `agent-data-analyst` - operational data analysis |
# MAGIC | **`uc_function`** | Unity Catalog functions as tools | `classify_priority`, `calculate_sla_budget`, `format_incident_summary` |
# MAGIC
# MAGIC ### Architecture
# MAGIC ```
# MAGIC                    ┌─────────────────────────┐
# MAGIC                    │    Supervisor API        │
# MAGIC                    │  (Orchestration Layer)   │
# MAGIC                    └──────────┬──────────────┘
# MAGIC                               │
# MAGIC          ┌────────────────────┼────────────────────┐
# MAGIC          │                    │                    │
# MAGIC   ┌──────▼──────┐    ┌───────▼───────┐   ┌───────▼────────┐
# MAGIC   │ MCP Server  │    │ Custom Agent   │   │  UC Functions  │
# MAGIC   │ (App Tool)  │    │  (App Tool)    │   │  (UC Tool)     │
# MAGIC   │             │    │                │   │                │
# MAGIC   │• Metrics    │    │• Trend Analysis│   │• Priority      │
# MAGIC   │• KB Search  │    │• Reliability   │   │• SLA Budget    │
# MAGIC   │• Incidents  │    │• Cost Analysis │   │• Incident Fmt  │
# MAGIC   └─────────────┘    └────────────────┘   └────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %pip install databricks-openai --upgrade -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize the Supervisor API Client

# COMMAND ----------

from databricks_openai import DatabricksOpenAI

client = DatabricksOpenAI(use_ai_gateway=True)

# Model to use for the supervisor
MODEL = "databricks-claude-sonnet-4-6"

# Catalog and schema for UC functions and tracing
CATALOG = "classic_stable_yh3b2z_catalog"
SCHEMA = "supertvisor-api"

print(f"Supervisor API client initialized")
print(f"Model: {MODEL}")
print(f"Catalog/Schema: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define All Tools
# MAGIC
# MAGIC We register three types of tools:
# MAGIC 1. **Custom MCP Server on App** (`mcp-ops-tools`)
# MAGIC 2. **Custom Agent on App** (`agent-data-analyst`)
# MAGIC 3. **UC Functions** (`classify_priority`, `calculate_sla_budget`, `format_incident_summary`)

# COMMAND ----------

# ─── Tool Definitions ─────────────────────────────────────────────────────────

tools = [
    # ── Tool Type 1: Custom MCP Server hosted on Databricks Apps ──
    {
        "type": "app",
        "app": {
            "name": "mcp-ops-tools",
            "description": "Custom MCP server with operations tools: get system metrics for any service, search the operations knowledge base for runbooks and troubleshooting guides, create incident tickets, and list all monitored services."
        }
    },

    # ── Tool Type 2: Custom Agent hosted on Databricks Apps ──
    {
        "type": "app",
        "app": {
            "name": "agent-data-analyst",
            "description": "A specialized data analyst agent that analyzes operational data including incident trends, service reliability metrics, SLA compliance, and cost analysis. Ask it questions about trends, patterns, reliability, uptime, costs, or general operational summaries."
        }
    },

    # ── Tool Type 3: UC Functions ──
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{CATALOG}.`{SCHEMA}`.classify_priority",
            "description": "Classifies incident priority (P1-P4) based on error rate percentage, P99 latency in milliseconds, and number of affected users."
        }
    },
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{CATALOG}.`{SCHEMA}`.calculate_sla_budget",
            "description": "Calculates remaining SLA error budget given current uptime, SLA target, period length, and days elapsed. Returns budget status and risk level."
        }
    },
    {
        "type": "uc_function",
        "uc_function": {
            "name": f"{CATALOG}.`{SCHEMA}`.format_incident_summary",
            "description": "Formats a professional incident summary report for stakeholder communication given service name, severity, error rate, latency, and description."
        }
    },
]

print(f"Registered {len(tools)} tools:")
for t in tools:
    tool_type = t["type"]
    if tool_type == "app":
        print(f"  [{tool_type}] {t['app']['name']}")
    elif tool_type == "uc_function":
        print(f"  [{tool_type}] {t['uc_function']['name']}")
    elif tool_type == "uc_connection":
        print(f"  [{tool_type}] {t['uc_connection']['name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper: Run Supervisor with Streaming

# COMMAND ----------

def run_supervisor(user_message: str, instructions: str = None, stream: bool = True):
    """Run the Supervisor API with all tools and print the response."""
    print(f"\n{'='*80}")
    print(f"USER: {user_message}")
    print(f"{'='*80}\n")

    default_instructions = """You are an intelligent operations supervisor agent. You have access to multiple tools:

1. **MCP Operations Tools** (mcp-ops-tools app): Use this for real-time system metrics, searching the knowledge base for runbooks, creating incident tickets, and listing services.
2. **Data Analyst Agent** (agent-data-analyst app): Use this for analytical questions about trends, reliability, SLA compliance, and cost analysis.
3. **UC Functions**: Use classify_priority to determine incident severity, calculate_sla_budget for SLA analysis, and format_incident_summary for stakeholder reports.

When investigating an issue:
- First gather metrics from the MCP tools
- Use the data analyst for trend analysis
- Classify priority using the UC function
- Create incident tickets if needed
- Format summaries for stakeholders

Be thorough but concise. Show your reasoning."""

    params = {
        "model": MODEL,
        "input": [{"type": "message", "role": "user", "content": user_message}],
        "tools": tools,
        "instructions": instructions or default_instructions,
        "stream": stream,
        "extra_body": {
            "trace_destination": {
                "catalog_name": CATALOG,
                "schema_name": SCHEMA,
                "table_prefix": "supervisor_traces"
            }
        }
    }

    if stream:
        full_text = ""
        with client.responses.create(**params) as response_stream:
            for event in response_stream:
                if hasattr(event, 'type'):
                    if event.type == 'response.output_text.delta':
                        print(event.delta, end="", flush=True)
                        full_text += event.delta
                    elif event.type == 'response.function_call_arguments.delta':
                        pass  # Tool call in progress
                    elif event.type == 'response.output_item.added':
                        if hasattr(event, 'item') and hasattr(event.item, 'type'):
                            if event.item.type == 'function_call':
                                print(f"\n  [Calling tool: {event.item.name}]", flush=True)
        print(f"\n\n{'='*80}")
        return full_text
    else:
        response = client.responses.create(**params)
        print(response.output_text)
        print(f"\n{'='*80}")
        return response.output_text

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 1: Basic Health Check
# MAGIC
# MAGIC The supervisor checks system health using the **Custom MCP Server** tools.

# COMMAND ----------

result = run_supervisor(
    "What's the current status of our payment-gateway service? Check its metrics and let me know if there are any issues."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 2: Multi-Tool Investigation
# MAGIC
# MAGIC The supervisor uses **MCP tools + UC functions** together to investigate an issue and classify its priority.

# COMMAND ----------

result = run_supervisor(
    """The order-service seems slow. Can you:
1. Get its current metrics
2. Classify the priority based on the metrics
3. Search the knowledge base for relevant troubleshooting steps
4. If it's P1 or P2, create an incident ticket"""
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 3: Data Analysis with Custom Agent
# MAGIC
# MAGIC The supervisor delegates analytical work to the **Custom Agent on Apps**.

# COMMAND ----------

result = run_supervisor(
    "I need a comprehensive operational review. Can you analyze incident trends for the past week and check our service reliability metrics? Also calculate the SLA budget for a service with 99.85% uptime against a 99.9% SLA target over 30 days (15 days elapsed)."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 4: Full Incident Response Workflow
# MAGIC
# MAGIC This demonstrates the complete workflow using **ALL tool types** together.

# COMMAND ----------

result = run_supervisor(
    """URGENT: We're getting reports of customer checkout failures.

Please execute our incident response procedure:
1. List all services and identify which ones are having problems
2. Get detailed metrics for any degraded/critical services
3. Classify the incident priority based on the metrics
4. Search the knowledge base for relevant runbooks
5. Ask the data analyst for trend analysis to see if this is a new issue or recurring
6. Create an incident ticket for the affected service
7. Generate a formatted incident summary for the stakeholder update"""
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 5: Background Mode (Async Execution)
# MAGIC
# MAGIC Run a complex analysis in the background and poll for results.

# COMMAND ----------

# Submit a background task
response = client.responses.create(
    model=MODEL,
    input=[{"type": "message", "role": "user", "content": "Run a complete health check on all services, analyze reliability trends, and calculate SLA budgets for any service below 99.9% uptime. Provide a comprehensive report."}],
    tools=tools,
    instructions="You are an operations supervisor. Be thorough in your analysis.",
    background=True,
    extra_body={
        "trace_destination": {
            "catalog_name": CATALOG,
            "schema_name": SCHEMA,
            "table_prefix": "supervisor_traces"
        }
    }
)

print(f"Background task submitted: {response.id}")
print(f"Status: {response.status}")

# COMMAND ----------

# Poll for completion
from time import sleep

status = response.status
while status in ("queued", "in_progress"):
    sleep(3)
    response = client.responses.retrieve(response.id)
    status = response.status
    print(f"Status: {status}...")

print(f"\nFinal Status: {status}")
print(f"\n{'='*80}")
print(response.output_text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 6: Non-Streaming Mode
# MAGIC
# MAGIC Simple synchronous call without streaming.

# COMMAND ----------

result = run_supervisor(
    "Give me a quick summary: what's the priority classification for a service with 4% error rate, 700ms P99 latency, and 3000 affected users?",
    stream=False
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## View Traces
# MAGIC
# MAGIC All Supervisor API calls are traced to Unity Catalog. You can view them in the AI Gateway UI or query the trace tables directly.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Check if trace tables exist
# MAGIC SHOW TABLES IN `classic_stable_yh3b2z_catalog`.`supertvisor-api` LIKE 'supervisor_traces*';

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Summary
# MAGIC
# MAGIC This demo showcased the **Supervisor API** with the newly supported tool types:
# MAGIC
# MAGIC | Feature | Tool Type | App/Function |
# MAGIC |---------|-----------|-------------|
# MAGIC | Custom MCP Server on Apps | `app` | `mcp-ops-tools` - 4 MCP tools for ops |
# MAGIC | Custom Agent on Apps | `app` | `agent-data-analyst` - data analysis agent |
# MAGIC | UC Functions | `uc_function` | 3 functions: priority, SLA budget, incident format |
# MAGIC | Tracing | `trace_destination` | Traces to Unity Catalog |
# MAGIC | Background Mode | `background=True` | Async execution with polling |
# MAGIC
# MAGIC ### Key Takeaways
# MAGIC 1. **Custom MCP Servers** on Apps expose tools via `@mcp.tool()` decorator with streamable HTTP transport
# MAGIC 2. **Custom Agents** on Apps expose chat endpoints that the Supervisor can delegate to
# MAGIC 3. **UC Functions** provide SQL-native tool capabilities with full governance
# MAGIC 4. The Supervisor API handles all **orchestration** - tool selection, execution, and response synthesis
# MAGIC 5. **Tracing** provides full observability into agent decisions and tool calls
