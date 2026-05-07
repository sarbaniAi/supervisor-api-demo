"""
Custom MCP Server hosted on Databricks Apps - Operations Tools
Provides tools for system monitoring, knowledge search, and incident management.
"""

import json
import random
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse

# Create the MCP server
mcp = FastMCP("ops-tools")


# ─── Tool 1: Get System Metrics ───────────────────────────────────────────────
@mcp.tool()
def get_system_metrics(service_name: str) -> str:
    """Get real-time system metrics for a given service including CPU, memory, latency, and error rate.
    Use this tool when the user asks about system health, performance, or monitoring data.

    Args:
        service_name: Name of the service to check (e.g., 'payment-gateway', 'user-auth', 'order-service', 'inventory-api')
    """
    # Simulated metrics for demo purposes
    services = {
        "payment-gateway": {
            "cpu_percent": round(random.uniform(45, 85), 1),
            "memory_percent": round(random.uniform(50, 78), 1),
            "p99_latency_ms": round(random.uniform(120, 450), 0),
            "error_rate_percent": round(random.uniform(0.1, 2.5), 2),
            "requests_per_sec": random.randint(800, 2500),
            "status": "degraded" if random.random() > 0.6 else "healthy",
            "active_connections": random.randint(150, 500),
            "uptime_hours": round(random.uniform(24, 720), 1),
        },
        "user-auth": {
            "cpu_percent": round(random.uniform(20, 55), 1),
            "memory_percent": round(random.uniform(30, 60), 1),
            "p99_latency_ms": round(random.uniform(50, 200), 0),
            "error_rate_percent": round(random.uniform(0.01, 0.5), 2),
            "requests_per_sec": random.randint(1000, 5000),
            "status": "healthy",
            "active_connections": random.randint(200, 800),
            "uptime_hours": round(random.uniform(168, 720), 1),
        },
        "order-service": {
            "cpu_percent": round(random.uniform(60, 95), 1),
            "memory_percent": round(random.uniform(65, 90), 1),
            "p99_latency_ms": round(random.uniform(200, 800), 0),
            "error_rate_percent": round(random.uniform(1.0, 5.0), 2),
            "requests_per_sec": random.randint(500, 1500),
            "status": "critical" if random.random() > 0.5 else "degraded",
            "active_connections": random.randint(100, 400),
            "uptime_hours": round(random.uniform(2, 48), 1),
        },
        "inventory-api": {
            "cpu_percent": round(random.uniform(30, 65), 1),
            "memory_percent": round(random.uniform(40, 70), 1),
            "p99_latency_ms": round(random.uniform(80, 300), 0),
            "error_rate_percent": round(random.uniform(0.05, 1.0), 2),
            "requests_per_sec": random.randint(300, 1200),
            "status": "healthy",
            "active_connections": random.randint(50, 250),
            "uptime_hours": round(random.uniform(72, 720), 1),
        },
    }

    svc = service_name.lower().strip()
    if svc in services:
        metrics = services[svc]
    else:
        # Generate random metrics for unknown services
        metrics = {
            "cpu_percent": round(random.uniform(20, 90), 1),
            "memory_percent": round(random.uniform(30, 85), 1),
            "p99_latency_ms": round(random.uniform(50, 500), 0),
            "error_rate_percent": round(random.uniform(0.01, 3.0), 2),
            "requests_per_sec": random.randint(100, 3000),
            "status": random.choice(["healthy", "degraded", "critical"]),
            "active_connections": random.randint(10, 500),
            "uptime_hours": round(random.uniform(1, 720), 1),
        }

    metrics["service"] = service_name
    metrics["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return json.dumps(metrics, indent=2)


# ─── Tool 2: Search Knowledge Base ────────────────────────────────────────────
@mcp.tool()
def search_knowledge_base(query: str) -> str:
    """Search the operations knowledge base for runbooks, troubleshooting guides, and best practices.
    Use this tool when the user asks about how to fix issues, troubleshooting steps, or operational procedures.

    Args:
        query: Search query describing the issue or topic
    """
    # Simulated knowledge base entries
    kb_entries = [
        {
            "id": "KB-001",
            "title": "High CPU Usage Troubleshooting Guide",
            "summary": "Steps to diagnose and resolve high CPU usage: 1) Check for runaway processes with top/htop, 2) Review recent deployments, 3) Check for connection pool exhaustion, 4) Scale horizontally if load is legitimate, 5) Enable CPU profiling for detailed analysis.",
            "tags": ["cpu", "performance", "troubleshooting"],
            "last_updated": "2026-04-15",
        },
        {
            "id": "KB-002",
            "title": "Payment Gateway Timeout Resolution",
            "summary": "When payment gateway shows elevated latency: 1) Check downstream bank API status, 2) Verify SSL certificate expiry, 3) Check connection pool settings (max_connections=100, timeout=30s), 4) Review circuit breaker state, 5) Failover to backup payment processor if P99 > 500ms.",
            "tags": ["payment", "timeout", "latency", "gateway"],
            "last_updated": "2026-05-01",
        },
        {
            "id": "KB-003",
            "title": "Database Connection Pool Exhaustion",
            "summary": "Symptoms: increasing latency, connection refused errors. Resolution: 1) Check current pool size vs max (SHOW PROCESSLIST), 2) Identify long-running queries, 3) Kill idle connections older than 300s, 4) Increase pool size if under-provisioned, 5) Add read replicas for read-heavy workloads.",
            "tags": ["database", "connection", "pool", "performance"],
            "last_updated": "2026-04-28",
        },
        {
            "id": "KB-004",
            "title": "Incident Escalation Procedures",
            "summary": "Severity levels: P1 (customer-facing outage, 15min response), P2 (degraded service, 30min response), P3 (non-critical, 4hr response), P4 (cosmetic, next business day). Escalation path: On-call engineer -> Team Lead -> VP Engineering -> CTO. Always update status page for P1/P2.",
            "tags": ["incident", "escalation", "procedures", "severity"],
            "last_updated": "2026-03-20",
        },
        {
            "id": "KB-005",
            "title": "Order Service Auto-Scaling Runbook",
            "summary": "Auto-scaling triggers: CPU > 70% for 5min OR request queue > 1000 OR P99 latency > 500ms. Scale-up: add 2 instances (max 20). Scale-down: remove 1 instance when CPU < 30% for 15min (min 3). Always verify health checks pass before routing traffic to new instances.",
            "tags": ["order", "scaling", "auto-scaling", "runbook"],
            "last_updated": "2026-04-10",
        },
    ]

    # Simple keyword matching for demo
    query_lower = query.lower()
    results = []
    for entry in kb_entries:
        score = 0
        for word in query_lower.split():
            if word in entry["title"].lower() or word in entry["summary"].lower():
                score += 1
            if word in entry["tags"]:
                score += 2
        if score > 0:
            results.append({**entry, "relevance_score": score})

    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    if not results:
        return json.dumps({"message": f"No results found for: {query}", "suggestion": "Try broader search terms or check the knowledge base portal."})

    return json.dumps({"query": query, "results_count": len(results), "results": results[:3]}, indent=2)


# ─── Tool 3: Create Incident Ticket ───────────────────────────────────────────
@mcp.tool()
def create_incident_ticket(
    title: str,
    description: str,
    severity: str,
    affected_service: str,
) -> str:
    """Create an incident ticket in the operations tracking system.
    Use this tool when an issue needs to be formally tracked and escalated.

    Args:
        title: Short title of the incident
        description: Detailed description of the issue, symptoms, and impact
        severity: Severity level - one of 'P1', 'P2', 'P3', 'P4'
        affected_service: Name of the affected service
    """
    ticket_id = f"INC-{random.randint(10000, 99999)}"
    created_at = datetime.utcnow().isoformat() + "Z"

    severity = severity.upper()
    if severity not in ("P1", "P2", "P3", "P4"):
        severity = "P3"

    response_time = {"P1": "15 minutes", "P2": "30 minutes", "P3": "4 hours", "P4": "Next business day"}

    ticket = {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "severity": severity,
        "affected_service": affected_service,
        "status": "OPEN",
        "created_at": created_at,
        "expected_response_time": response_time[severity],
        "assigned_team": "SRE On-Call",
        "escalation_path": "On-call -> Team Lead -> VP Engineering",
        "status_page_updated": severity in ("P1", "P2"),
    }

    return json.dumps(ticket, indent=2)


# ─── Tool 4: List All Services ────────────────────────────────────────────────
@mcp.tool()
def list_services() -> str:
    """List all monitored services and their current status summary.
    Use this tool when the user wants an overview of all services."""
    services = [
        {"name": "payment-gateway", "status": "degraded", "region": "us-east-1", "team": "payments"},
        {"name": "user-auth", "status": "healthy", "region": "us-east-1", "team": "identity"},
        {"name": "order-service", "status": "critical", "region": "us-west-2", "team": "commerce"},
        {"name": "inventory-api", "status": "healthy", "region": "us-west-2", "team": "supply-chain"},
        {"name": "notification-service", "status": "healthy", "region": "eu-west-1", "team": "comms"},
        {"name": "analytics-pipeline", "status": "healthy", "region": "us-east-1", "team": "data"},
    ]
    return json.dumps({"services": services, "total": len(services), "timestamp": datetime.utcnow().isoformat() + "Z"}, indent=2)


# ─── REST API endpoints (for supervisor to call directly) ──────────────────────
from starlette.requests import Request


async def health(request):
    return JSONResponse({"status": "healthy", "app": "mcp-ops-tools"})


async def api_call_tool(request: Request):
    """REST endpoint to call any MCP tool by name."""
    body = await request.json()
    tool_name = body.get("tool", "")
    args = body.get("arguments", {})

    tool_map = {
        "get_system_metrics": get_system_metrics,
        "search_knowledge_base": search_knowledge_base,
        "create_incident_ticket": create_incident_ticket,
        "list_services": list_services,
    }

    if tool_name in tool_map:
        result = tool_map[tool_name](**args)
        return JSONResponse({"result": result})
    else:
        return JSONResponse({"error": f"Unknown tool: {tool_name}", "available": list(tool_map.keys())}, status_code=400)


# ─── Mount MCP + REST as ASGI app ─────────────────────────────────────────────
mcp_app = Starlette(
    routes=[
        Route("/health", health),
        Route("/api/tool", api_call_tool, methods=["POST"]),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ],
)
