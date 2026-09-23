import re
import unicodedata
from collections import defaultdict
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TYPE_MAP = {
    "retail": "RETAIL",
    "office": "OFFICE",
    "commercial office": "OFFICE",
    "residential": "RESIDENTIAL",
}


def normalize_type(value: str | None) -> str | None:
    if not value:
        return None
    key = " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())
    if key == "commercial":
        return "COMMERCIAL"
    return TYPE_MAP.get(key, key.upper())


def normalize_city(location: str) -> str | None:
    text = unicodedata.normalize("NFKC", location).casefold()
    aliases = {
        "mumbai": ("mumbai", "bombay"),
        "bengaluru": ("bengaluru", "bangalore"),
        "gurugram": ("gurugram", "gurgaon"),
        "noida": ("noida",),
        "alibaug": ("alibaug",),
    }
    found = [city.title() for city, names in aliases.items() if any(n in text for n in names)]
    return found[0] if len(found) == 1 else None


def parse_inr(value: str | float | Decimal) -> int:
    if isinstance(value, bool):
        raise TypeError("Invalid money value")
    if isinstance(value, (int, Decimal)):
        amount = Decimal(value)
    elif isinstance(value, float):
        amount = Decimal(str(value))
    else:
        text = unicodedata.normalize("NFKC", value).strip().casefold()
        text = re.sub(r"^(₹|inr|rs\.?)[ ]*", "", text).strip()
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]{1,2})?|[0-9]{1,3}(?:,[0-9]{2})*(?:,[0-9]{3})|[0-9]{1,3}(?:,[0-9]{3})+)[ ]*(crores?|cr|lakhs?|lacs?|l)?", text)
        if not match:
            raise ValueError("Use a value such as ₹12 Cr, 75 lakh, or 120000000")
        number, suffix = match.groups()
        amount = Decimal(number.replace(",", ""))
        if suffix in {"cr", "crore", "crores"}:
            amount *= 10_000_000
        elif suffix in {"l", "lakh", "lakhs", "lac", "lacs"}:
            amount *= 100_000
    if amount < 0 or amount > Decimal(1000000000000):
        raise ValueError("Money value is outside the supported range")
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_inr(value: int | Decimal | None) -> str:
    if value is None:
        return "Unknown"
    amount = Decimal(value)
    if amount >= 10_000_000:
        return f"₹{amount / Decimal(10_000_000):.2f} Cr"
    if amount >= 100_000:
        return f"₹{amount / Decimal(100_000):.2f} lakh"
    return f"₹{int(amount):,}"


def property_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "property_type_raw": row.property_type_raw,
        "property_type": row.property_type,
        "sub_type": row.sub_type,
        "location": row.location,
        "city": row.city_normalized,
        "area_sqft": row.area_sqft,
        "current_value_inr": row.current_value_inr,
        "annual_rent_inr": row.annual_rent_inr,
        "purchase_price_inr": row.purchase_price_inr,
        "occupancy_status": row.occupancy_status,
        "tenant_status": row.tenant_status,
        "ownership_percent": row.ownership_percent,
        "status": row.status,
        "version": row.version,
    }


def filter_properties(
    properties: list[dict[str, Any]], property_type: str | None = None, location: str | None = None
) -> list[dict[str, Any]]:
    normalized_type = normalize_type(property_type)
    result = []
    for item in properties:
        if item.get("status", "ACTIVE") != "ACTIVE":
            continue
        if normalized_type == "COMMERCIAL" and item["property_type"] not in {"RETAIL", "OFFICE"}:
            continue
        if normalized_type and normalized_type != "COMMERCIAL" and item["property_type"] != normalized_type:
            continue
        if location and location.casefold() not in item["location"].casefold() and location.casefold() not in (item.get("city") or "").casefold():
            continue
        result.append(item)
    return result


