"""
Chat screen — the main conversation interface.

Layout (flex column, full viewport height below header):
  ┌──────────────────────────────────────────┐
  │ HEADER (sticky)                           │
  ├──────────────────────────────────────────┤
  │ EMERGENCY BANNER (conditional)            │
  ├──────────────────────────────────────────┤
  │                                          │
  │  scrollable message area  (flex: 1)      │
  │                                          │
  ├──────────────────────────────────────────┤
  │ INPUT BAR  (pinned)                      │
  ├──────────────────────────────────────────┤
  │ FOOTER LINKS                             │
  └──────────────────────────────────────────┘
"""

import html as _html
import uuid
from nicegui import ui, app

from components.header import create_header
from components.chat_bubble import add_chat_bubble, add_typing_indicator
from services.session import session_manager
from services.conversation import conversation_service
from services.safety import safety_service
from models.message import Message
from models.report import Report
from services.conversation import HARM_CATEGORIES, HARM_CATEGORIES_SIMPLE, _SIMPLE_TO_FULL


# ─── utilities ────────────────────────────────────────────────────────────────

def _scroll_bottom() -> None:
    """Scroll the NiceGUI scroll-area to the bottom."""
    ui.run_javascript(
        "setTimeout(function(){"
        "  var el = document.querySelector('.q-scrollarea__container');"
        "  if (el) el.scrollTop = el.scrollHeight + 9999;"
        "}, 80);"
    )


def _resolve_session():
    """Return (session_id, session), creating a new session only if needed."""
    sid = app.storage.user.get("session_id")
    session = session_manager.get_session(sid) if sid else None
    if session is None:
        sid = str(uuid.uuid4())
        app.storage.user["session_id"] = sid
        session = session_manager.create_session(sid)
    return sid, session


# ─── main page function ───────────────────────────────────────────────────────

def show() -> None:
    """Render the full chat interface."""
    create_header(show_exit=True)

    sid, session = _resolve_session()

    # Per-render mutable state (never shared across sessions)
    ctrl = {"sending": False}

    # ── outer column fills viewport below the sticky header ──────────────────
    with ui.column().style(
        "width: 100%; max-width: 640px; margin: 0 auto; "
        "height: calc(100dvh - 62px); "   # 62 px ≈ header height
        "display: flex; flex-direction: column; overflow: hidden;"
    ):

        # ── emergency / human-support banner ─────────────────────────────────
        if session.state == "HUMAN_SUPPORT":
            ui.html(
                '<div class="emergency-banner" style="margin: 8px 12px 0; flex-shrink: 0;">'
                '👤 <strong>Human support requested.</strong> '
                'A safeguarding officer will review this conversation. '
                'You can also call <strong>116</strong> (Child Helpline) at any time.'
                '</div>'
            )

        # ── scrollable messages column ────────────────────────────────────────
        with ui.scroll_area().style("flex: 1; min-height: 0; width: 100%;"):
            msg_col = ui.column().style(
                "width: 100%; padding: 12px 6px 16px; gap: 0;"
            )

        # Replay stored messages (browser refresh / language change)
        with msg_col:
            for msg in session.messages:
                add_chat_bubble(msg_col, msg.role, msg.text)

        # ── input bar ─────────────────────────────────────────────────────────
        with ui.row().style(
            "padding: 8px 10px; background: #ffffff; "
            "border-top: 1px solid #e2e8f0; "
            "width: 100%; gap: 8px; align-items: flex-end; flex-shrink: 0;"
        ):
            inp = (
                ui.textarea(placeholder="Type your message…")
                .style(
                    "flex: 1; font-family: Nunito, Arial, sans-serif; "
                    "font-size: 0.95rem; resize: none; max-height: 110px;"
                )
                .props("outlined dense rows=1 auto-grow")
            )
            # Enter sends (Shift+Enter = newline via auto-grow)
            inp.on(
                "keydown.enter.prevent",
                lambda: _do_send(sid, ctrl, msg_col, inp),
            )

            ui.button("Send", on_click=lambda: _do_send(sid, ctrl, msg_col, inp)).style(
                "background-color: #006463; color: white; border-radius: 10px; "
                "font-weight: 700; padding: 8px 20px; min-height: 40px; flex-shrink: 0;"
            ).props("no-caps")

        # ── footer utility links ──────────────────────────────────────────────
        with ui.row().style(
            "padding: 5px 8px; background: #f7fafa; "
            "border-top: 1px solid #e2e8f0; flex-shrink: 0; flex-wrap: wrap; gap: 2px;"
        ):
            _footer_btn("🆘 Human Help", "/help")
            _footer_btn("🌍 Language", "/language")
            _footer_btn("📋 My Report", "/report")

    # ── initial greeting (only on fresh session) ──────────────────────────────
    if not session.messages:
        ui.timer(0.05, lambda: _send_greeting(sid, ctrl, msg_col, inp), once=True)
    else:
        _scroll_bottom()


def _footer_btn(label: str, route: str) -> None:
    ui.button(label, on_click=lambda: ui.navigate.to(route)).props("flat no-caps").style(
        "color: #006463; font-size: 0.78rem; font-weight: 700; padding: 3px 6px; min-height: 28px;"
    )


# ─── send pipeline ────────────────────────────────────────────────────────────

