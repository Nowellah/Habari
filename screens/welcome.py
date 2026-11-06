import os
from nicegui import ui
from components.header import create_header


def show() -> None:
    """Welcome / landing screen."""
    create_header(show_exit=True)

    logo_path = (
        "assets/habari-logo.png"
        if os.path.exists("assets/habari-logo.png")
        else "assets/habari-logo.svg"
    )

    with ui.column().style(
        "max-width: 480px; margin: 0 auto; padding: 32px 20px 48px; "
        "align-items: center; width: 100%;"
    ):
        # Logo
        ui.image(logo_path).style(
            "height: 100px; width: auto; margin-bottom: 8px;"
        )

        # Hero headline
        ui.html(
            '<h1 style="font-size: 1.6rem; font-weight: 800; color: #006463; '
            'text-align: center; margin: 0 0 10px; line-height: 1.3;">'
            'Your voice matters.<br>We\'re here to listen.'
            '</h1>'
        )

        ui.html(
            '<p style="font-size: 1rem; color: #4a5568; text-align: center; '
            'margin: 0 0 28px; line-height: 1.65; max-width: 380px;">'
            'You can talk about something worrying you online, ask questions, '
            'or get help. You do <strong>not</strong> need to share your name to begin.'
            '</p>'
        )

        # Primary CTA
        with ui.column().style("width: 100%; gap: 12px;"):
            ui.button(
                "💬  Start Chat",
                on_click=lambda: ui.navigate.to("/age"),
            ).classes("btn-primary").props("no-caps")

            ui.button(
                "🆘  Get Help Now",
                on_click=lambda: ui.navigate.to("/help"),
            ).classes("btn-accent").props("no-caps")

            ui.button(
                "✕  Quick Exit",
                on_click=lambda: ui.run_javascript(
                    "window.location.replace('https://www.bbc.co.uk/cbbc')"
                ),
            ).classes("btn-danger").props("no-caps")

        # Divider
        ui.html('<hr class="section-divider" style="width:100%;">')

        # Trust signals
        with ui.row().style(
            "gap: 8px; flex-wrap: wrap; justify-content: center; width: 100%;"
        ):
            for item in [
                "🔒 Private & anonymous",
                "🌍 Multiple languages",
                "👤 No name needed",
            ]:
                ui.html(
                    f'<span style="background: white; border: 1px solid #e2e8f0; '
                    f'border-radius: 20px; padding: 5px 14px; font-size: 0.82rem; '
                    f'color: #006463; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">'
                    f'{item}</span>'
                )

        # Privacy footnote
        ui.html(
            '<p style="font-size: 0.78rem; color: #718096; text-align: center; '
            'margin-top: 20px; font-style: italic; line-height: 1.5;">'
            'Quick Exit takes you away from this page but does not erase your browsing history.'
            '</p>'
        )

        # Officer portal link (subtle, at the bottom)
        ui.html('<hr class="section-divider" style="width:100%;">')
        ui.button(
            "🛡️ Officer Portal",
            on_click=lambda: ui.navigate.to("/officer/login"),
        ).props("flat no-caps").style(
            "color:#718096;font-size:0.8rem;align-self:center;"
        )
