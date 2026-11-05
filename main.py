import os
from nicegui import ui, app
from dotenv import load_dotenv

load_dotenv()

from components.theme import inject_styles
from screens import welcome, age, language, chat, report, confirmation, status
from screens import help as help_screen


@ui.page("/")
def index():
    inject_styles()
    welcome.show()


@ui.page("/age")
def age_page():
    inject_styles()
    age.show()


@ui.page("/language")
def language_page():
    inject_styles()
    language.show()


@ui.page("/chat")
def chat_page():
    inject_styles()
    chat.show()


@ui.page("/report")
def report_page():
    inject_styles()
    report.show()


@ui.page("/confirmation")
def confirmation_page():
    inject_styles()
    confirmation.show()


@ui.page("/status")
def status_page():
    inject_styles()
    status.show()


@ui.page("/help")
def help_page():
    inject_styles()
    help_screen.show()


if __name__ == "__main__":
    ui.run(
        host="127.0.0.1",
        port=8080,
        title="HABARI — Child Safety",
        favicon="assets/habari-logo.svg",
        dark=False,
        reload=False,
        storage_secret=os.getenv(
            "STORAGE_SECRET", "habari-dev-secret-change-in-production"
        ),
    )
