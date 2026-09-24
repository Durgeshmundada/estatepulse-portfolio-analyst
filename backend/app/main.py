import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .agent import close_agent_client, run_agent
from .analytics import format_inr, metrics, normalize_city, property_dict, summary_card
from .config import get_settings
from .db import Base, engine, get_db
from .models import (
    AgentEvent,
    AttentionFlag,
    ChangeRequest,
    Conversation,
    Message,
    Property,
    User,
    utcnow,
)
from .schemas import ConfirmRequest, ConversationCreate, MessageCreate, SessionCreate
from .seed import seed

settings = get_settings()
serializer = URLSafeTimedSerializer(settings.session_secret, salt="estatepulse-session")


def as_user(token: str | None = Cookie(default=None, alias="estatepulse_session"), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(401, "Select a demo portfolio first")
    try:
        user_id = serializer.loads(token, max_age=86_400)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(401, "Your demo session expired") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "Unknown demo portfolio")
    return user


def as_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(403, "Invalid admin access token")


def message_dto(item: Message) -> dict[str, Any]:
    return {"id": item.id, "role": item.role.lower(), "text": item.text, "cards": item.cards_json or [], "created_at": item.created_at.isoformat(), "request_id": item.request_id}


def conversation_dto(item: Conversation, open_flags: int = 0) -> dict[str, Any]:
    return {"id": item.id, "title": item.title, "user_id": item.user_id, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(), "needs_attention": open_flags > 0}


def properties_for(db: Session, user_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(Property).where(Property.user_id == user_id).order_by(Property.id)).all()
    return [property_dict(row) for row in rows]


def owned_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return conversation


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.seed_data_dir.exists():
        seed(settings.seed_data_dir)
    yield
    await close_agent_client()


app = FastAPI(title="EstatePulse Portfolio Analyst", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "ok", "ai_mode": "gemini" if settings.gemini_api_key else "local-fallback"}


@app.get("/api/demo/users")
def demo_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return {"items": [{"id": u.id, "name": u.name, "city": u.city, "preferences": u.preferences} for u in users]}


@app.post("/api/session")
def create_session(payload: SessionCreate, response: Response, db: Session = Depends(get_db)):
    if payload.access_code != settings.demo_access_code:
        raise HTTPException(403, "Incorrect demo access code")
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(404, "Demo user not found")
    response.set_cookie("estatepulse_session", serializer.dumps(user.id), httponly=True, samesite="lax", secure=settings.app_env == "production", max_age=86_400)
    return {"user": {"id": user.id, "name": user.name, "city": user.city, "preferences": user.preferences}}


@app.get("/api/session")
def get_session(user: User = Depends(as_user)):
    return {"user": {"id": user.id, "name": user.name, "city": user.city, "preferences": user.preferences}}


@app.delete("/api/session", status_code=204)
def delete_session(response: Response):
    response.delete_cookie("estatepulse_session")


@app.get("/api/portfolio")
def get_portfolio(user: User = Depends(as_user), db: Session = Depends(get_db)):
    properties = properties_for(db, user.id)
    data = metrics(properties)
    return {"portfolio_version": user.portfolio_version, "summary": data, "card": summary_card(data), "properties": properties}


@app.get("/api/conversations")
def list_conversations(user: User = Depends(as_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())).all()
    return {"items": [conversation_dto(row) for row in rows]}


@app.post("/api/conversations", status_code=201)
def create_conversation(_: ConversationCreate, user: User = Depends(as_user), db: Session = Depends(get_db)):
    item = Conversation(id=str(uuid4()), user_id=user.id)
    db.add(item)
    db.commit()
    return conversation_dto(item)


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user: User = Depends(as_user), db: Session = Depends(get_db)):
    conversation = owned_conversation(db, conversation_id, user.id)
    messages = db.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at, Message.id)).all()
    pending = db.scalar(select(ChangeRequest).where(ChangeRequest.conversation_id == conversation.id, ChangeRequest.status == "PENDING").order_by(ChangeRequest.created_at.desc()))
    return {**conversation_dto(conversation), "messages": [message_dto(m) for m in messages], "context": conversation.context_json, "pending_change": pending.id if pending else None}


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    user: User = Depends(as_user),
    db: Session = Depends(get_db),
):
    conversation = owned_conversation(db, conversation_id, user.id)
    db.execute(delete(AttentionFlag).where(AttentionFlag.conversation_id == conversation.id))
    db.execute(delete(AgentEvent).where(AgentEvent.conversation_id == conversation.id))
    db.execute(delete(ChangeRequest).where(ChangeRequest.conversation_id == conversation.id))
    db.execute(delete(Message).where(Message.conversation_id == conversation.id))
    db.delete(conversation)
    db.commit()


