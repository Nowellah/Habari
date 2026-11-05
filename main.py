import os
from nicegui import ui, app
from dotenv import load_dotenv

load_dotenv()

from components.theme import apply_global_styles
from screens import welcome, age, language, chat, report, confirmation, status
from screens import help as help_screen

apply_global_styles()


@ui.page("/")
def index():
    welcome.show()


@ui.page("/age")
def age_page():
    age.show()


@ui.page("/language")
def language_page():
    language.show()


@ui.page("/chat")
def chat_page():
    chat.show()


@ui.page("/report")
def report_page():
    report.show()


@ui.page("/confirmation")
def confirmation_page():
    confirmation.show()


@ui.page("/status")
def status_page():
    status.show()


@ui.page("/help")
def help_page():
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
