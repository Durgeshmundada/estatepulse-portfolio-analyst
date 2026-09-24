import json
import re
import time
from decimal import Decimal
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from .analytics import (
    filter_properties,
    format_inr,
    metrics,
    normalize_type,
    parse_inr,
    rank,
    scenario_properties,
    summary_card,
)
from .config import get_settings
from .schemas import AgentPlan


class GraphState(TypedDict, total=False):
    user_id: str
    user_name: str
    conversation_id: str
    request_id: str
    text: str
    history: list[dict[str, str]]
    context: dict[str, Any]
    properties: list[dict[str, Any]]
    portfolio_version: int
    plan: dict[str, Any]
    reply_text: str
    cards: list[dict[str, Any]]
    context_update: dict[str, Any]
    change_request: dict[str, Any] | None
    attention: str | None
    events: list[dict[str, Any]]


SYSTEM_PROMPT = """You are the intent planner for ASTRA, a real-estate portfolio analyst.
Return only a JSON object matching the supplied schema. Portfolio facts and arithmetic are done by code.
Classify the latest user request. Preserve clear follow-up context. Treat what-if, exclude, sell hypothetically,
or value change percentages as scenarios. Treat add/update/save as proposed actual changes requiring confirmation.
Commercial means retail plus office. 'Performing better' means highest gross rental yield unless specified.
Never choose another user. If historical appreciation/cost/dates are requested, use unsupported.
Extract a property reference as the phrase the user used, never invent an ID. Monetary value_inr must be whole INR.
Use greeting for greetings and casual check-ins, thanks for appreciation or farewells, and help when the user
asks what ASTRA can do. Never classify those conversational messages as unsupported.
"""


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(AgentPlan.model_fields["intent"].annotation.__args__)},
        "property_type": {"type": ["string", "null"]},
        "second_property_type": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "property_ref": {"type": ["string", "null"]},
        "value_inr": {"type": ["integer", "null"]},
        "value_change_pct": {"type": ["number", "null"]},
        "area_sqft": {"type": ["integer", "null"]},
        "sub_type": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
    },
    "required": list(AgentPlan.model_fields),
    "additionalProperties": False,
}


