import argparse
import asyncio
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agent import _heuristic_plan, execute_node, run_agent
from app.analytics import normalize_city, normalize_type
from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_DATASET = Path(__file__).with_name("cases.json")
DEFAULT_REPORT = Path(__file__).parent / "reports" / "latest.json"
CLAIM_PATTERN = re.compile(
    r"₹\s*[0-9]+(?:\.[0-9]+)?\s*(?:Cr|crores?|lakh|lakhs?)|[0-9]+(?:\.[0-9]+)?%",
    re.IGNORECASE,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_fixture_data(data_dir: Path = PROJECT_DIR / "data") -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    users = {row["user_id"]: row["name"] for row in _read_csv(data_dir / "users.csv")}
    by_user: dict[str, list[dict[str, Any]]] = {user_id: [] for user_id in users}
    for row in _read_csv(data_dir / "properties.csv"):
        by_user[row["user_id"]].append({
            "id": row["property_id"],
            "property_type_raw": row["property_type"],
            "property_type": normalize_type(row["property_type"]) or "OTHER",
            "sub_type": row["sub_type"] or None,
            "location": row["location"],
            "city": normalize_city(row["location"]),
            "area_sqft": int(row["area_sqft"]) if row["area_sqft"] else None,
            "current_value_inr": int(row["current_estimated_value_inr"]),
            "purchase_price_inr": int(row["purchase_price_inr"]) if row["purchase_price_inr"] else None,
            "annual_rent_inr": int(row["annual_rent_inr"]) if row["annual_rent_inr"] else None,
            "occupancy_status": row["occupancy_status"].upper().replace("-", "_"),
            "tenant_status": row["tenant_status"].upper(),
            "ownership_percent": int(row["ownership_percent"]),
            "status": row["status"].upper(),
            "version": 1,
        })
    return users, by_user


def load_cases(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        cases = json.load(stream)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Eval case IDs must be unique")
    return cases


def _state(case: dict[str, Any], users: dict[str, str], properties: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    user_id = case["user_id"]
    return {
        "user_id": user_id,
        "user_name": users[user_id],
        "conversation_id": f"eval-{case['id']}",
        "request_id": f"eval-{case['id']}",
        "text": case["input"],
        "history": case.get("history", []),
        "context": case.get("context", {}),
        "properties": properties[user_id],
        "portfolio_version": 1,
        "events": [],
    }


def _card_property_ids(cards: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for card in cards:
        for item in card.get("items", []):
            if item.get("id"):
                ids.append(item["id"])
    return ids


def _claims(value: str) -> set[str]:
    return {" ".join(match.group(0).casefold().split()) for match in CLAIM_PATTERN.finditer(value)}


def _usage(result: dict[str, Any]) -> dict[str, int] | None:
    for event in result.get("events", []):
        usage = event.get("output", {}).get("usage")
        if usage:
            return {
                "prompt_tokens": int(usage.get("promptTokenCount", 0)),
                "output_tokens": int(usage.get("candidatesTokenCount", 0)),
                "total_tokens": int(usage.get("totalTokenCount", 0)),
            }
    return None


def score_case(case: dict[str, Any], result: dict[str, Any], latency_ms: int, mode: str) -> dict[str, Any]:
    expected = case["expect"]
    plan = result.get("plan", {})
    reply = result.get("reply_text", "")
    cards = result.get("cards", [])
    change = result.get("change_request")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, expected_value: Any, actual: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "expected": expected_value, "actual": actual})

    if "intent" in expected:
        check("intent", plan.get("intent") == expected["intent"], expected["intent"], plan.get("intent"))
    folded = reply.casefold()
    for phrase in expected.get("contains", []):
        check(f"contains:{phrase}", phrase.casefold() in folded, phrase, reply)
    combined = json.dumps({"reply": reply, "cards": cards}, ensure_ascii=False).casefold()
    for phrase in expected.get("not_contains", []):
        check(f"not_contains:{phrase}", phrase.casefold() not in combined, f"exclude {phrase}", combined)
    if "card_types" in expected:
        actual_types = [card.get("type") for card in cards]
        check(
            "card_types",
            all(card_type in actual_types for card_type in expected["card_types"]),
            expected["card_types"],
            actual_types,
        )
    property_ids = _card_property_ids(cards)
    if "property_ids" in expected:
        check("property_ids", set(property_ids) == set(expected["property_ids"]), expected["property_ids"], property_ids)
    if "property_ids_include" in expected:
        check(
            "property_ids_include",
            set(expected["property_ids_include"]).issubset(property_ids),
            expected["property_ids_include"],
            property_ids,
        )
    if "change_operation" in expected:
        check("change_operation", bool(change) and change.get("operation") == expected["change_operation"], expected["change_operation"], change)
    if "change_property_id" in expected:
        check("change_property_id", bool(change) and change.get("property_id") == expected["change_property_id"], expected["change_property_id"], change)
    if "change_payload" in expected:
        actual_payload = change.get("payload", {}) if change else {}
        wanted = expected["change_payload"]
        check("change_payload", all(actual_payload.get(key) == value for key, value in wanted.items()), wanted, actual_payload)
    if expected.get("no_change_request"):
        check("no_change_request", change is None, None, change)
    if "context_scenario" in expected:
        present = bool(result.get("context_update", {}).get("scenario"))
        check("context_scenario", present == expected["context_scenario"], expected["context_scenario"], present)
    if "max_reply_chars" in expected:
        check("max_reply_chars", len(reply) <= expected["max_reply_chars"], expected["max_reply_chars"], len(reply))
    if expected.get("grounded"):
        reply_claims = _claims(reply)
        evidence_claims = _claims(json.dumps(cards, ensure_ascii=False))
        for card in cards:
            for group in card.get("groups", []):
                if isinstance(group.get("share"), (int, float)):
                    evidence_claims.add(f"{group['share']:.2f}%")
        evidence_claims |= {" ".join(item.casefold().split()) for item in expected.get("grounding_allow", [])}
        unsupported = sorted(reply_claims - evidence_claims)
        check("grounded_numbers", not unsupported, sorted(reply_claims), unsupported)

    model_event = next(
        (event for event in result.get("events", []) if event.get("kind") == "MODEL"),
        None,
    )
    if mode in case.get("require_model_modes", []):
        model_succeeded = bool(
            model_event
            and model_event.get("success")
            and model_event.get("name") not in {"local_fast_path", "local_intent_fallback"}
        )
        check("model_success", model_succeeded, "successful external model call", model_event)
    if model_event:
        route = str(model_event.get("name"))
        if not model_event.get("success"):
            route += ":fallback"
    else:
        route = "offline_heuristic"
    return {
        "id": case["id"],
        "user_id": case["user_id"],
        "input": case["input"],
        "tags": case.get("tags", []),
        "passed": all(item["passed"] for item in checks),
        "latency_ms": latency_ms,
        "route": route,
        "intent": plan.get("intent"),
        "reply": reply,
        "card_types": [card.get("type") for card in cards],
        "usage": _usage(result),
        "checks": checks,
    }


async def evaluate_case(
    case: dict[str, Any],
    mode: str,
    users: dict[str, str],
    properties: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    state = _state(case, users, properties)
    started = perf_counter()
    if mode == "offline":
        plan = _heuristic_plan(state["text"], state["context"])
        result = execute_node({**state, "plan": plan.model_dump()})
        result["plan"] = plan.model_dump()
    else:
        result = await run_agent(state)
    latency_ms = int((perf_counter() - started) * 1000)
    return score_case(case, result, latency_ms, mode)


def _percent(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


async def run_evaluation(cases: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    users, properties = load_fixture_data()
    selected = [case for case in cases if mode in case.get("modes", ["offline", "live"])]
    results = []
    for case in selected:
        results.append(await evaluate_case(case, mode, users, properties))
    passed = sum(result["passed"] for result in results)
    intent_checks = [check for result in results for check in result["checks"] if check["name"] == "intent"]
    grounding_checks = [check for result in results for check in result["checks"] if check["name"] == "grounded_numbers"]
    model_checks = [check for result in results for check in result["checks"] if check["name"] == "model_success"]
    guardrail_results = [result for result in results if "guardrail" in result["tags"]]
    token_usage = [result["usage"] for result in results if result["usage"]]
    tag_counts: Counter[str] = Counter(tag for result in results for tag in result["tags"])
    tag_passes: Counter[str] = Counter(
        tag for result in results if result["passed"] for tag in result["tags"]
    )
    latencies = [result["latency_ms"] for result in results]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "model": get_settings().gemini_model if mode == "live" else "local_heuristic",
        "summary": {
            "cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": _percent(passed, len(results)),
            "intent_accuracy": _percent(sum(check["passed"] for check in intent_checks), len(intent_checks)),
            "groundedness_rate": _percent(sum(check["passed"] for check in grounding_checks), len(grounding_checks)),
            "model_success_rate": _percent(sum(check["passed"] for check in model_checks), len(model_checks)),
            "guardrail_pass_rate": _percent(sum(result["passed"] for result in guardrail_results), len(guardrail_results)),
            "latency_ms": {
                "mean": round(statistics.mean(latencies), 2) if latencies else 0,
                "p50": _percentile(latencies, 0.5),
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies, default=0),
            },
            "tokens": {
                "coverage_cases": len(token_usage),
                "prompt": sum(item["prompt_tokens"] for item in token_usage),
                "output": sum(item["output_tokens"] for item in token_usage),
                "total": sum(item["total_tokens"] for item in token_usage),
            },
            "by_tag": {
                tag: {"cases": count, "passed": tag_passes[tag], "pass_rate": _percent(tag_passes[tag], count)}
                for tag, count in sorted(tag_counts.items())
            },
        },
        "results": results,
    }


def _write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _print_report(report: dict[str, Any], output: Path) -> None:
    summary = report["summary"]
    print(f"EstatePulse evals · {report['mode']} · {summary['passed']}/{summary['cases']} passed")
    for result in report["results"]:
        marker = "PASS" if result["passed"] else "FAIL"
        print(f"{marker:4} {result['id']} ({result['latency_ms']} ms, {result['route']})")
        if not result["passed"]:
            for check in result["checks"]:
                if not check["passed"]:
                    print(f"     {check['name']}: expected {check['expected']!r}, got {check['actual']!r}")
    metrics = (
        f"pass={summary['pass_rate']:.1%} intent={summary['intent_accuracy']:.1%} "
        f"grounded={summary['groundedness_rate']:.1%} "
        f"guardrails={summary['guardrail_pass_rate']:.1%} "
    )
    if summary["model_success_rate"] is not None:
        metrics += f"model={summary['model_success_rate']:.1%} "
    metrics += f"p95={summary['latency_ms']['p95']} ms"
    print(metrics)
    print(f"report={output}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EstatePulse quality and guardrail evaluations")
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-under", type=float, default=0.95)
    parser.add_argument("--guardrail-fail-under", type=float, default=1.0)
    parser.add_argument("--model-fail-under", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    report = asyncio.run(run_evaluation(load_cases(args.dataset), args.mode))
    report["thresholds"] = {
        "pass_rate": args.fail_under,
        "guardrail_pass_rate": args.guardrail_fail_under,
        "model_success_rate": args.model_fail_under,
        "max_p95_ms": args.max_p95_ms,
    }
    _write_report(report, args.output)
    _print_report(report, args.output)
    summary = report["summary"]
    failed = summary["pass_rate"] < args.fail_under
    failed |= summary["guardrail_pass_rate"] < args.guardrail_fail_under
    if summary["model_success_rate"] is not None:
        failed |= summary["model_success_rate"] < args.model_fail_under
    if args.max_p95_ms is not None:
        failed |= summary["latency_ms"]["p95"] > args.max_p95_ms
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