def _do_send(sid: str, ctrl: dict, msg_col, inp) -> None:
    """Validate then dispatch."""
    if ctrl["sending"]:
        return
    text = (inp.value or "").strip()
    if not text:
        return
    inp.value = ""
    _handle_send(sid, ctrl, msg_col, inp, text)


def _handle_send(sid: str, ctrl: dict, msg_col, inp, text: str) -> None:
    """Full pipeline: urgency → child bubble → typing → reply → persist."""
    ctrl["sending"] = True

    session = session_manager.get_session(sid)
    lang = session.language if session else "en"

    # 1. Urgency check — always runs regardless of state
    urgency = safety_service.check_urgency(text)
    if urgency["urgent"]:
        guidance = safety_service.get_emergency_guidance(lang)
        safe_msg = _html.escape(guidance["message"])
        with msg_col:
            ui.html(
                f'<div class="emergency-banner critical" style="margin: 6px 4px;">'
                f'🚨 {safe_msg}'
                f'</div>'
            )

    # 2. Render child bubble + persist
    add_chat_bubble(msg_col, "child", text)
    if session:
        session_manager.update_session(
            sid,
            messages=list(session.messages) + [Message(role="child", text=text)],
        )
    _scroll_bottom()

    # 3. Typing indicator
    with msg_col:
        typing_el = add_typing_indicator(msg_col)

    # 4. Get reply from conversation service
    reply, quick_replies = conversation_service.process_message(sid, text)

    # 5. Remove typing indicator
    try:
        typing_el.delete()
    except Exception:
        pass

    # 6. Handle navigation sentinels
    if reply == "__navigate_report__":
        _ensure_report_built(sid)
        ui.navigate.to("/report")
        ctrl["sending"] = False
        return
    if reply == "__navigate_help__":
        session_manager.update_session(sid, state="HUMAN_SUPPORT")
        ui.navigate.to("/help")
        ctrl["sending"] = False
        return

    # 7. If state just became REPORT_REVIEW, build the report object
    current_session = session_manager.get_session(sid)
    if current_session and current_session.state == "REPORT_REVIEW":
        _ensure_report_built(sid)

    # 8. Render bot bubble + quick replies
    add_chat_bubble(msg_col, "bot", reply)
    if quick_replies:
        _render_quick_replies(msg_col, quick_replies, sid, ctrl, inp)

    # 9. Persist bot message
    fresh = session_manager.get_session(sid)
    if fresh:
        session_manager.update_session(
            sid,
            messages=list(fresh.messages) + [
                Message(role="bot", text=reply, quick_replies=quick_replies)
            ],
        )

    _scroll_bottom()
    ctrl["sending"] = False


def _send_greeting(sid: str, ctrl: dict, msg_col, inp) -> None:
    """Called once on a fresh session to trigger the opening bot message."""
    reply, quick_replies = conversation_service.process_message(sid, "__init__")
    add_chat_bubble(msg_col, "bot", reply)
    if quick_replies:
        _render_quick_replies(msg_col, quick_replies, sid, ctrl, inp)
    session = session_manager.get_session(sid)
    if session:
        session_manager.update_session(
            sid,
            messages=[Message(role="bot", text=reply, quick_replies=quick_replies)],
        )
    _scroll_bottom()


# ─── quick replies ────────────────────────────────────────────────────────────

def _render_quick_replies(msg_col, quick_replies: list[str], sid, ctrl, inp) -> None:
    """Render pill buttons; clicking sends the pill text as a message."""
    with msg_col:
        with ui.element("div").classes("quick-replies-row"):
            for qr in quick_replies:
                _make_pill(msg_col, qr, sid, ctrl, inp)


def _make_pill(msg_col, qr_text: str, sid, ctrl, inp) -> None:
    """Create one quick-reply pill with its own click handler."""

    def on_click():
        _handle_send(sid, ctrl, msg_col, inp, qr_text)

    ui.html(
        f'<button class="qr-pill">{_html.escape(qr_text)}</button>'
    ).on("click", on_click)


# ─── report builder ───────────────────────────────────────────────────────────

def _ensure_report_built(sid: str) -> None:
    """Construct a Report from conversation history if one doesn't exist yet."""
    session = session_manager.get_session(sid)
    if session is None or session.current_report is not None:
        return

    harm_category = session.harm_category or "Unspecified concern"
    description = "No description provided yet."
    severity = "medium"

    # Use the last substantive child message as description
    child_texts = [
        m.text for m in session.messages
        if m.role == "child"
        and m.text not in HARM_CATEGORIES
        and m.text not in HARM_CATEGORIES_SIMPLE
        and m.text not in _SIMPLE_TO_FULL
    ]
    if child_texts:
        description = child_texts[-1]

    lower_desc = description.lower()
    if any(w in lower_desc for w in ("danger", "hurt", "kill", "dead", "abuse", "hit", "beat")):
        severity = "high"
    if any(w in lower_desc for w in ("naked", "nude", "picture", "grooming", "exploit")):
        severity = "high"

    report = Report(
        harm_category=harm_category,
        description=description,
        language=session.language,
        age_bracket=session.age_bracket,
        severity=severity,
    )
    session_manager.update_session(sid, current_report=report)