def metrics(properties: list[dict[str, Any]]) -> dict[str, Any]:
    active = [p for p in properties if p.get("status", "ACTIVE") == "ACTIVE"]
    gross_value = sum(Decimal(p["current_value_inr"]) for p in active)
    owned_value = sum(
        Decimal(p["current_value_inr"]) * Decimal(p.get("ownership_percent", 100)) / 100
        for p in active
    )
    known_rents = [p for p in active if p.get("annual_rent_inr") is not None]
    owned_rent = sum(
        Decimal(p["annual_rent_inr"]) * Decimal(p.get("ownership_percent", 100)) / 100
        for p in known_rents
    )
    yield_pct = (owned_rent / owned_value * 100) if owned_value and len(known_rents) == len(active) else None
    known_occ = [p for p in active if p.get("occupancy_status") != "UNKNOWN"]
    physical = [p for p in known_occ if p.get("occupancy_status") in {"TENANTED", "SELF_OCCUPIED"}]
    tenanted = [p for p in known_occ if p.get("occupancy_status") == "TENANTED"]
    vacant = [p for p in known_occ if p.get("occupancy_status") == "VACANT"]
    by_type: dict[str, Decimal] = defaultdict(Decimal)
    by_city: dict[str, Decimal] = defaultdict(Decimal)
    for p in active:
        owned = Decimal(p["current_value_inr"]) * Decimal(p.get("ownership_percent", 100)) / 100
        by_type[p["property_type"]] += owned
        by_city[p.get("city") or "Unknown"] += owned
    pct = lambda count: float(Decimal(count) / Decimal(len(known_occ)) * 100) if known_occ else None
    return {
        "property_count": len(active),
        "gross_value_inr": int(gross_value),
        "owned_value_inr": int(owned_value),
        "annual_rent_inr": int(owned_rent),
        "rent_complete": len(known_rents) == len(active),
        "rental_yield_pct": round(float(yield_pct), 4) if yield_pct is not None else None,
        "physical_occupancy_pct": round(pct(len(physical)), 2) if known_occ else None,
        "tenanted_pct": round(pct(len(tenanted)), 2) if known_occ else None,
        "vacancy_pct": round(pct(len(vacant)), 2) if known_occ else None,
        "by_type": {k: int(v) for k, v in sorted(by_type.items())},
        "by_city": {k: int(v) for k, v in sorted(by_city.items())},
    }


def rank(properties: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    def value(p):
        if field == "rental_yield":
            current = p["current_value_inr"]
            rent = p.get("annual_rent_inr")
            return (Decimal(rent) / Decimal(current) * 100) if rent is not None and current else None
        return Decimal(p.get(field) or 0)

    rows = [(p, value(p)) for p in properties]
    rows = [(p, v) for p, v in rows if v is not None]
    rows.sort(key=lambda pair: (-pair[1], pair[0]["id"]))
    return [{**p, "metric_value": round(float(v), 4)} for p, v in rows]


def scenario_properties(
    properties: list[dict[str, Any]], operations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = deepcopy(properties)
    for operation in operations:
        if operation["op"] == "exclude":
            targets = set(operation["property_ids"])
            result = [p for p in result if p["id"] not in targets]
        elif operation["op"] == "scale_value":
            targets = set(operation["property_ids"])
            factor = Decimal(1) + Decimal(str(operation["change_pct"])) / 100
            for item in result:
                if item["id"] in targets:
                    item["current_value_inr"] = int(Decimal(item["current_value_inr"]) * factor)
    return result


def summary_card(data: dict[str, Any], label: str = "Actual portfolio") -> dict[str, Any]:
    return {
        "type": "summary",
        "title": label,
        "metrics": [
            {"label": "Portfolio value", "value": format_inr(data["owned_value_inr"])},
            {"label": "Annual rent", "value": format_inr(data["annual_rent_inr"])},
            {"label": "Gross yield", "value": f'{data["rental_yield_pct"]:.2f}%' if data["rental_yield_pct"] is not None else "Unknown"},
            {"label": "Properties", "value": str(data["property_count"])},
        ],
        "rent_complete": data["rent_complete"],
    }
