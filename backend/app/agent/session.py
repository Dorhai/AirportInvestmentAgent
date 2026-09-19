"""Conversation session state with TTL eviction."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.chat import ToolResult

_MAX_EXCHANGES = 6
_TTL_SECONDS = 3600.0


class Exchange(BaseModel):
    user_message: str
    reply: str
    evidence: list[ToolResult] = Field(default_factory=list)


class Session(BaseModel):
    conversation_id: str
    exchanges: deque[Exchange] = Field(
        default_factory=lambda: deque(maxlen=_MAX_EXCHANGES)
    )
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"arbitrary_types_allowed": True}

    @property
    def last_evidence(self) -> list[ToolResult]:
        """Most recent non-empty evidence list, or empty."""
        for ex in reversed(self.exchanges):
            if ex.evidence:
                return ex.evidence
        return []

    def accumulated_evidence(self) -> list[ToolResult]:
        """All tool results in the session, deduplicated by kind and airports/region (newest wins)."""
        deduped = {}
        for ex in self.exchanges:
            for ev in ex.evidence:
                key = (
                    ev.kind,
                    tuple(sorted(ev.airports)),
                    getattr(ev, "region", None) if ev.kind == "ranking" else None,
                    getattr(ev, "metric", None) if ev.kind == "ranking" else None,
                )
                deduped[key] = ev
        return list(deduped.values())

    @property
    def recent_airports(self) -> list[str]:
        """Airport codes derived from the last 2 non-empty evidence turns."""
        codes: list[str] = []
        ev_exchanges = [ex for ex in self.exchanges if ex.evidence]
        for ex in ev_exchanges[-2:]:
            for ev in ex.evidence:
                codes.extend(ev.airports)
        return list(dict.fromkeys(codes))

    def history_messages(self) -> list[dict[str, str]]:
        """Flatten exchanges into role/content dicts for LLM context."""
        msgs: list[dict[str, str]] = []
        for ex in self.exchanges:
            msgs.append({"role": "user", "content": ex.user_message})
            msgs.append({"role": "assistant", "content": ex.reply})
        return msgs


class SessionStore:
    """In-memory per-conversation store with TTL eviction and per-conversation locks."""

    def __init__(self, *, ttl_seconds: float = _TTL_SECONDS) -> None:
        self._sessions: dict[str, Session] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._ttl = ttl_seconds

    def get_or_create(self, conversation_id: str) -> Session:
        self._evict_stale()
        session = self._sessions.get(conversation_id)
        if session is None:
            session = Session(conversation_id=conversation_id)
            self._sessions[conversation_id] = session
        session.last_seen = datetime.now(timezone.utc)
        return session

    def lock_for(self, conversation_id: str) -> asyncio.Lock:
        """Return the per-conversation lock (creates one if needed)."""
        lock = self._locks.get(conversation_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[conversation_id] = lock
        return lock

    def append(self, conversation_id: str, exchange: Exchange) -> None:
        session = self._sessions.get(conversation_id)
        if session is not None:
            session.exchanges.append(exchange)

    def _evict_stale(self) -> None:
        now = datetime.now(timezone.utc)
        stale = [
            cid
            for cid, s in self._sessions.items()
            if (now - s.last_seen).total_seconds() > self._ttl
        ]
        for cid in stale:
            self._sessions.pop(cid, None)
            self._locks.pop(cid, None)

    def evict(self, conversation_id: str) -> None:
        self._sessions.pop(conversation_id, None)
        self._locks.pop(conversation_id, None)