async def process_message(
    payload: MessageCreate,
    conversation_id: str,
    user: User,
    db: Session,
) -> dict[str, Any]:
    started = perf_counter()
    conversation = owned_conversation(db, conversation_id, user.id)
    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.request_id == payload.request_id,
            Message.role == "ASSISTANT",
        )
    )
    if existing:
        return {"request_id": payload.request_id, "conversation_id": conversation.id, "message": message_dto(existing), "server_ms": 0, "replayed": True}
    user_message = Message(id=str(uuid4()), conversation_id=conversation.id, role="USER", request_id=payload.request_id, text=payload.text, cards_json=[])
    db.add(user_message)
    if conversation.title == "New conversation":
        conversation.title = payload.text.strip()[:80]
    conversation.updated_at = utcnow()
    db.commit()
    properties = properties_for(db, user.id)
    history_rows = db.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(12)).all()
    history = [{"role": m.role.lower(), "text": m.text} for m in reversed(history_rows)]
    try:
        result = await run_agent({
            "user_id": user.id, "user_name": user.name,
            "conversation_id": conversation.id, "request_id": payload.request_id,
            "text": payload.text, "history": history, "context": conversation.context_json or {},
            "properties": properties, "portfolio_version": user.portfolio_version, "events": [],
        })
    except Exception as exc:
        flag = AttentionFlag(id=str(uuid4()), conversation_id=conversation.id, reason="AGENT_FAILURE", detail=type(exc).__name__)
        assistant = Message(id=str(uuid4()), conversation_id=conversation.id, role="ASSISTANT", request_id=payload.request_id, text="I couldn't complete that analysis. Please try again.", cards_json=[])
        db.add_all([flag, assistant])
        db.commit()
        raise HTTPException(503, "Analysis temporarily unavailable") from exc
    cards = list(result.get("cards", []))
    if result.get("change_request"):
        spec = result["change_request"]
        change = ChangeRequest(
            id=str(uuid4()), conversation_id=conversation.id, user_id=user.id,
            operation=spec["operation"], property_id=spec["property_id"], payload_json=spec["payload"],
            before_json=spec["before"], expected_version=spec["expected_version"], status="PENDING",
        )
        db.add(change)
        after = dict(spec["before"] or {})
        after.update(spec["payload"])
        cards.append({"type": "change_review", "title": "Review actual portfolio change", "change_id": change.id, "operation": change.operation, "before": spec["before"], "after": after, "status": "PENDING"})
    assistant = Message(id=str(uuid4()), conversation_id=conversation.id, role="ASSISTANT", request_id=payload.request_id, text=result["reply_text"], cards_json=cards)
    conversation.context_json = result.get("context_update", conversation.context_json)
    conversation.updated_at = utcnow()
    db.add(assistant)
    if result.get("attention"):
        db.add(AttentionFlag(id=str(uuid4()), conversation_id=conversation.id, reason=result["attention"], detail="Requested during conversation"))
    for event in result.get("events", []):
        db.add(AgentEvent(id=str(uuid4()), conversation_id=conversation.id, request_id=payload.request_id, kind=event["kind"], name=event["name"], input_json=event.get("input", {}), output_json=event.get("output", {}), duration_ms=event.get("duration_ms", 0), success=event.get("success", True), error=event.get("error")))
    db.commit()
    elapsed = int((perf_counter() - started) * 1000)
    return {"request_id": payload.request_id, "conversation_id": conversation.id, "message": message_dto(assistant), "server_ms": elapsed, "replayed": False}


