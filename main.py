import os
from nicegui import ui, app
from dotenv import load_dotenv

load_dotenv()

from components.theme import inject_styles
from screens import welcome, age, language, chat, report, confirmation, status
from screens import help as help_screen
from screens.officer import login as officer_login
from screens.officer import dashboard as officer_dashboard
from screens.officer import case_detail as officer_case


# ── Child-facing screens ──────────────────────────────────────────────────────

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


# ── Officer portal ────────────────────────────────────────────────────────────

@ui.page("/officer/login")
def officer_login_page():
    officer_login.show()


@ui.page("/officer")
def officer_root():
    # Redirect /officer → /officer/login
    ui.navigate.to("/officer/login")


@ui.page("/officer/dashboard")
def officer_dashboard_page():
    officer_dashboard.show()


@ui.page("/officer/case/{code}")
def officer_case_page(code: str):
    officer_case.show(code)


# ── Run ───────────────────────────────────────────────────────────────────────

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
