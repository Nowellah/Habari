import html
import uuid
from nicegui import ui, app
from components.header import create_header
from components.chat_bubble import add_chat_bubble
from services.session import session_manager
from services.conversation import conversation_service
from services.safety import safety_service
from models.message import Message


def show() -> None:
    """Main chat interface."""
    create_header(show_exit=True)

    # Resolve or create session
    session_id = app.storage.user.get("session_id")
    if session_id:
        session = session_manager.get_session(session_id)
    else:
        session = None

    if session is None:
        session_id = str(uuid.uuid4())
        app.storage.user["session_id"] = session_id
        session = session_manager.create_session(session_id)

    # Mutable state (per-page-load, not per-session)
    state = {"sending": False}

    # Layout: full-height flex column
    with ui.column().style(
        "width: 100%; max-width: 640px; margin: 0 auto; "
        "height: calc(100vh - 64px); display: flex; flex-direction: column;"
    ):
        # Scrollable messages area
        scroll = ui.scroll_area().style(
            "flex: 1; overflow-y: auto; padding: 8px 12px;"
        )
        messages_container = scroll

        # Render existing messages
        with messages_container:
            for msg in session.messages:
                add_chat_bubble(messages_container, msg.role, msg.text)
                if msg.role == "bot" and msg.quick_replies:
                    _render_quick_replies(
                        messages_container, msg.quick_replies,
                        lambda t, sid=session_id, st=state, mc=messages_container: handle_send(
                            sid, st, mc, inp_ref, t
                        ),
                    )

        # Input row pinned at bottom
        with ui.row().style(
            "padding: 8px 12px; background: #fff; border-top: 1px solid #ddd; "
            "width: 100%; box-sizing: border-box; gap: 8px; align-items: center;"
        ):
            inp_ref = ui.input(placeholder="Type your message here…").style(
                "flex: 1;"
            ).props("outlined dense")

            ui.button(
                "Send",
                on_click=lambda: handle_send(session_id, state, messages_container, inp_ref),
            ).style(
                "background-color: #006463; color: white; border-radius: 8px; "
                "font-weight: 600; padding: 6px 16px;"
            )

        # Footer links
        with ui.row().style(
            "padding: 6px 12px; gap: 16px; background: #FFF9F0; "
            "border-top: 1px solid #eee;"
        ):
            ui.button(
                "Get Human Help",
                on_click=lambda: ui.navigate.to("/help"),
            ).props("flat").style("color: #006463; font-size: 0.85rem;")
            ui.button(
                "Change Language",
                on_click=lambda: ui.navigate.to("/language"),
            ).props("flat").style("color: #006463; font-size: 0.85rem;")

    # Send initial greeting if no messages yet
    if not session.messages:
        _init_greeting(session_id, messages_container, inp_ref, state)


def _init_greeting(session_id, messages_container, inp_ref, state):
    reply, quick_replies = conversation_service.process_message(session_id, "__init__")
    _add_and_store_bot_message(session_id, messages_container, reply, quick_replies, inp_ref, state)


def handle_send(session_id, state, messages_container, inp_ref, text: str = None):
    """Handle sending a message from the user."""
    if state["sending"]:
        return
    msg_text = text if text is not None else inp_ref.value
    if not msg_text or not msg_text.strip():
        return

    state["sending"] = True
    inp_ref.value = ""

    # Urgency check
    urgency = safety_service.check_urgency(msg_text)
    if urgency["urgent"]:
        guidance = safety_service.get_emergency_guidance(
            session_manager.get_session(session_id).language
            if session_manager.get_session(session_id) else "en"
        )
        escaped_msg = html.escape(guidance["message"])
        with messages_container:
            ui.html(f'<div class="emergency-banner">{escaped_msg}</div>')

    # Add child bubble
    add_chat_bubble(messages_container, "child", msg_text)

    # Store child message in session
    session = session_manager.get_session(session_id)
    if session:
        updated_msgs = list(session.messages) + [Message(role="child", text=msg_text)]
        session_manager.update_session(session_id, messages=updated_msgs)

    # Show spinner
    spinner_row = None
    with messages_container:
        spinner_row = ui.row().style("padding: 4px 12px;")
        with spinner_row:
            ui.spinner(size="sm").style("color: #006463;")

    # Get reply
    reply, quick_replies = conversation_service.process_message(session_id, msg_text)

    # Remove spinner
    if spinner_row:
        spinner_row.delete()

    _add_and_store_bot_message(session_id, messages_container, reply, quick_replies, inp_ref, state)

    # Scroll to bottom
    ui.run_javascript(
        'var el = document.querySelector(".q-scroll-area__container"); '
        'if(el) el.scrollTop = 999999;'
    )

    state["sending"] = False


def _add_and_store_bot_message(session_id, messages_container, reply, quick_replies, inp_ref, state):
    """Add bot bubble and quick replies; persist to session."""
    add_chat_bubble(messages_container, "bot", reply)

    if quick_replies:
        _render_quick_replies(
            messages_container,
            quick_replies,
            lambda t, sid=session_id, st=state, mc=messages_container: handle_send(
                sid, st, mc, inp_ref, t
            ),
        )

    # Store bot message in session
    session = session_manager.get_session(session_id)
    if session:
        updated_msgs = list(session.messages) + [
            Message(role="bot", text=reply, quick_replies=quick_replies)
        ]
        session_manager.update_session(session_id, messages=updated_msgs)


def _render_quick_replies(container, quick_replies: list[str], on_click_factory) -> None:
    """Render quick reply pill buttons."""
    with container:
        with ui.row().style("flex-wrap: wrap; padding: 4px 0;"):
            for qr in quick_replies:
                qr_text = qr  # capture

                def make_handler(t):
                    return lambda: on_click_factory(t)

                ui.button(qr_text, on_click=make_handler(qr_text)).style(
                    "background-color: #006463; color: white; border-radius: 20px; "
                    "padding: 6px 16px; margin: 4px; font-size: 0.85rem; "
                    "font-family: Nunito, Arial, sans-serif;"
                )
