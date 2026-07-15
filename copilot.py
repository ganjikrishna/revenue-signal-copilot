"""Core, framework-free business logic for Revenue Signal Copilot."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any


INDUSTRY_FIT = {"marketing", "media", "sports", "entertainment", "health and fitness", "technology"}


@dataclass(frozen=True)
class Lead:
    company: str
    contact_name: str
    industry: str
    employee_count: int
    email_opens: int
    visited_pricing: bool
    requested_demo: bool
    days_since_activity: int
    pain_point: str
    source: str
    is_demo_data: bool


def _text(value: Any, field: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()[:limit]


def parse_lead(data: dict[str, Any]) -> Lead:
    """Validate untrusted JSON and return the permitted lead fields."""
    try:
        employees = int(data["employee_count"])
        opens = int(data["email_opens"])
        recency = int(data["days_since_activity"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("employee_count, email_opens, and days_since_activity must be integers") from exc
    if not 0 <= employees <= 1_000_000 or not 0 <= opens <= 10_000 or not 0 <= recency <= 3_650:
        raise ValueError("numeric values are outside the accepted range")
    return Lead(
        company=_text(data.get("company"), "company", 120),
        contact_name=_text(data.get("contact_name"), "contact_name", 120),
        industry=_text(data.get("industry"), "industry", 120).lower(),
        employee_count=employees,
        email_opens=opens,
        visited_pricing=bool(data.get("visited_pricing", False)),
        requested_demo=bool(data.get("requested_demo", False)),
        days_since_activity=recency,
        pain_point=_text(data.get("pain_point"), "pain_point", 600),
        source=_text(data.get("source"), "source", 120),
        is_demo_data=bool(data.get("is_demo_data", False)),
    )


def score_lead(lead: Lead) -> tuple[int, list[str]]:
    score, reasons = 0, []
    signals = [
        (lead.industry in INDUSTRY_FIT, 20, "Industry matches the target profile"),
        (lead.employee_count >= 200, 15, "Organization size suggests meaningful workflow scale"),
        (lead.visited_pricing, 20, "Visited the pricing page"),
        (lead.requested_demo, 25, "Requested a demo"),
        (lead.days_since_activity <= 7, 10, "Engaged within the last seven days"),
    ]
    for active, points, reason in signals:
        if active:
            score += points
            reasons.append(f"+{points}: {reason}")
    engagement = min(lead.email_opens * 2, 10)
    if engagement:
        score += engagement
        reasons.append(f"+{engagement}: Email engagement")
    return min(score, 100), reasons


def deterministic_result(lead: Lead) -> dict[str, Any]:
    score, reasons = score_lead(lead)
    tier = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
    next_action = (
        "Offer a 20-minute workflow discovery call within one business day."
        if tier == "High"
        else "Send a relevant use case and invite a reply with their current process."
        if tier == "Medium"
        else "Add to a value-led nurture sequence and monitor for new intent."
    )
    brief = (
        f"{lead.company} is a {lead.employee_count}-employee {lead.industry} organization acquired via "
        f"{lead.source}. Their stated challenge: {lead.pain_point}"
    )
    draft = (
        f"Hi {lead.contact_name},\n\nI noticed your interest in improving marketing operations. "
        f"You highlighted this challenge: {lead.pain_point} Teams often start by mapping the handoffs and repetitive steps. "
        "Would a short conversation next week be useful to compare approaches?\n\nBest,\nVinay"
    )
    return {"score": score, "tier": tier, "reasons": reasons, "brief": brief, "next_action": next_action, "outreach_draft": draft, "mode": "demo"}


def enhance_with_openai(lead: Lead, baseline: dict[str, Any]) -> dict[str, Any]:
    """Optionally improve narrative fields; deterministic score remains authoritative."""
    if os.getenv("ENABLE_AI", "false").lower() != "true" or not os.getenv("OPENAI_API_KEY"):
        return baseline
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            instructions=(
                "You are a revenue enablement analyst. Return JSON only with keys brief, next_action, "
                "and outreach_draft. Never invent facts. Keep the draft under 120 words and require human review."
            ),
            input=json.dumps({"lead": asdict(lead), "score": baseline["score"], "reasons": baseline["reasons"]}),
        )
        enhanced = json.loads(response.output_text)
        for key in ("brief", "next_action", "outreach_draft"):
            if isinstance(enhanced.get(key), str) and enhanced[key].strip():
                baseline[key] = enhanced[key].strip()
        baseline["mode"] = "ai-assisted"
    except Exception:
        baseline["mode"] = "demo-fallback"
    return baseline


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    lead = parse_lead(data)
    return enhance_with_openai(lead, deterministic_result(lead))