def _extract_money(text: str) -> int | None:
    patterns = [
        r"(?:₹|inr|rs\.?)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:crores?|cr|lakhs?|lacs?|l))",
        r"(?:worth|value(?:\s+to)?|at)\s+(?:₹|inr|rs\.?)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return parse_inr(match.group(1))
            except ValueError:
                return None
    return None


def _heuristic_plan(text: str, context: dict[str, Any]) -> AgentPlan:
    lower = text.casefold().strip()
    property_type = next((t for t in ["retail", "residential", "office", "commercial"] if t in lower), None)
    money = _extract_money(text)
    area_match = re.search(r"([0-9][0-9,]*)\s*(?:sq\.?\s*ft|sqft)", lower)
    area = int(area_match.group(1).replace(",", "")) if area_match else None
    pct_match = re.search(r"(?:falls?|drops?|decreases?|increases?|rises?|changes?)\s+(?:by\s+)?(-?\d+(?:\.\d+)?)\s*%", lower)
    pct = float(pct_match.group(1)) if pct_match else None
    if pct is not None and any(word in lower for word in ["fall", "drop", "decrease"]):
        pct = -abs(pct)
    location = next((x for x in ["Bandra", "Mumbai", "Andheri", "Lower Parel", "Worli", "Alibaug", "Gurugram", "Noida", "Whitefield", "Koramangala", "Indiranagar", "Delhi"] if x.casefold() in lower), None)
    if re.fullmatch(r"(?:hi|hey|hello|good\s+(?:morning|afternoon|evening)|howdy)[!. ]*", lower):
        return AgentPlan(intent="greeting")
    if any(x in lower for x in ["thank you", "thanks", "that helps", "bye", "goodbye"]):
        return AgentPlan(intent="thanks")
    if any(x in lower for x in ["what can you do", "how can you help", "help me", "your capabilities"]):
        return AgentPlan(intent="help")
    if any(x in lower for x in ["human", "person", "support team"]):
        return AgentPlan(intent="human_help")
    if any(x in lower for x in ["back to actual", "clear scenario", "reset scenario"]):
        return AgentPlan(intent="scenario_reset")
    if any(x in lower for x in ["what if", "hypothetical", "exclude", "without", "sell"]):
        intent = "scenario_value_change" if pct is not None else "scenario_exclude"
        return AgentPlan(intent=intent, property_type=property_type, location=location, property_ref=location, value_change_pct=pct)
    if any(x in lower for x in ["add ", "i own", "new property"]):
        return AgentPlan(intent="propose_add", property_type=property_type, location=location, property_ref=location, value_inr=money, area_sqft=area)
    if any(x in lower for x in ["update", "change", "set "]) and (money is not None or "property" in lower):
        return AgentPlan(intent="propose_update", property_type=property_type, location=location, property_ref=location, value_inr=money)
    if any(x in lower for x in ["appreciat", "since purchase", "historical", "last five years", "cagr", "irr"]):
        return AgentPlan(intent="unsupported", reason="Historical purchase values and dates are unavailable.")
    if "highest" in lower or "most rent" in lower or "performing" in lower or "better" in lower:
        return AgentPlan(intent="highest_yield" if "yield" in lower or "perform" in lower else "highest_rent", property_type=property_type)
    if "compare" in lower or "versus" in lower or " vs " in lower:
        types = [t for t in ["retail", "residential", "office", "commercial"] if t in lower]
        return AgentPlan(intent="compare", property_type=types[0] if types else context.get("last_type"), second_property_type=types[1] if len(types) > 1 else None)
    if any(x in lower for x in ["how much", "exposure", "percentage", "share"]):
        return AgentPlan(intent="exposure", property_type=property_type or context.get("last_type"), location=location)
    if property_type or location or any(x in lower for x in ["show", "which properties", "tell me about"]):
        return AgentPlan(intent="list", property_type=property_type or context.get("last_type"), location=location)
    return AgentPlan(intent="summary")


async def _gemini_plan(state: GraphState) -> tuple[AgentPlan, dict[str, Any]]:
    settings = get_settings()
    started = time.perf_counter()
    if settings.app_env == "test" or not settings.gemini_api_key:
        plan = _heuristic_plan(state["text"], state.get("context", {}))
        return plan, {"kind": "MODEL", "name": "local_intent_fallback", "duration_ms": int((time.perf_counter() - started) * 1000), "success": True, "input": {"text": state["text"]}, "output": plan.model_dump()}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    context = {
        "conversation_context": state.get("context", {}),
        "recent_history": state.get("history", [])[-6:],
        "available_properties": [
            {"id": p["id"], "type": p["property_type"], "location": p["location"]}
            for p in state["properties"][:50]
        ],
        "latest_user_message": state["text"],
    }
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(context)}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
            "responseJsonSchema": PLAN_SCHEMA,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, params={"key": settings.gemini_api_key}, json=payload)
            response.raise_for_status()
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        plan = AgentPlan.model_validate_json(raw)
        event = {"kind": "MODEL", "name": settings.gemini_model, "duration_ms": int((time.perf_counter() - started) * 1000), "success": True, "input": {"text": state["text"]}, "output": plan.model_dump()}
        return plan, event
    except Exception as exc:
        plan = _heuristic_plan(state["text"], state.get("context", {}))
        event = {"kind": "MODEL", "name": settings.gemini_model, "duration_ms": int((time.perf_counter() - started) * 1000), "success": False, "error": type(exc).__name__, "input": {"text": state["text"]}, "output": {"fallback": plan.model_dump()}}
        return plan, event


async def plan_node(state: GraphState) -> dict[str, Any]:
    plan, event = await _gemini_plan(state)
    return {"plan": plan.model_dump(), "events": [event]}


