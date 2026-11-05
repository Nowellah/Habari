import html
from datetime import datetime
from nicegui import ui


def add_chat_bubble(container, role: str, text: str) -> None:
    """
    Add a chat message bubble to a container.

    Args:
        container: A NiceGUI container element.
        role: "child" or "bot"
        text: The message text (will be HTML-escaped to prevent XSS).
    """
    escaped = html.escape(text)
    timestamp = datetime.utcnow().strftime("%H:%M")

    with container:
        if role == "child":
            with ui.row().style("justify-content: flex-end; width: 100%; margin: 4px 0;"):
                with ui.column().style("align-items: flex-end; max-width: 80%;"):
                    ui.html(f'<div class="child-bubble">{escaped}</div>')
                    ui.label(timestamp).style(
                        "font-size: 0.7rem; color: #888; margin-top: 2px;"
                    )
        else:
            with ui.row().style("justify-content: flex-start; width: 100%; margin: 4px 0;"):
                with ui.column().style("align-items: flex-start; max-width: 80%;"):
                    ui.html(f'<div class="bot-bubble">{escaped}</div>')
                    ui.label(timestamp).style(
                        "font-size: 0.7rem; color: #888; margin-top: 2px;"
                    )
