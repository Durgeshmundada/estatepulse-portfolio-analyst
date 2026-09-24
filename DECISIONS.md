# Engineering Decision Log

## One bounded agent

Use one LangGraph workflow with Gemini as an intent planner and deterministic execution nodes. The portfolio shares one compact domain and does not justify agent hand-offs. This keeps latency, tool selection, and failures inspectable.

## Deterministic portfolio facts

Python services retrieve, filter, and calculate every portfolio value. Gemini interprets language but does not produce authoritative arithmetic. Typed display templates keep numerical responses reproducible and testable.

## Relational storage

Use SQLAlchemy with SQLite for the demo. Exact ownership filters, constraints, transactions, and audited updates suit relational storage; vector search does not. SQLite limits horizontal writes, so PostgreSQL is the production migration path.

## No RAG or vector database

The authoritative source is twelve structured records. Embedding those rows would make exact aggregation harder without adding useful knowledge. Add RAG only if sourced documents become a real requirement.

## Incremental response streaming

Use newline-delimited JSON so the API can emit progress, text deltas, and a final persisted message with cards over one response. Keep the original JSON endpoint for compatibility. The final event is the database-backed source of truth, so streaming does not weaken retries or conversation history.

## Snapshot scenarios

Represent scenarios as ordered operations over copied portfolio data stored in conversation context. This creates a clear boundary between actual and hypothetical state. Large portfolios would store versioned operations and execute them through indexed queries.

## Confirmation before persistence

The agent creates reviewable change requests. A separate endpoint performs the transaction after user confirmation. This costs one interaction but prevents an intent-classification error from immediately modifying a holding.

## Bounded conversation memory

Persist the full transcript while supplying recent turns and structured focus to the model. Current facts are retrieved again from the database. This prevents token growth and stale numerical memory.

## Database-backed observability

Store model and deterministic execution events with request IDs, duration, safe inputs/outputs, and status. This directly powers the business dashboard without enterprise tracing infrastructure.

## Dual response contract

Keep the validated JSON endpoint for compatibility and add NDJSON streaming for the chat interface. Streaming sends progress and text deltas, then finishes with the same persisted message and cards returned by the JSON endpoint.

## React/Vite frontend

Use a responsive React SPA because the product has two interactive views and no SEO requirement. Vite keeps local and production builds compact. Server rendering would add a runtime boundary without assignment value.

## Gemini API

Use Gemini 2.5 Flash through its structured JSON REST interface because the user will provide a Gemini key and the assignment accepts an equivalent gateway. A deterministic fallback supports local development; health reports the active mode.

## Render single-service deployment

Build React into the FastAPI image and mount a persistent Render disk for SQLite. One service simplifies reviewer access. The deployment runs one worker; PostgreSQL is required before horizontal scaling.