def _resolve(properties: list[dict[str, Any]], plan: AgentPlan) -> list[dict[str, Any]]:
    candidates = filter_properties(properties, plan.property_type, plan.location)
    if plan.property_ref and not plan.location:
        ref = plan.property_ref.casefold()
        candidates = [p for p in candidates if ref in p["location"].casefold() or ref == p["id"].casefold()]
    return candidates


def _gross_yield(item: dict[str, Any]) -> float | None:
    rent = item.get("annual_rent_inr")
    value = item.get("current_value_inr")
    if rent is None or not value:
        return None
    return round(float(Decimal(rent) / Decimal(value) * 100), 2)


def _property_card(
    items: list[dict[str, Any]], title: str, *, ranking_metric: str | None = None
) -> dict[str, Any]:
    rows = []
    for item in items:
        yield_pct = _gross_yield(item)
        metric = None
        if ranking_metric == "rental_yield":
            metric = f"{yield_pct:.2f}% gross yield" if yield_pct is not None else "Yield unknown"
        elif ranking_metric == "annual_rent_inr":
            metric = f"{format_inr(item.get('annual_rent_inr'))} annual rent"
        rows.append({
            "id": item["id"], "type": item["property_type"].title(),
            "location": item["location"],
            "area": f'{item["area_sqft"]:,} sq ft' if item.get("area_sqft") else "Unknown",
            "value": format_inr(item["current_value_inr"]),
            "rent": format_inr(item.get("annual_rent_inr")),
            "occupancy": item["occupancy_status"].replace("_", " ").title(),
            "metric": metric,
        })
    return {
        "type": "properties", "title": title, "variant": "ranking" if ranking_metric else "matches",
        "items": rows,
    }


