# Supervisor API Demo - Installation & Asset Map

## Workspace
- **URL**: https://fevm-classic-stable-yh3b2z.cloud.databricks.com
- **Profile**: `fevm-classic`
- **Catalog**: `classic_stable_yh3b2z_catalog`
- **Schema**: `supertvisor-api`
- **SQL Warehouse**: `25899ae5a5341c16` (Serverless Starter Warehouse)

---

## Deployed Databricks Apps (3 apps)

| App Name | Type | Status | URL |
|----------|------|--------|-----|
| `supervisor-demo` | Main UI (FastAPI + HTML) | RUNNING | https://supervisor-demo-7474660536314099.aws.databricksapps.com |
| `mcp-ops-tools` | Custom MCP Server | RUNNING | https://mcp-ops-tools-7474660536314099.aws.databricksapps.com |
| `agent-data-analyst` | Custom Agent | RUNNING | https://agent-data-analyst-7474660536314099.aws.databricksapps.com |

### App Source Code on Workspace
| App | Workspace Path |
|-----|---------------|
| `supervisor-demo` | `/Users/sarbani.maiti@databricks.com/supervisor-app/` |
| `mcp-ops-tools` | `/Users/sarbani.maiti@databricks.com/mcp-ops-tools/` |
| `agent-data-analyst` | `/Users/sarbani.maiti@databricks.com/agent-data-analyst/` |

---

## Unity Catalog Functions (3 functions)

All in `classic_stable_yh3b2z_catalog`.`supertvisor-api`:

| Function | Signature | Purpose |
|----------|-----------|---------|
| `classify_priority` | `(error_rate DOUBLE, p99_latency_ms DOUBLE, affected_users INT) -> STRING` | Classify incident severity P1-P4 |
| `calculate_sla_budget` | `(uptime_percent DOUBLE, sla_target DOUBLE, days_in_period INT, days_elapsed INT) -> STRING` | Calculate SLA error budget |
| `format_incident_summary` | `(service_name STRING, severity STRING, error_rate DOUBLE, latency_ms DOUBLE, description STRING) -> STRING` | Format stakeholder incident report |

---

## Notebooks on Workspace

| Notebook | Path | Purpose |
|----------|------|---------|
| Setup UC Functions | `/Users/sarbani.maiti@databricks.com/supervisor-api-demo/01_setup_uc_functions` | Creates UC functions |
| Supervisor API Demo | `/Users/sarbani.maiti@databricks.com/supervisor-api-demo/02_supervisor_api_demo` | 6 demo scenarios using Supervisor API |

---

## Local File Structure

```
supervisor-api-demo/
|-- INSTALLATION.md              # This file
|-- README.md                    # GitHub README
|
|-- supervisor-app-v2/           # Main demo app (FastAPI + HTML frontend)
|   |-- app.yaml                 # Databricks App config
|   |-- requirements.txt
|   |-- server/
|   |   |-- __init__.py
|   |   |-- app.py               # FastAPI backend - tool execution, chat API
|   |-- client/
|       |-- index.html           # Single-page frontend (7 guided pages)
|
|-- mcp-ops-tools/               # Custom MCP Server app
|   |-- app.yaml
|   |-- app.py                   # 4 MCP tools + REST API
|   |-- requirements.txt
|
|-- agent-data-analyst/          # Custom Agent app
|   |-- app.yaml
|   |-- app.py                   # Data analysis agent with /chat endpoint
|   |-- requirements.txt
|
|-- notebooks/
|   |-- 01_setup_uc_functions.py # Databricks notebook - UC function creation
|   |-- 02_supervisor_api_demo.py # Databricks notebook - Supervisor API demos
|
|-- supervisor-app/              # (v1 Streamlit version - superseded by v2)
    |-- app.py
    |-- app.yaml
    |-- requirements.txt
```

---

## Service Principal Permissions

The `supervisor-demo` app SP (`cef009cd-de97-4815-a0a2-237f727637d8`) has:
- **CAN_USE** on `mcp-ops-tools` app
- **CAN_USE** on `agent-data-analyst` app
- **CAN_USE** on SQL warehouse `25899ae5a5341c16`
- **USE CATALOG** on `classic_stable_yh3b2z_catalog`
- **USE SCHEMA, EXECUTE** on `classic_stable_yh3b2z_catalog`.`supertvisor-api`

---

## Redeployment Commands

```bash
# Redeploy supervisor demo
databricks sync ./supervisor-app-v2 "/Users/sarbani.maiti@databricks.com/supervisor-app" \
  --profile fevm-classic --watch=false
databricks apps deploy supervisor-demo \
  --source-code-path "/Workspace/Users/sarbani.maiti@databricks.com/supervisor-app" \
  --profile fevm-classic

# Redeploy MCP server
databricks sync ./mcp-ops-tools "/Users/sarbani.maiti@databricks.com/mcp-ops-tools" \
  --profile fevm-classic --watch=false
databricks apps deploy mcp-ops-tools \
  --source-code-path "/Workspace/Users/sarbani.maiti@databricks.com/mcp-ops-tools" \
  --profile fevm-classic

# Redeploy agent
databricks sync ./agent-data-analyst "/Users/sarbani.maiti@databricks.com/agent-data-analyst" \
  --profile fevm-classic --watch=false
databricks apps deploy agent-data-analyst \
  --source-code-path "/Workspace/Users/sarbani.maiti@databricks.com/agent-data-analyst" \
  --profile fevm-classic
```

---

## Fresh Install on New Workspace

1. Create 3 apps: `databricks apps create <name>`
2. Create UC schema: `CREATE SCHEMA IF NOT EXISTS catalog.schema`
3. Run `01_setup_uc_functions` notebook to create UC functions
4. Update `app.yaml` env vars with new workspace URLs, warehouse ID, catalog/schema
5. Sync and deploy all 3 apps
6. Grant SP permissions (catalog, schema, warehouse, cross-app access)
7. Open the supervisor-demo app URL
