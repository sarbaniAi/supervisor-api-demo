"""
Custom Agent hosted on Databricks Apps - Data Analyst Agent
This agent analyzes operational data and provides insights.
It exposes a ChatCompletion-compatible endpoint so the Supervisor API can call it as an "app" tool.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Data Analyst Agent")


# ─── Simulated data store ─────────────────────────────────────────────────────
def generate_incident_trends():
    """Generate simulated incident trend data."""
    categories = ["infrastructure", "application", "database", "network", "security"]
    trends = []
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        daily = {}
        for cat in categories:
            daily[cat] = random.randint(0, 15)
        trends.append({"date": date, "incidents": daily, "total": sum(daily.values())})
    return trends


def generate_service_reliability():
    """Generate simulated service reliability data."""
    services = ["payment-gateway", "user-auth", "order-service", "inventory-api", "notification-service"]
    data = []
    for svc in services:
        uptime = round(random.uniform(95.0, 99.99), 2)
        mttr_minutes = round(random.uniform(5, 120), 1)
        incidents_30d = random.randint(0, 15)
        data.append({
            "service": svc,
            "uptime_percent_30d": uptime,
            "mttr_minutes": mttr_minutes,
            "incidents_last_30d": incidents_30d,
            "sla_target": 99.9,
            "sla_met": uptime >= 99.9,
        })
    return data


def analyze_query(question: str) -> str:
    """Simple query analysis to return relevant data insights."""
    q = question.lower()

    if any(w in q for w in ["trend", "incident", "pattern", "week"]):
        trends = generate_incident_trends()
        total_incidents = sum(t["total"] for t in trends)
        worst_day = max(trends, key=lambda t: t["total"])
        top_category = {}
        for t in trends:
            for cat, count in t["incidents"].items():
                top_category[cat] = top_category.get(cat, 0) + count
        top_cat = max(top_category, key=top_category.get)

        return json.dumps({
            "analysis_type": "incident_trends",
            "period": "last_7_days",
            "total_incidents": total_incidents,
            "daily_average": round(total_incidents / 7, 1),
            "worst_day": {"date": worst_day["date"], "count": worst_day["total"]},
            "top_category": {"name": top_cat, "count": top_category[top_cat]},
            "trend_direction": random.choice(["increasing", "stable", "decreasing"]),
            "daily_breakdown": trends,
            "recommendation": f"Focus on {top_cat} incidents which account for {round(top_category[top_cat]/total_incidents*100, 1)}% of all incidents.",
        }, indent=2)

    elif any(w in q for w in ["reliability", "uptime", "sla", "mttr"]):
        reliability = generate_service_reliability()
        sla_breaches = [s for s in reliability if not s["sla_met"]]

        return json.dumps({
            "analysis_type": "service_reliability",
            "period": "last_30_days",
            "services_analyzed": len(reliability),
            "sla_breaches": len(sla_breaches),
            "breached_services": [s["service"] for s in sla_breaches],
            "avg_uptime": round(sum(s["uptime_percent_30d"] for s in reliability) / len(reliability), 2),
            "avg_mttr_minutes": round(sum(s["mttr_minutes"] for s in reliability) / len(reliability), 1),
            "service_details": reliability,
            "recommendation": f"{'Investigate ' + sla_breaches[0]['service'] + ' - SLA breach detected.' if sla_breaches else 'All services meeting SLA targets.'}",
        }, indent=2)

    elif any(w in q for w in ["cost", "spend", "budget", "resource"]):
        services = ["payment-gateway", "user-auth", "order-service", "inventory-api", "notification-service"]
        cost_data = []
        for svc in services:
            compute = round(random.uniform(500, 5000), 2)
            storage = round(random.uniform(100, 1000), 2)
            network = round(random.uniform(50, 500), 2)
            cost_data.append({
                "service": svc,
                "compute_cost": compute,
                "storage_cost": storage,
                "network_cost": network,
                "total_cost": round(compute + storage + network, 2),
            })
        total = sum(c["total_cost"] for c in cost_data)
        most_expensive = max(cost_data, key=lambda c: c["total_cost"])

        return json.dumps({
            "analysis_type": "cost_analysis",
            "period": "current_month",
            "total_spend": round(total, 2),
            "budget": 25000.00,
            "budget_utilization_percent": round(total / 25000 * 100, 1),
            "most_expensive_service": most_expensive["service"],
            "cost_breakdown": cost_data,
            "recommendation": f"{'Budget on track.' if total < 25000 else 'Over budget - review ' + most_expensive['service'] + ' costs.'}",
        }, indent=2)

    else:
        # General operational summary
        return json.dumps({
            "analysis_type": "operational_summary",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "active_incidents": random.randint(1, 8),
            "services_healthy": random.randint(4, 6),
            "services_total": 6,
            "avg_response_time_ms": round(random.uniform(100, 400), 0),
            "deployments_today": random.randint(0, 5),
            "alerts_triggered_24h": random.randint(3, 25),
            "recommendation": "Review order-service which has shown elevated error rates in the past hour.",
        }, indent=2)


# ─── Chat Completion compatible endpoint ──────────────────────────────────────
@app.post("/chat")
async def chat(request: Request):
    """Chat endpoint compatible with Databricks App tool interface."""
    body = await request.json()
    messages = body.get("messages", [])

    # Extract the user's question from the last message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        user_message = "Give me an operational summary"

    # Generate analysis
    analysis = analyze_query(user_message)

    return JSONResponse({
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"Here is my analysis:\n\n{analysis}",
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
        "model": "data-analyst-agent",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "data-analyst", "version": "1.0.0"}