@app.post("/api/conversations/{conversation_id}/messages")
async def send_message(
    payload: MessageCreate,
    conversation_id: str,
    user: User = Depends(as_user),
    db: Session = Depends(get_db),
):
    return await process_message(payload, conversation_id, user, db)


def stream_line(event: str, **data: Any) -> str:
    return json.dumps({"type": event, **data}, ensure_ascii=False) + "\n"


def response_chunks(text: str, words_per_chunk: int = 4) -> list[str]:
    words = re.findall(r"\S+\s*", text)
    return ["".join(words[index:index + words_per_chunk]) for index in range(0, len(words), words_per_chunk)]


@app.post("/api/conversations/{conversation_id}/messages/stream")
async def stream_message(
    payload: MessageCreate,
    conversation_id: str,
    user: User = Depends(as_user),
    db: Session = Depends(get_db),
):
    owned_conversation(db, conversation_id, user.id)

    async def generate():
        yield stream_line("status", text="Reading your portfolio…")
        try:
            result = await process_message(payload, conversation_id, user, db)
        except HTTPException as exc:
            yield stream_line("error", detail=str(exc.detail))
            return
        except Exception:
            yield stream_line("error", detail="Analysis temporarily unavailable")
            return
        for chunk in response_chunks(result["message"]["text"]):
            yield stream_line("delta", text=chunk)
            await asyncio.sleep(0.012)
        yield stream_line("done", **result)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/changes/{change_id}/confirm")
def confirm_change(payload: ConfirmRequest, change_id: str, user: User = Depends(as_user), db: Session = Depends(get_db)):
    change = db.scalar(select(ChangeRequest).where(ChangeRequest.id == change_id, ChangeRequest.user_id == user.id))
    if not change:
        raise HTTPException(404, "Change request not found")
    if change.status == "CONFIRMED":
        receipts = db.scalars(
            select(Message).where(
                Message.conversation_id == change.conversation_id,
                Message.role == "ASSISTANT",
            ).order_by(Message.created_at.desc())
        ).all()
        receipt = next(
            (
                message for message in receipts
                if any(card.get("change_id") == change.id for card in (message.cards_json or []))
            ),
            None,
        )
        if not receipt:
            raise HTTPException(409, "This change was already confirmed")
        return {"message": message_dto(receipt), "replayed": True}
    if change.status != "PENDING":
        raise HTTPException(409, "This change is no longer pending")
    before = change.before_json
    if change.operation == "UPDATE":
        prop = db.scalar(select(Property).where(Property.id == change.property_id, Property.user_id == user.id))
        if not prop or prop.version != change.expected_version:
            change.status = "STALE"
            db.commit()
            raise HTTPException(409, "The property changed since this review was created")
        for key, value in change.payload_json.items():
            setattr(prop, key, value)
        prop.version += 1
        prop.updated_at = utcnow()
    else:
        data = change.payload_json
        prop = Property(
            id=f"P-{uuid4().hex[:8].upper()}", user_id=user.id,
            property_type_raw=data["property_type_raw"], property_type=data["property_type"],
            sub_type=data.get("sub_type"), location=data["location"], city_normalized=normalize_city(data["location"]),
            area_sqft=data.get("area_sqft"), current_value_inr=data["current_value_inr"],
            purchase_price_inr=data.get("purchase_price_inr"), annual_rent_inr=data.get("annual_rent_inr"),
            ownership_percent=data.get("ownership_percent", 100), occupancy_status=data.get("occupancy_status", "UNKNOWN"),
            tenant_status=data.get("tenant_status", "UNKNOWN"), status=data.get("status", "ACTIVE"),
        )
        db.add(prop)
    user.portfolio_version += 1
    change.status = "CONFIRMED"
    change.confirmed_at = utcnow()
    conversation = owned_conversation(db, change.conversation_id, user.id)
    context = dict(conversation.context_json or {})
    context.pop("scenario", None)
    conversation.context_json = context
    db.flush()
    total = metrics(properties_for(db, user.id))["owned_value_inr"]
    card = {"type": "change_receipt", "title": "Actual portfolio updated", "change_id": change.id, "operation": change.operation, "property_id": prop.id, "before": before, "after": property_dict(prop), "portfolio_value": format_inr(total)}
    user_msg = Message(id=str(uuid4()), conversation_id=conversation.id, role="USER", request_id=payload.request_id, text="Confirm change", cards_json=[])
    assistant = Message(id=str(uuid4()), conversation_id=conversation.id, role="ASSISTANT", request_id=payload.request_id, text=f"Saved. Your actual portfolio is now worth {format_inr(total)}.", cards_json=[card])
    db.add_all([user_msg, assistant, AgentEvent(id=str(uuid4()), conversation_id=conversation.id, request_id=payload.request_id, kind="WRITE", name=change.operation.lower(), input_json={"change_id": change.id}, output_json={"property_id": prop.id, "portfolio_value_inr": total}, duration_ms=0, success=True)])
    conversation.updated_at = utcnow()
    db.commit()
    return {"message": message_dto(assistant), "replayed": False}


