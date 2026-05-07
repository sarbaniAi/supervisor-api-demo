#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Supervisor API Demo - One-Click Setup
# Deploys 3 Databricks Apps + UC Functions on any Databricks workspace
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ─── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ─── Check Prerequisites ──────────────────────────────────────────────────────
info "Checking prerequisites..."
command -v databricks >/dev/null 2>&1 || error "databricks CLI not found. Install: https://docs.databricks.com/dev-tools/cli/install.html"
command -v python3 >/dev/null 2>&1 || error "python3 not found"

# ─── Get Configuration ─────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Supervisor API Demo - Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# Profile
if [ -n "$1" ]; then
    PROFILE="$1"
else
    read -p "Databricks CLI profile (or press Enter for DEFAULT): " PROFILE
    PROFILE=${PROFILE:-DEFAULT}
fi
PROFILE_FLAG="--profile $PROFILE"
if [ "$PROFILE" = "DEFAULT" ]; then PROFILE_FLAG=""; fi

# Validate auth
info "Validating authentication..."
WHOAMI=$(databricks current-user me $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('userName',''))" 2>/dev/null)
[ -z "$WHOAMI" ] && error "Authentication failed. Run: databricks auth login --host <workspace-url> --profile $PROFILE"
ok "Authenticated as: $WHOAMI"

# Get workspace URL
HOST=$(databricks auth env $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('env',{}).get('DATABRICKS_HOST',''))" 2>/dev/null)
ok "Workspace: $HOST"

# Catalog
read -p "Unity Catalog name [press Enter to auto-detect]: " CATALOG
if [ -z "$CATALOG" ]; then
    CATALOG=$(databricks catalogs list $PROFILE_FLAG 2>&1 | head -2 | tail -1 | awk '{print $1}')
    info "Using catalog: $CATALOG"
fi

SCHEMA="supervisor_api"
info "Schema: $CATALOG.$SCHEMA"

# ─── Find SQL Warehouse ───────────────────────────────────────────────────────
info "Finding SQL warehouse..."
WAREHOUSE_ID=$(databricks warehouses list $PROFILE_FLAG 2>&1 | grep -v "^ID" | head -1 | awk '{print $1}')
[ -z "$WAREHOUSE_ID" ] && error "No SQL warehouse found. Create one first."
ok "Warehouse: $WAREHOUSE_ID"

# ─── Check Supervisor API Preview ──────────────────────────────────────────────
info "Checking Supervisor API preview..."
python3 -c "
from databricks.sdk import WorkspaceClient
w = WorkspaceClient(profile='$PROFILE' if '$PROFILE' != 'DEFAULT' else None)
try:
    val = w.workspace_settings_v2.get_public_workspace_setting(name='supervisor_api')
    if val.effective_boolean_val and val.effective_boolean_val.value:
        print('ENABLED')
    else:
        print('DISABLED')
except:
    print('NOT_ENROLLED')
" 2>/dev/null | {
    read STATUS
    if [ "$STATUS" = "ENABLED" ]; then
        ok "Supervisor API preview is enabled"
    else
        warn "Supervisor API preview is NOT enabled."
        echo "  Go to: $HOST/settings/previews"
        echo "  Search for 'Supervisor API' and toggle it ON"
        read -p "  Press Enter once enabled (or Ctrl+C to abort)..."
    fi
}

# ─── Create Schema & UC Functions ──────────────────────────────────────────────
info "Creating schema and UC functions..."
TOKEN=$(databricks auth token --host "$HOST" $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['access_token'])")

run_sql() {
    RESULT=$(curl -s -X POST "$HOST/api/2.0/sql/statements" \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"statement\": \"$1\", \"warehouse_id\": \"$WAREHOUSE_ID\", \"wait_timeout\": \"50s\"}" 2>&1)
    STATE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('status',{}).get('state','FAILED'))" 2>/dev/null)
    echo "$STATE"
}

S=$(run_sql "CREATE SCHEMA IF NOT EXISTS $CATALOG.$SCHEMA")
[ "$S" = "SUCCEEDED" ] && ok "Schema created" || warn "Schema: $S"

