# Supervisor API Demo: New Tool Types

Interactive demo showcasing the **newly supported tool types** in Databricks Supervisor Agent and Supervisor API:

- **Custom MCP Servers** hosted on Databricks Apps
- **Custom Agents** hosted on Databricks Apps
- **External MCP Servers** with U2M Per-User Auth
- **Unity Catalog Functions** as tools

## Architecture

```
                Supervisor API / Chat Completions
                (Claude Sonnet 4.6 + Function Calling)
                              |
          +-------------------+-------------------+
          |                   |                   |
    MCP Server           Agent App          UC Functions
    (Databricks App)    (Databricks App)   (Unity Catalog)
          |                   |                   |
    4 ops tools:        Analytics:          3 SQL functions:
    - metrics           - trends            - classify_priority
    - kb search         - reliability       - calculate_sla_budget
    - incidents         - costs             - format_incident_summary
    - list svcs         - summaries
```

## Demo App Features

The main app is a guided, multi-page experience (inspired by [MLflow GenAI Demo](https://docs.databricks.com/en/mlflow/genai/index.html)):

| Page | Content |
|------|---------|
| Demo Overview | Architecture, tool types table, quick-start code |
| Custom MCP Server | How-to steps, code, **interactive tool tester** |
| Custom Agent on Apps | Code, **live agent test**, multi-cloud patterns |
| UC Functions | SQL examples, **interactive priority classifier** |
| External MCP (U2M Auth) | Setup steps, pre-built connectors |
| API vs Agent Bricks | Side-by-side comparison, when-to-use guide |
| Selling Points | SA field guide, objection handling |
| Live Supervisor Agent | Chat UI with 4 scenario buttons |

## Components

| Component | Directory | Description |
|-----------|-----------|-------------|
| Supervisor Demo App | `supervisor-app-v2/` | FastAPI + HTML frontend (main UI) |
| MCP Server App | `mcp-ops-tools/` | Custom MCP server with 4 ops tools |
| Agent App | `agent-data-analyst/` | Data analysis agent with /chat endpoint |
| Notebooks | `notebooks/` | UC function setup + Supervisor API notebook |

## Quick Deploy

### Prerequisites
- Databricks workspace with Unity Catalog
- `databricks` CLI authenticated
- Foundation Model API access (Claude Sonnet or GPT-5)

### Steps

```bash
# 1. Clone
git clone https://github.com/sarbaniAi/supervisor-api-demo.git
cd supervisor-api-demo

# 2. Create apps
databricks apps create mcp-ops-tools
databricks apps create agent-data-analyst
databricks apps create supervisor-demo

# 3. Create UC schema and functions
# Import and run notebooks/01_setup_uc_functions.py

# 4. Update supervisor-app-v2/app.yaml with your workspace URLs

# 5. Deploy all 3 apps
for app_dir in mcp-ops-tools agent-data-analyst; do
  databricks sync ./$app_dir "/Users/$USER/$app_dir" --watch=false
  databricks apps deploy $app_dir --source-code-path "/Workspace/Users/$USER/$app_dir"
done

databricks sync ./supervisor-app-v2 "/Users/$USER/supervisor-app" --watch=false
databricks apps deploy supervisor-demo --source-code-path "/Workspace/Users/$USER/supervisor-app"

# 6. Grant cross-app permissions (see INSTALLATION.md)
```

## Supervisor API Code (Native)

When the `supervisor_api` workspace preview is enabled:

```python
from databricks_openai import DatabricksOpenAI

client = DatabricksOpenAI(use_ai_gateway=True)

response = client.responses.create(
    model="databricks-claude-sonnet-4-6",
    input=[{"type": "message", "role": "user",
            "content": "Check system health and investigate issues"}],
    tools=[
        {"type": "app", "app": {"name": "mcp-ops-tools", "description": "Ops monitoring tools"}},
        {"type": "app", "app": {"name": "agent-data-analyst", "description": "Data analytics"}},
        {"type": "uc_function", "uc_function": {"name": "catalog.schema.classify_priority",
         "description": "Classify incident severity"}},
    ],
    stream=True
)
```

## Resources

- [Supervisor API Docs](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/supervisor-api)
- [MCP on Databricks](https://docs.databricks.com/aws/en/generative-ai/mcp)
- [Custom MCP Servers](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
- [External MCP Servers](https://docs.databricks.com/aws/en/generative-ai/mcp/external-mcp)

## License

Databricks Field Engineering internal demo.
