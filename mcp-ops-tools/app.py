"""
Custom MCP Server hosted on Databricks Apps - Operations Tools
Provides tools for system monitoring, knowledge search, and incident management.
"""

import json
import random
from datetime import datetime
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request

# Create the MCP server
mcp = FastMCP("ops-tools")


# ─── Tool 1: Get System Metrics ───────────────────────────────────────────────
@mcp.tool()
def get_system_metrics(service_name: str) -> str:
    """Get real-time system metrics for a given service including CPU, memory, latency, and error rate.

    Args:
        service_name: Name of the service to check (e.g., 'payment-gateway', 'user-auth', 'order-service', 'inventory-api')
    """
    services_data = {
        "payment-gateway": {"status": "degraded", "team": "payments"},
        "user-auth": {"status": "healthy", "team": "identity"},
        "order-service": {"status": "critical", "team": "commerce"},
        "inventory-api": {"status": "healthy", "team": "supply-chain"},
        "notification-service": {"status": "healthy", "team": "comms"},
        "analytics-pipeline": {"status": "healthy", "team": "data"},
    }
    svc = service_name.lower().strip()
    base = services_data.get(svc, {"status": random.choice(["healthy", "degraded"]), "team": "unknown"})
    metrics = {
        "service": service_name,
        "status": base["status"],
        "team": base["team"],
        "cpu_percent": round(random.uniform(20, 95) if base["status"] != "healthy" else random.uniform(20, 55), 1),
        "memory_percent": round(random.uniform(30, 90) if base["status"] != "healthy" else random.uniform(30, 60), 1),
        "p99_latency_ms": round(random.uniform(200, 800) if base["status"] != "healthy" else random.uniform(50, 200), 0),
        "error_rate_percent": round(random.uniform(1.0, 5.0) if base["status"] == "critical" else random.uniform(0.01, 0.5) if base["status"] == "healthy" else random.uniform(0.5, 2.5), 2),
        "requests_per_sec": random.randint(300, 3000),
        "active_connections": random.randint(50, 500),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return json.dumps(metrics, indent=2)


# ─── Tool 2: Search Knowledge Base ────────────────────────────────────────────
@mcp.tool()
def search_knowledge_base(query: str) -> str:
    """Search the operations knowledge base for runbooks, troubleshooting guides, and best practices.

    Args:
        query: Search query describing the issue or topic
    """
    kb_entries = [
        {"id": "KB-001", "title": "High CPU Usage Troubleshooting Guide", "summary": "Steps: 1) Check runaway processes, 2) Review recent deployments, 3) Check connection pool exhaustion, 4) Scale horizontally, 5) Enable CPU profiling.", "tags": ["cpu", "performance"]},
        {"id": "KB-002", "title": "Payment Gateway Timeout Resolution", "summary": "When payment gateway shows elevated latency: 1) Check downstream bank API, 2) Verify SSL certs, 3) Check connection pool (max=100, timeout=30s), 4) Review circuit breaker, 5) Failover if P99>500ms.", "tags": ["payment", "timeout", "latency"]},
        {"id": "KB-003", "title": "Database Connection Pool Exhaustion", "summary": "Symptoms: increasing latency, connection refused. Fix: 1) SHOW PROCESSLIST, 2) Kill idle connections >300s, 3) Increase pool size, 4) Add read replicas.", "tags": ["database", "connection", "pool"]},
        {"id": "KB-004", "title": "Incident Escalation Procedures", "summary": "P1: 15min response, P2: 30min, P3: 4hr, P4: next business day. Path: On-call -> Team Lead -> VP Eng -> CTO. Update status page for P1/P2.", "tags": ["incident", "escalation"]},
        {"id": "KB-005", "title": "Order Service Auto-Scaling Runbook", "summary": "Triggers: CPU>70% for 5min OR queue>1000 OR P99>500ms. Scale-up: +2 instances (max 20). Scale-down: -1 when CPU<30% for 15min (min 3).", "tags": ["order", "scaling"]},
    ]
    query_lower = query.lower()
    results = []
    for entry in kb_entries:
        score = sum(1 for w in query_lower.split() if w in entry["title"].lower() or w in entry["summary"].lower()) + sum(2 for w in query_lower.split() if w in entry["tags"])
        if score > 0:
            results.append({**entry, "relevance_score": score})
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return json.dumps({"query": query, "results_count": len(results), "results": results[:3]}, indent=2) if results else json.dumps({"message": f"No results for: {query}", "suggestion": "Try broader terms."})


# ─── Tool 3: Create Incident Ticket ───────────────────────────────────────────
@mcp.tool()
def create_incident_ticket(title: str, description: str, severity: str, affected_service: str) -> str:
    """Create an incident ticket in the operations tracking system.

    Args:
        title: Short title of the incident
        description: Detailed description of the issue
        severity: Severity level - one of 'P1', 'P2', 'P3', 'P4'
        affected_service: Name of the affected service
    """
    severity = severity.upper()
    if severity not in ("P1", "P2", "P3", "P4"):
        severity = "P3"
    response_time = {"P1": "15 minutes", "P2": "30 minutes", "P3": "4 hours", "P4": "Next business day"}
    ticket = {
        "ticket_id": f"INC-{random.randint(10000, 99999)}",
        "title": title, "description": description, "severity": severity,
        "affected_service": affected_service, "status": "OPEN",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "expected_response_time": response_time[severity],
        "assigned_team": "SRE On-Call",
        "status_page_updated": severity in ("P1", "P2"),
    }
    return json.dumps(ticket, indent=2)


# ─── Tool 4: List All Services ────────────────────────────────────────────────
@mcp.tool()
def list_services() -> str:
    """List all monitored services and their current status summary."""
    services = [
        {"name": "payment-gateway", "status": "degraded", "region": "us-east-1", "team": "payments"},
        {"name": "user-auth", "status": "healthy", "region": "us-east-1", "team": "identity"},
        {"name": "order-service", "status": "critical", "region": "us-west-2", "team": "commerce"},
        {"name": "inventory-api", "status": "healthy", "region": "us-west-2", "team": "supply-chain"},
        {"name": "notification-service", "status": "healthy", "region": "eu-west-1", "team": "comms"},
        {"name": "analytics-pipeline", "status": "healthy", "region": "us-east-1", "team": "data"},
    ]
    return json.dumps({"services": services, "total": len(services), "timestamp": datetime.utcnow().isoformat() + "Z"}, indent=2)


# ─── REST API (for direct tool testing from the demo UI) ──────────────────────
async def health(request):
    return JSONResponse({"status": "healthy", "app": "mcp-ops-tools"})

async def api_call_tool(request: Request):
    body = await request.json()
    tool_name = body.get("tool", "")
    args = body.get("arguments", {})
    tool_map = {"get_system_metrics": get_system_metrics, "search_knowledge_base": search_knowledge_base, "create_incident_ticket": create_incident_ticket, "list_services": list_services}
    if tool_name in tool_map:
        return JSONResponse({"result": tool_map[tool_name](**args)})
    return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=400)


# ─── ASGI App with proper MCP lifecycle ───────────────────────────────────────
mcp_streamable = mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app):
    async with mcp_streamable.router.lifespan_context(app):
        yield

mcp_app = Starlette(
    routes=[
        Route("/health", health),
        Route("/api/tool", api_call_tool, methods=["POST"]),
        Mount("/", app=mcp_streamable),
    ],
    lifespan=lifespan,
)