S=$(run_sql "CREATE OR REPLACE FUNCTION $CATALOG.$SCHEMA.classify_priority(error_rate DOUBLE COMMENT 'Error rate %', p99_latency_ms DOUBLE COMMENT 'P99 latency ms', affected_users INT COMMENT 'Affected users') RETURNS STRING COMMENT 'Classifies incident priority P1-P4' RETURN CASE WHEN error_rate > 5.0 OR p99_latency_ms > 1000 OR affected_users > 10000 THEN 'P1 - Critical: Immediate response (15 min SLA)' WHEN error_rate > 2.0 OR p99_latency_ms > 500 OR affected_users > 1000 THEN 'P2 - High: Urgent response (30 min SLA)' WHEN error_rate > 0.5 OR p99_latency_ms > 300 OR affected_users > 100 THEN 'P3 - Medium: Standard response (4 hr SLA)' ELSE 'P4 - Low: Next business day' END")
[ "$S" = "SUCCEEDED" ] && ok "classify_priority created" || warn "classify_priority: $S"

S=$(run_sql "CREATE OR REPLACE FUNCTION $CATALOG.$SCHEMA.calculate_sla_budget(uptime_percent DOUBLE COMMENT 'Current uptime %', sla_target DOUBLE COMMENT 'SLA target %', days_in_period INT COMMENT 'Total days', days_elapsed INT COMMENT 'Days elapsed') RETURNS STRING COMMENT 'Calculates SLA error budget' RETURN CONCAT('SLA Budget: Target=', CAST(sla_target AS STRING), '%, Current=', CAST(uptime_percent AS STRING), '%, Allowed=', CAST(ROUND((100 - sla_target) / 100 * days_in_period * 24 * 60, 1) AS STRING), 'min, Used=', CAST(ROUND((100 - uptime_percent) / 100 * days_elapsed * 24 * 60, 1) AS STRING), 'min, Remaining=', CAST(ROUND(((100 - sla_target) / 100 * days_in_period * 24 * 60) - ((100 - uptime_percent) / 100 * days_elapsed * 24 * 60), 1) AS STRING), 'min, Risk=', CASE WHEN uptime_percent < sla_target THEN 'BREACHED' WHEN (uptime_percent - sla_target) < 0.05 THEN 'CRITICAL' WHEN (uptime_percent - sla_target) < 0.1 THEN 'WARNING' ELSE 'HEALTHY' END)")
[ "$S" = "SUCCEEDED" ] && ok "calculate_sla_budget created" || warn "calculate_sla_budget: $S"

S=$(run_sql "CREATE OR REPLACE FUNCTION $CATALOG.$SCHEMA.format_incident_summary(service_name STRING COMMENT 'Service name', severity STRING COMMENT 'Severity P1-P4', error_rate DOUBLE COMMENT 'Error rate %', latency_ms DOUBLE COMMENT 'P99 latency ms', description STRING COMMENT 'Description') RETURNS STRING COMMENT 'Formats incident report' RETURN CONCAT('=== INCIDENT REPORT === Service: ', service_name, ' | Severity: ', severity, ' | Error Rate: ', CAST(error_rate AS STRING), '% | P99: ', CAST(latency_ms AS STRING), 'ms | Description: ', description, ' | Impact: ', CASE WHEN severity = 'P1' THEN 'Customer-facing outage' WHEN severity = 'P2' THEN 'Service degradation' ELSE 'Minor issue' END, ' === END ===')")
[ "$S" = "SUCCEEDED" ] && ok "format_incident_summary created" || warn "format_incident_summary: $S"

# ─── Create and Deploy Apps ────────────────────────────────────────────────────
info "Creating Databricks Apps..."

create_and_deploy_app() {
    APP_NAME=$1
    SOURCE_DIR=$2

    # Create app (ignore if exists)
    databricks apps create "$APP_NAME" $PROFILE_FLAG 2>/dev/null || true

    # Sync source
    databricks sync "./$SOURCE_DIR" "/Users/$WHOAMI/$APP_NAME" $PROFILE_FLAG --watch=false 2>&1 | grep -q "Sync Complete" && ok "Synced $APP_NAME" || warn "Sync $APP_NAME may have issues"

    # Deploy
    RESULT=$(databricks apps deploy "$APP_NAME" --source-code-path "/Workspace/Users/$WHOAMI/$APP_NAME" $PROFILE_FLAG 2>&1)
    if echo "$RESULT" | grep -q "SUCCEEDED"; then
        ok "Deployed $APP_NAME"
    else
        warn "Deploy $APP_NAME: check logs with 'databricks apps logs $APP_NAME $PROFILE_FLAG'"
    fi
}

