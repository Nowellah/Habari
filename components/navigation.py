from nicegui import ui


def navigate_to(screen_name: str) -> None:
    """Navigate to a named screen by route."""
    ui.navigate.to(f"/{screen_name}")


def go_welcome() -> None:
    ui.navigate.to("/")


def go_age() -> None:
    ui.navigate.to("/age")


def go_language() -> None:
    ui.navigate.to("/language")


def go_chat() -> None:
    ui.navigate.to("/chat")


def go_help() -> None:
    ui.navigate.to("/help")
