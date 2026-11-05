from typing import Optional
from .api_client import api_client
from .session import session_manager

_HARM_CATEGORIES: list[str] = [
    "I am in danger or thinking about hurting myself.",
    "Someone is asking me for pictures, money, or secrets.",
    "An adult in charge is hurting me.",
    "Someone is being mean to me or pretending to be someone else.",
    "Something online is making me uncomfortable.",
]

_SIMPLE_HARM_CATEGORIES: list[str] = [
    "I feel unsafe.",
    "Someone is asking for pictures or money.",
    "Someone is hurting me.",
    "Someone is being mean to me.",
    "Something online upsets me.",
]

_DEMO_RESPONSES: dict[str, tuple[str, list[str]]] = {
    "__init__": (
        "What would you like to talk about today?",
        _HARM_CATEGORIES,
    ),
    "I am in danger or thinking about hurting myself.": (
        "I'm really glad you told me. You are not alone, and help is available right now. "
        "Please call 116 — the Child Helpline — or tell a trusted adult near you. "
        "Can you tell me a little more about what is happening so I can help you?",
        ["Tell me more", "I need human support", "Call 116"],
    ),
    "Someone is asking me for pictures, money, or secrets.": (
        "That is not okay, and it is not your fault. "
        "You don't have to send anything to anyone who makes you feel uncomfortable. "
        "Can you tell me more about who is asking and what they are saying?",
        ["Tell me more", "I want to make a report", "I need human support"],
    ),
    "An adult in charge is hurting me.": (
        "I believe you, and what you are describing is serious. "
        "You deserve to be safe. "
        "Can you tell me more about what is happening? "
        "I can help you make a report and connect you with someone who can help.",
        ["Tell me more", "I want to make a report", "I need human support"],
    ),
    "Someone is being mean to me or pretending to be someone else.": (
        "That sounds really upsetting, and it is not okay for anyone to treat you that way. "
        "Can you tell me more about what they are doing or saying?",
        ["Tell me more", "I want to make a report", "I need human support"],
    ),
    "Something online is making me uncomfortable.": (
        "I'm glad you felt you could tell me. "
        "You don't have to deal with this alone. "
        "Can you describe what you have seen or what is happening online?",
        ["Tell me more", "I want to make a report", "I need human support"],
    ),
    "I want to make a report": (
        "I can help you make a report. "
        "Your report will be reviewed by a trained safeguarding officer. "
        "You do not have to share your name. "
        "Can you describe what happened in your own words?",
        ["Continue to report", "Ask me a question instead"],
    ),
    "I need human support": (
        "A trained safeguarding officer can speak with you directly. "
        "You can also call the Child Helpline on 116 at any time. "
        "Would you like me to connect you now?",
        ["Yes, connect me", "No, I'll stay here"],
    ),
    "default": (
        "Thank you for sharing that with me. "
        "You are safe here, and I am listening. "
        "Can you tell me a bit more so I can help you better?",
        ["Tell me more", "I want to make a report", "Get human support"],
    ),
}

_SIMPLE_DEMO_RESPONSES: dict[str, tuple[str, list[str]]] = {
    "__init__": (
        "Hi! What do you want to talk about?",
        _SIMPLE_HARM_CATEGORIES,
    ),
    "default": (
        "I'm here to help you. Can you tell me more?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
}


class ConversationService:
    """Manages conversation state and message routing."""

    def process_message(self, session_id: str, text: str) -> tuple[str, list[str]]:
        """
        Process a message for a session.

        Returns (reply_text, quick_replies).
        Falls back to rule-based demo responses if backend is offline.
        """
        session = session_manager.get_session(session_id)
        if session is None:
            session = session_manager.create_session(session_id)

        is_young = session.age_bracket == "Under 10"

        # Attempt live backend
        response = api_client.send_message(session_id, text, session.language)
        is_demo = response.get("demo", False)

        if not is_demo:
            reply = response.get("reply_text", "")
            options = response.get("options", [])
            new_state = response.get("state", session.state)
            session_manager.update_session(session_id, state=new_state)
            return reply, options

        # --- Demo / rule-based fallback ---
        if text == "__init__":
            session_manager.update_session(session_id, state="CHAT_READY")
            if is_young:
                return _SIMPLE_DEMO_RESPONSES["__init__"]
            return _DEMO_RESPONSES["__init__"]

        # State transitions
        current_state = session.state
        if current_state == "CHAT_READY":
            session_manager.update_session(session_id, state="PICK_HARM")
        elif current_state == "PICK_HARM":
            session_manager.update_session(session_id, state="DESCRIBE_PROBLEM")
        elif current_state == "DESCRIBE_PROBLEM":
            session_manager.update_session(session_id, state="REPORT_REVIEW")

        if is_young:
            reply, qr = _SIMPLE_DEMO_RESPONSES.get(text, _SIMPLE_DEMO_RESPONSES["default"])
            return reply, qr

        reply, qr = _DEMO_RESPONSES.get(text, _DEMO_RESPONSES["default"])
        return reply, qr


# Module-level singleton
conversation_service = ConversationService()