# Deploy MCP Server
info "Deploying MCP Server (mcp-ops-tools)..."
create_and_deploy_app "mcp-ops-tools" "mcp-ops-tools"

# Deploy Agent
info "Deploying Agent (agent-data-analyst)..."
create_and_deploy_app "agent-data-analyst" "agent-data-analyst"

# Update supervisor app config with workspace-specific values
info "Configuring supervisor app..."
WORKSPACE_ID=$(echo "$HOST" | grep -o '[0-9]*' | head -1 || echo "")
MCP_URL="https://mcp-ops-tools-${WORKSPACE_ID}.aws.databricksapps.com"
AGENT_URL="https://agent-data-analyst-${WORKSPACE_ID}.aws.databricksapps.com"

# Get the actual app URLs
MCP_URL=$(databricks apps get mcp-ops-tools $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('url',''))" 2>/dev/null)
AGENT_URL=$(databricks apps get agent-data-analyst $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('url',''))" 2>/dev/null)

# Update app.yaml with correct values
cd supervisor-app-v2
python3 -c "
import re
with open('app.yaml', 'r') as f: content = f.read()
replacements = {
    'MCP_APP_URL': '$MCP_URL',
    'AGENT_APP_URL': '$AGENT_URL',
    'UC_CATALOG': '$CATALOG',
    'UC_SCHEMA': '$SCHEMA',
    'SQL_WAREHOUSE_ID': '$WAREHOUSE_ID',
    'WORKSPACE_URL': '$HOST',
}
for key, val in replacements.items():
    content = re.sub(f'(name: {key}\\n\\s+value: ).*', f'\\\\1{val}', content)
with open('app.yaml', 'w') as f: f.write(content)
print('Updated app.yaml')
"
cd ..

# Deploy Supervisor Demo
info "Deploying Supervisor Demo (supervisor-demo)..."
create_and_deploy_app "supervisor-demo" "supervisor-app-v2"

# ─── Grant Permissions ─────────────────────────────────────────────────────────
info "Granting cross-app permissions..."
SUPERVISOR_SP=$(databricks apps get supervisor-demo $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('service_principal_client_id',''))" 2>/dev/null)

# Grant SP access to other apps
curl -s -X PATCH "$HOST/api/2.0/permissions/apps/mcp-ops-tools" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"access_control_list\": [{\"service_principal_name\": \"$SUPERVISOR_SP\", \"permission_level\": \"CAN_USE\"}]}" >/dev/null 2>&1
curl -s -X PATCH "$HOST/api/2.0/permissions/apps/agent-data-analyst" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"access_control_list\": [{\"service_principal_name\": \"$SUPERVISOR_SP\", \"permission_level\": \"CAN_USE\"}]}" >/dev/null 2>&1

# Grant SQL warehouse access
curl -s -X PATCH "$HOST/api/2.0/permissions/sql/warehouses/$WAREHOUSE_ID" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"access_control_list\": [{\"service_principal_name\": \"$SUPERVISOR_SP\", \"permission_level\": \"CAN_USE\"}]}" >/dev/null 2>&1

# Grant UC catalog/schema access
run_sql "GRANT USE CATALOG ON CATALOG $CATALOG TO \`$SUPERVISOR_SP\`" >/dev/null 2>&1
run_sql "GRANT USE SCHEMA, EXECUTE ON SCHEMA $CATALOG.$SCHEMA TO \`$SUPERVISOR_SP\`" >/dev/null 2>&1

ok "Permissions configured"

# ─── Summary ───────────────────────────────────────────────────────────────────
DEMO_URL=$(databricks apps get supervisor-demo $PROFILE_FLAG 2>&1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('url',''))" 2>/dev/null)

echo ""
echo "═══════════════════════════════════════════════════════"
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo -e "  Demo App:  ${BLUE}$DEMO_URL${NC}"
echo -e "  MCP Server: $MCP_URL"
echo -e "  Agent App:  $AGENT_URL"
echo ""
echo "  Catalog:    $CATALOG.$SCHEMA"
echo "  Warehouse:  $WAREHOUSE_ID"
echo "  Profile:    $PROFILE"
echo ""
echo "═══════════════════════════════════════════════════════"
