from nicegui import ui
from typing import Callable, Optional


def primary_button(label: str, on_click: Callable) -> ui.button:
    """Teal background, white text button."""
    return ui.button(label, on_click=on_click).style(
        "background-color: #006463; color: white; border-radius: 8px; "
        "font-weight: 600; padding: 8px 20px;"
    )


def secondary_button(label: str, on_click: Callable) -> ui.button:
    """White background, teal border/text button."""
    return ui.button(label, on_click=on_click).props("outline").style(
        "color: #006463; border: 2px solid #006463; border-radius: 8px; "
        "font-weight: 600; padding: 8px 20px; background: white;"
    )


def danger_button(label: str, on_click: Callable) -> ui.button:
    """Red background, white text button."""
    return ui.button(label, on_click=on_click).style(
        "background-color: #c0392b; color: white; border-radius: 8px; "
        "font-weight: 600; padding: 8px 20px;"
    )


def quick_exit_button() -> ui.button:
    """Quick Exit button that redirects to bbc cbbc."""
    return danger_button(
        "Quick Exit",
        on_click=lambda: ui.run_javascript(
            "window.location.href='https://www.bbc.co.uk/cbbc'"
        ),
    )
