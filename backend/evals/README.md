# EstatePulse evaluation harness

The harness runs the same planner and deterministic execution path used by chat without writing portfolio data.

Offline mode is deterministic, fast, and free. It evaluates the local planner, answer quality, numerical grounding, tenant isolation, scenarios, and write guardrails:

```powershell
cd backend
uv run python -m evals.run --mode offline
```

Live mode exercises normal routing, including Gemini for requests that do not use the local fast path. It requires `GEMINI_API_KEY` in `backend/.env` and reports model token usage when the API supplies it:

```powershell
uv run python -m evals.run --mode live --max-p95-ms 12000
```

Both modes write `evals/reports/latest.json`. The command exits with status 1 when the overall pass rate is below 95%, any guardrail or model-required case fails, or the optional p95 latency threshold is exceeded. Model-required cases distinguish a successful Gemini call from a correct local fallback. Use `--dataset`, `--output`, `--fail-under`, `--guardrail-fail-under`, and `--model-fail-under` to customize a run.

The GitHub Actions quality workflow runs the offline suite on every push and pull request and uploads its JSON report. Live mode stays outside routine CI because external quota and latency are not deterministic.

Each case can assert intent, required or forbidden response text, card types, returned property IDs, pending change payloads, scenario context, response length, and numerical grounding. Cases tagged `guardrail` contribute to the independent guardrail threshold.
