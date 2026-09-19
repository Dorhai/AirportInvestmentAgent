from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.session import Session


def render_thread_digest(session: "Session") -> str:
    if not session.exchanges:
        return ""

    lines = []
    questions = []
    for ex in session.exchanges:
        questions.append(ex.user_message)
    
    if questions:
        lines.append("Prior questions in this thread:")
        for q in questions:
            lines.append(f"- {q}")

    from app.agent.conversation_frame import frame_from_session
    frame = frame_from_session(session)
    if frame.airports:
        lines.append(f"\nAirports discussed: {', '.join(frame.airports)}")
    if frame.region:
        lines.append(f"Active region: {frame.region}")
        
    return "\n".join(lines)