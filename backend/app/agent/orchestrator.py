"""Conversation orchestrator — the primary entry point for agent turns."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from collections.abc import AsyncIterator
import json
import time
from pathlib import Path

from app.agent.guardrails import (
    Confirm,
    Proceed,
    screen_input,
    screen_output,
)
from app.agent.llm import LLMClient, TurnContext
from app.agent.prompts import SYSTEM_PROMPT, compose_response_hints, render_facts_digest
from app.agent.session import Exchange, Session, SessionStore
from app.agent.conversation_frame import frame_from_session, render_frame_digest
from app.agent.conversation_memory import render_thread_digest
from app.agent.follow_up import plan_fallback_tools
from app.agent.tools import TOOLS, execute
from app.agent.airport_scope import resolve_airport_scope
from app.models.chat import ChatResponse, ToolResult
from app.models.request import ChatRequest
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Turn audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnAudit:
    conversation_id: str
    user_message: str
    tools_called: list[str]
    evidence_count: int
    evidence_origin: Literal["this_turn", "carried", "none"]
    injection_detected: bool
    number_warnings: list[str]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: dict[str, Any]

    def render(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"

class Orchestrator:
    def __init__(
        self,
        *,
        llm: LLMClient,
        analysis: AnalysisService,
        sessions: SessionStore,
    ) -> None:
        self._llm = llm
        self._analysis = analysis
        self._sessions = sessions

    async def turn(self, req: ChatRequest) -> ChatResponse:
        """Compat wrapper that drains the stream and returns the final ChatResponse."""
        response = None
        async for event in self.turn_stream(req):
            if event.event == "done":
                response = ChatResponse.model_validate(event.data)
        if response is None:
            raise RuntimeError("Stream finished without a 'done' event")
        return response

    async def turn_stream(self, req: ChatRequest) -> AsyncIterator[SseEvent]:
        session = self._sessions.get_or_create(req.conversation_id)
        lock = self._sessions.lock_for(req.conversation_id)

        async with lock:
            try:
                async for event in self._run_turn_stream(req, session):
                    yield event
            except Exception as e:
                logger.exception("Error in turn_stream")
                yield SseEvent(event="error", data={"detail": str(e)})

    async def _run_turn_stream(
        self, req: ChatRequest, session: Session
    ) -> AsyncIterator[SseEvent]:
        # 1. Input screening
        gate = screen_input(req.message, req.voice_confidence)

        if isinstance(gate, Confirm):
            resp = ChatResponse(
                message=gate.confirmation.prompt,
                airports=[],
                needs_confirmation=gate.confirmation,
            )
            yield SseEvent(event="done", data=resp.model_dump(mode="json"))
            return

        assert isinstance(gate, Proceed)

        # Start universe task early so it runs in parallel with LLM tool selection
        universe_task = asyncio.create_task(self._analysis.universe())

        # 2. Build Conversation Frame and Scope
        frame = frame_from_session(session)
        scope = resolve_airport_scope(req.message, session, frame)
        frame_digest = render_frame_digest(frame, scope)
        thread_digest = render_thread_digest(session)

        # 3. Referent resolution ("the first one", etc.) and scoped follow up hints
        hints = list(gate.hints)
        from app.agent.guardrails import resolve_mentions, build_follow_up_hints
        mentions = resolve_mentions(req.message)
        from app.agent.guardrails import Resolved

        mention_codes = (
            list(mentions.codes) if isinstance(mentions, Resolved) else []
        )
        carried_evidence = session.accumulated_evidence()
        
        follow_up_hints = build_follow_up_hints(req.message, frame, mentions, carried_evidence)
        hints.extend(follow_up_hints)
        from app.agent.capability import capability_hints

        hints.extend(capability_hints(req.message))

        if scope.source == "referent":
            hints.append(f"Resolved referents: {', '.join(scope.codes)}")

        # 4. Determine evidence carry-over
        facts_digest = render_facts_digest(carried_evidence)
        evidence_origin: Literal["this_turn", "carried", "none"] = (
            "carried" if carried_evidence else "none"
        )

        # 5. Build TurnContext for tool selection
        ctx = TurnContext(
            system_prompt=SYSTEM_PROMPT,
            history=session.history_messages(),
            conversation_frame=frame_digest,
            thread_digest=thread_digest,
            facts_digest=facts_digest,
            resolution_hints=hints,
            injection_note=gate.injection_note,
            user_message=req.message,
        )

        # 5. Tool selection
        yield SseEvent(event="phase", data={"step": "tool_select"})
        tool_mode = list(TOOLS.keys())
        calls = await self._llm.choose_tools(ctx, tool_mode)

        from app.agent.tool_coalesce import coalesce_tools
        from app.agent.tool_reconcile import reconcile_tool_calls

        calls = coalesce_tools(calls, frame, mentions)
        calls = reconcile_tool_calls(req.message, calls)

        from app.agent.display_evidence import message_wants_airport_comparison
        from app.agent.evidence_display import should_refresh_region_ranking
        from app.agent.llm import ToolCall

        if (
            should_refresh_region_ranking(req.message, scope)
            and scope.region
            and not message_wants_airport_comparison(req.message, scope)
            and not any(c.name == "rank_region" for c in calls)
        ):
            calls = [
                ToolCall(name="rank_region", arguments={"region": scope.region}),
                *calls,
            ]

        # 6. Execute tools concurrently
        new_evidence: list[ToolResult] = []
        evidence_origin: Literal["this_turn", "carried", "none"] = (
            "carried" if carried_evidence else "none"
        )
        if not calls:
            calls = plan_fallback_tools(req.message, session, frame, carried_evidence)

        if calls:
            yield SseEvent(event="phase", data={"step": "tools"})
            universe = await universe_task
            
            # Prefetch long_haul_reports for requested codes
            long_haul_reports = dict(universe.long_haul_reports)
            for call in calls:
                if call.name == "get_long_haul_percentage":
                    code = call.arguments.get("code")
                    if code and isinstance(code, str) and code not in long_haul_reports:
                        long_haul_reports[code] = self._analysis.long_haul_report(code)
            
            if long_haul_reports != universe.long_haul_reports:
                universe = universe.model_copy(update={"long_haul_reports": long_haul_reports})
                
            results = await asyncio.gather(
                *(
                    asyncio.to_thread(execute, call, universe)
                    for call in calls
                )
            )
            new_evidence = list(results)
            evidence_origin = "this_turn"

            from app.agent.display_evidence import upgrade_evidence_for_ui

            new_evidence = upgrade_evidence_for_ui(
                req.message, scope, new_evidence, universe
            )

        from app.agent.evidence_display import carried_evidence_for_turn

        if new_evidence:
            display_evidence = new_evidence
        else:
            display_evidence = carried_evidence_for_turn(
                req.message, scope, carried_evidence
            )
            if display_evidence:
                evidence_origin = "carried"

        context_evidence = display_evidence
        response_evidence = display_evidence

        # 7. Emit meta event before LLM response
        yield SseEvent(event="phase", data={"step": "compose"})
        
        # We need a partial ChatResponse for the meta event
        partial_resp = ChatResponse.assemble(
            "",
            response_evidence,
            evidence_origin,
            extra_warnings=None,
        )
        yield SseEvent(event="meta", data=partial_resp.model_dump(mode="json"))

        prose_hints = [*hints, *compose_response_hints(context_evidence)]
        response_ctx = TurnContext(
            system_prompt=SYSTEM_PROMPT,
            history=session.history_messages(),
            conversation_frame=frame_digest,
            thread_digest=thread_digest,
            facts_digest=render_facts_digest(context_evidence),
            resolution_hints=prose_hints,
            injection_note=gate.injection_note,
            user_message=req.message,
        )

        prose_chunks: list[str] = []
        async for chunk in self._llm.respond_stream(response_ctx, context_evidence):
            prose_chunks.append(chunk)
            yield SseEvent(event="delta", data={"text": chunk})

        prose = "".join(prose_chunks)

        # 8. Output screening
        cleaned_prose, extra_warnings = screen_output(prose, context_evidence)

        # 9. Assemble response
        response = ChatResponse.assemble(
            cleaned_prose,
            response_evidence,
            evidence_origin,
            extra_warnings=extra_warnings or None,
        )

        # 10. Append exchange to session
        session_evidence = new_evidence if new_evidence else display_evidence
        self._sessions.append(
            req.conversation_id,
            Exchange(
                user_message=req.message,
                reply=cleaned_prose,
                evidence=session_evidence,
            ),
        )

        # 11. Audit log
        audit = TurnAudit(
            conversation_id=req.conversation_id,
            user_message=req.message,
            tools_called=[c.name for c in calls],
            evidence_count=len(response_evidence),
            evidence_origin=evidence_origin,
            injection_detected=bool(gate.injection_note),
            number_warnings=extra_warnings,
        )
        logger.info("TurnAudit: %s", audit)

        yield SseEvent(event="done", data=response.model_dump(mode="json"))
