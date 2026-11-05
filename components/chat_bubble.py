import html
from datetime import datetime, timezone
from nicegui import ui


def add_chat_bubble(container, role: str, text: str) -> None:
    """
    Add a chat bubble to *container*.

    role: "child" | "bot"
    text: raw user/bot text — always HTML-escaped before rendering.
    """
    safe_text = html.escape(text).replace("\n", "<br>")
    now = datetime.now(timezone.utc).strftime("%H:%M")

    align = "flex-end" if role == "child" else "flex-start"
    bubble_class = "child-bubble" if role == "child" else "bot-bubble"

    with container:
        ui.html(
            f'<div class="bubble-row {role}" style="justify-content: {align};">'
            f'  <div>'
            f'    <div class="{bubble_class}">{safe_text}</div>'
            f'    <div class="bubble-time">{now}</div>'
            f'  </div>'
            f'</div>'
        )


def add_typing_indicator(container) -> object:
    """Add animated typing dots. Returns the element so caller can delete it."""
    with container:
        el = ui.html(
            '<div class="bubble-row bot" style="justify-content: flex-start;">'
            '  <div class="bot-bubble" style="padding: 12px 18px;">'
            '    <span class="typing-dot"></span>'
            '    <span class="typing-dot"></span>'
            '    <span class="typing-dot"></span>'
            '  </div>'
            '</div>'
        )
    return el