def execute_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    plan = AgentPlan.model_validate(state["plan"])
    actual = state["properties"]
    context = dict(state.get("context", {}))
    cards: list[dict[str, Any]] = []
    text = ""
    change_request = None
    attention = None
    active_scenario = context.get("scenario")
    current = actual
    if active_scenario and active_scenario.get("baseline_version") == state["portfolio_version"]:
        current = scenario_properties(actual, active_scenario.get("operations", []))

    if plan.intent == "greeting":
        first_name = state.get("user_name", "").split(" ")[0]
        name = f", {first_name}" if first_name else ""
        text = (
            f"Hello{name}! What would you like to explore today—portfolio value, "
            "rental performance, exposure, or a what-if scenario?"
        )
    elif plan.intent == "thanks":
        text = "You're welcome. Ask me anytime if you'd like to compare properties or model another scenario."
    elif plan.intent == "help":
        text = (
            "I can summarise your portfolio, find or compare properties, calculate value exposure "
            "and gross rental yield, model temporary what-if scenarios, and prepare reviewed property updates."
        )
    elif plan.intent == "summary":
        data = metrics(current)
        label = "Hypothetical portfolio" if active_scenario else "Actual portfolio"
        cards = [summary_card(data, label)]
        text = f"Your {label.lower()} is worth {format_inr(data['owned_value_inr'])} across {data['property_count']} properties, with {format_inr(data['annual_rent_inr'])} in known annual rent."
    elif plan.intent == "list":
        items = filter_properties(current, plan.property_type, plan.location)
        cards = [_property_card(items, "Matching properties")]
        text = f"I found {len(items)} matching {'hypothetical ' if active_scenario else ''}properties."
        context["last_property_ids"] = [p["id"] for p in items]
        if plan.property_type:
            context["last_type"] = plan.property_type
    elif plan.intent == "exposure":
        group = filter_properties(current, plan.property_type, plan.location)
        total_metrics, group_metrics = metrics(current), metrics(group)
        denominator = total_metrics["owned_value_inr"]
        share = group_metrics["owned_value_inr"] / denominator * 100 if denominator else None
        label = plan.property_type or plan.location or "Selected"
        text = f"{label.title()} represents {format_inr(group_metrics['owned_value_inr'])}, or {share:.2f}% of your {'hypothetical ' if active_scenario else ''}portfolio value." if share is not None else "The exposure percentage is undefined because the portfolio value is zero."
        cards = [{"type": "comparison", "title": f"{label.title()} exposure", "groups": [
            {"label": label.title(), "value": format_inr(group_metrics["owned_value_inr"]), "share": round(share or 0, 2)},
            {"label": "Rest of portfolio", "value": format_inr(denominator - group_metrics["owned_value_inr"]), "share": round(100 - (share or 0), 2)},
        ]}]
        if plan.property_type:
            context["last_type"] = plan.property_type
    elif plan.intent in {"highest_rent", "highest_yield"}:
        items = filter_properties(current, plan.property_type, plan.location)
        field = "rental_yield" if plan.intent == "highest_yield" else "annual_rent_inr"
        ranked = rank(items, field)
        if not ranked:
            text = "I don't have enough data to rank those properties."
        else:
            winner = ranked[0]
            if field == "rental_yield":
                text = (
                    f"{winner['id']} in {winner['location']} leads on gross rental yield at "
                    f"{winner['metric_value']:.2f}%, generating {format_inr(winner['annual_rent_inr'])} "
                    f"a year on a current value of {format_inr(winner['current_value_inr'])}."
                )
                if len(ranked) > 1:
                    runner_up = ranked[1]
                    if (runner_up.get("annual_rent_inr") or 0) > (winner.get("annual_rent_inr") or 0):
                        text += (
                            f" {runner_up['id']} earns more absolute rent at "
                            f"{format_inr(runner_up['annual_rent_inr'])}, but its yield is lower at "
                            f"{runner_up['metric_value']:.2f}%."
                        )
            else:
                yield_pct = _gross_yield(winner)
                text = (
                    f"{winner['id']} in {winner['location']} generates the highest annual rent at "
                    f"{format_inr(winner['annual_rent_inr'])}"
                    + (f", equivalent to a {yield_pct:.2f}% gross yield." if yield_pct is not None else ".")
                )
            cards = [_property_card(ranked[:3], "Performance ranking", ranking_metric=field)]
            context["last_property_ids"] = [p["id"] for p in ranked[:3]]
            context["single_property_id"] = winner["id"]
    elif plan.intent == "compare":
        first = filter_properties(current, plan.property_type)
        second = filter_properties(current, plan.second_property_type)
        if not plan.property_type or not plan.second_property_type:
            text = "Which two property categories would you like me to compare?"
        else:
            groups = []
            for label, items in [(plan.property_type, first), (plan.second_property_type, second)]:
                data = metrics(items)
                groups.append({"label": label.title(), "value": format_inr(data["owned_value_inr"]), "rent": format_inr(data["annual_rent_inr"]), "yield": f'{data["rental_yield_pct"]:.2f}%' if data["rental_yield_pct"] is not None else "Unknown"})
            cards = [{"type": "comparison", "title": "Portfolio comparison", "groups": groups}]
            text = f"Here is your {plan.property_type} versus {plan.second_property_type} comparison using ownership-adjusted value and gross rental yield."
            context["last_type"] = plan.property_type
    elif plan.intent in {"scenario_exclude", "scenario_value_change"}:
        targets = _resolve(actual, plan)
        if not targets and context.get("single_property_id"):
            targets = [p for p in actual if p["id"] == context["single_property_id"]]
        if len(targets) != 1 and plan.property_ref and not plan.location:
            text = "I couldn't identify one property confidently. Please name its location or property ID."
        elif not targets:
            text = "I couldn't find a matching property in this portfolio."
        else:
            operations = list(active_scenario.get("operations", [])) if active_scenario else []
            if plan.intent == "scenario_exclude":
                operations.append({"op": "exclude", "property_ids": [p["id"] for p in targets]})
            elif plan.value_change_pct is None:
                text = "What percentage change should I apply to that property's value?"
                return {"reply_text": text, "cards": [], "context_update": context, "events": state.get("events", [])}
            else:
                operations.append({"op": "scale_value", "property_ids": [p["id"] for p in targets], "change_pct": plan.value_change_pct})
            changed = scenario_properties(actual, operations)
            before, after = metrics(actual), metrics(changed)
            context["scenario"] = {"baseline_version": state["portfolio_version"], "operations": operations}
            text = f"Hypothetically, your portfolio value changes from {format_inr(before['owned_value_inr'])} to {format_inr(after['owned_value_inr'])}. Your actual portfolio is unchanged."
            cards = [{"type": "scenario", "title": "Hypothetical scenario", "baseline": format_inr(before["owned_value_inr"]), "scenario": format_inr(after["owned_value_inr"]), "delta": format_inr(after["owned_value_inr"] - before["owned_value_inr"]), "operations": operations}]
    elif plan.intent == "scenario_reset":
        context.pop("scenario", None)
        data = metrics(actual)
        text = f"You're back to your actual portfolio, currently worth {format_inr(data['owned_value_inr'])}."
        cards = [summary_card(data)]
    elif plan.intent == "propose_add":
        missing = [name for name, value in [("property type", plan.property_type), ("location", plan.location), ("current value", plan.value_inr)] if value is None]
        if missing:
            text = "Please provide the " + ", ".join(missing) + " so I can prepare the property for review."
        else:
            payload = {"property_type_raw": plan.property_type.title(), "property_type": normalize_type(plan.property_type), "location": plan.location, "area_sqft": plan.area_sqft, "current_value_inr": plan.value_inr, "annual_rent_inr": None, "ownership_percent": 100, "occupancy_status": "UNKNOWN", "tenant_status": "UNKNOWN", "status": "ACTIVE"}
            change_request = {"operation": "ADD", "payload": payload, "property_id": None, "before": None, "expected_version": None}
            text = "I've prepared this property for review. Nothing has been saved yet."
    elif plan.intent == "propose_update":
        targets = _resolve(actual, plan)
        if not targets and context.get("single_property_id"):
            targets = [p for p in actual if p["id"] == context["single_property_id"]]
        if len(targets) != 1:
            text = "Please identify one property by location or property ID before I prepare the update."
        elif plan.value_inr is None:
            text = "What should the property's new estimated value be?"
        else:
            before = targets[0]
            payload = {"current_value_inr": plan.value_inr}
            change_request = {"operation": "UPDATE", "payload": payload, "property_id": before["id"], "before": before, "expected_version": before["version"]}
            text = "I've prepared the value update for review. Nothing has been saved yet."
    elif plan.intent == "human_help":
        text = "I've marked this conversation for the business team to review."
        attention = "HUMAN_REQUESTED"
    else:
        if plan.reason and any(
            word in plan.reason.casefold()
            for word in ["history", "historical", "purchase", "date", "appreciation", "cagr", "irr"]
        ):
            text = (
                "I can't calculate historical appreciation from this portfolio because purchase prices "
                "and valuation dates are unavailable. I can still analyse current value, rent, yield, and exposure."
            )
        else:
            text = (
                "I couldn't map that request to the available portfolio data. I can help with current values, "
                "rent and yield, exposure, comparisons, what-if scenarios, and reviewed property updates."
            )

    event = {"kind": "TOOL", "name": plan.intent, "duration_ms": int((time.perf_counter() - started) * 1000), "success": True, "input": plan.model_dump(), "output": {"text": text, "card_types": [c["type"] for c in cards]}}
    return {"reply_text": text, "cards": cards, "context_update": context, "change_request": change_request, "attention": attention, "events": state.get("events", []) + [event]}


builder = StateGraph(GraphState)
builder.add_node("plan", plan_node)
builder.add_node("execute", execute_node)
builder.add_edge(START, "plan")
builder.add_edge("plan", "execute")
builder.add_edge("execute", END)
graph = builder.compile()


async def run_agent(state: GraphState) -> GraphState:
    return await graph.ainvoke(state)
