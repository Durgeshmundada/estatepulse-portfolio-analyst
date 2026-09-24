from app.agent import _heuristic_plan, execute_node


def properties():
    return [
        {"id": "P001", "property_type": "RETAIL", "location": "Bandra West, Mumbai", "city": "Mumbai", "area_sqft": 5200, "current_value_inr": 120_000_000, "annual_rent_inr": 7_200_000, "ownership_percent": 100, "occupancy_status": "TENANTED", "status": "ACTIVE", "version": 1},
        {"id": "P003", "property_type": "RETAIL", "location": "Lower Parel, Mumbai", "city": "Mumbai", "area_sqft": 3100, "current_value_inr": 92_000_000, "annual_rent_inr": 6_000_000, "ownership_percent": 100, "occupancy_status": "TENANTED", "status": "ACTIVE", "version": 1},
    ]


def state(plan):
    return {"user_id": "U001", "user_name": "Rahul Mehta", "conversation_id": "C1", "request_id": "R1", "text": "", "history": [], "context": {}, "properties": properties(), "portfolio_version": 1, "plan": plan.model_dump(), "events": []}


def test_greetings_are_natural_and_personal():
    for text in ["Hey", "Hello!", "Good morning"]:
        plan = _heuristic_plan(text, {})
        assert plan.intent == "greeting"
        result = execute_node(state(plan))
        assert "Rahul" in result["reply_text"]
        assert "portfolio value" in result["reply_text"]


def test_yield_ranking_explains_yield_and_absolute_rent():
    plan = _heuristic_plan("Which property has the highest rental yield?", {})
    result = execute_node(state(plan))
    assert "6.52%" in result["reply_text"]
    assert "earns more absolute rent" in result["reply_text"]
    card = result["cards"][0]
    assert card["variant"] == "ranking"
    assert card["items"][0]["metric"] == "6.52% gross yield"

