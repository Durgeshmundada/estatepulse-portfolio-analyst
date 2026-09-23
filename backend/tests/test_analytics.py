from app.analytics import (
    filter_properties,
    format_inr,
    metrics,
    normalize_city,
    normalize_type,
    parse_inr,
    scenario_properties,
)


def sample_properties():
    return [
        {"id": "P001", "property_type": "RETAIL", "location": "Bandra West, Mumbai", "city": "Mumbai", "current_value_inr": 120_000_000, "annual_rent_inr": 7_200_000, "ownership_percent": 100, "occupancy_status": "TENANTED", "status": "ACTIVE"},
        {"id": "P002", "property_type": "OFFICE", "location": "Andheri East, Mumbai", "city": "Mumbai", "current_value_inr": 85_000_000, "annual_rent_inr": 0, "ownership_percent": 100, "occupancy_status": "VACANT", "status": "ACTIVE"},
        {"id": "P003", "property_type": "RETAIL", "location": "Lower Parel, Mumbai", "city": "Mumbai", "current_value_inr": 92_000_000, "annual_rent_inr": 6_000_000, "ownership_percent": 100, "occupancy_status": "TENANTED", "status": "ACTIVE"},
    ]


def test_money_parser_and_formatter():
    assert parse_inr("₹12 Cr") == 120_000_000
    assert parse_inr("75 lakh") == 7_500_000
    assert parse_inr("1.5 Cr") == 15_000_000
    assert format_inr(297_000_000) == "₹29.70 Cr"


def test_normalization_preserves_explicit_taxonomy():
    assert normalize_type("Commercial Office") == "OFFICE"
    assert normalize_type("Office") == "OFFICE"
    assert normalize_city("Alibaug, Maharashtra") == "Alibaug"


def test_u001_golden_metrics():
    data = metrics(sample_properties())
    assert data["owned_value_inr"] == 297_000_000
    assert data["annual_rent_inr"] == 13_200_000
    assert data["rental_yield_pct"] == 4.4444
    assert data["vacancy_pct"] == 33.33
    retail = metrics(filter_properties(sample_properties(), "retail"))
    assert retail["owned_value_inr"] == 212_000_000


def test_scenario_never_mutates_baseline():
    original = sample_properties()
    changed = scenario_properties(original, [{"op": "exclude", "property_ids": ["P001"]}])
    assert metrics(changed)["owned_value_inr"] == 177_000_000
    assert metrics(original)["owned_value_inr"] == 297_000_000