@app.post("/api/changes/{change_id}/cancel")
def cancel_change(change_id: str, user: User = Depends(as_user), db: Session = Depends(get_db)):
    change = db.scalar(select(ChangeRequest).where(ChangeRequest.id == change_id, ChangeRequest.user_id == user.id))
    if not change:
        raise HTTPException(404, "Change request not found")
    if change.status != "PENDING":
        raise HTTPException(409, "This change can no longer be cancelled")
    change.status = "CANCELLED"
    db.commit()
    return {"change_id": change.id, "status": change.status}


@app.get("/api/admin/overview", dependencies=[Depends(as_admin)])
def admin_overview(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    conversations = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()
    flags = db.scalars(select(AttentionFlag).where(AttentionFlag.resolved.is_(False)).order_by(AttentionFlag.created_at.desc())).all()
    durations = db.scalars(select(AgentEvent.duration_ms).where(AgentEvent.kind == "MODEL", AgentEvent.success.is_(True))).all()
    sorted_durations = sorted(durations)
    p50 = sorted_durations[len(sorted_durations) // 2] if sorted_durations else None
    return {
        "metrics": {"users": len(users), "conversations": len(conversations), "open_flags": len(flags), "model_p50_ms": p50},
        "users": [{"id": u.id, "name": u.name, "city": u.city, "property_count": db.scalar(select(func.count()).select_from(Property).where(Property.user_id == u.id)), "conversation_count": db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == u.id))} for u in users],
        "conversations": [{**conversation_dto(c, db.scalar(select(func.count()).select_from(AttentionFlag).where(AttentionFlag.conversation_id == c.id, AttentionFlag.resolved.is_(False)))), "user_name": db.get(User, c.user_id).name} for c in conversations],
        "flags": [{"id": f.id, "conversation_id": f.conversation_id, "reason": f.reason, "detail": f.detail, "created_at": f.created_at.isoformat()} for f in flags],
    }


@app.get("/api/admin/conversations/{conversation_id}", dependencies=[Depends(as_admin)])
def admin_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    messages = db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)).all()
    events = db.scalars(select(AgentEvent).where(AgentEvent.conversation_id == conversation_id).order_by(AgentEvent.created_at, AgentEvent.id)).all()
    return {"conversation": conversation_dto(conversation), "messages": [message_dto(m) for m in messages], "events": [{"id": e.id, "request_id": e.request_id, "kind": e.kind, "name": e.name, "duration_ms": e.duration_ms, "success": e.success, "input": e.input_json, "output": e.output_json, "error": e.error, "created_at": e.created_at.isoformat()} for e in events]}


@app.post("/api/admin/flags/{flag_id}/resolve", dependencies=[Depends(as_admin)])
def resolve_flag(flag_id: str, db: Session = Depends(get_db)):
    flag = db.get(AttentionFlag, flag_id)
    if not flag:
        raise HTTPException(404, "Flag not found")
    flag.resolved = True
    flag.resolved_at = datetime.now(UTC)
    db.commit()
    return {"id": flag.id, "resolved": True}


static_dir = settings.static_dir.resolve()
if static_dir.exists():
    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = static_dir / path
        if path and candidate.is_file() and static_dir in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
