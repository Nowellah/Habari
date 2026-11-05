"""
Conversation service — manages the chatbot dialogue state machine.

In demo mode (backend unreachable) this module drives a multi-turn rule-based
conversation that:
  1. Greets the child
  2. Offers five reporting categories
  3. Acknowledges the selected category
  4. Invites the child to describe what happened
  5. Responds supportively and asks one follow-up question
  6. Offers to help submit a report or speak to a human
  7. Routes "Continue to report" → REPORT_REVIEW state

Age-appropriate variants are used for age_bracket == "Under 10".
"""

from __future__ import annotations
from typing import Optional
from .api_client import api_client
from .session import session_manager

# ── Reporting categories ──────────────────────────────────────────────────────

HARM_CATEGORIES = [
    "I am in danger or thinking about hurting myself.",
    "Someone is asking me for pictures, money, or secrets.",
    "An adult in charge is hurting me.",
    "Someone is being mean to me or pretending to be someone else.",
    "Something online is making me uncomfortable.",
]

HARM_CATEGORIES_SIMPLE = [
    "I feel unsafe or want to hurt myself.",
    "Someone wants my pictures or money.",
    "An adult is hurting me.",
    "Someone is being mean to me.",
    "Something online upsets me.",
]

# Map simple → full for state-machine lookup
_SIMPLE_TO_FULL = dict(zip(HARM_CATEGORIES_SIMPLE, HARM_CATEGORIES))

# Shared quick-reply sets
_QR_REPORT_OR_HUMAN = [
    "Continue to report →",
    "I need human support",
    "Tell me more about what happens next",
]
_QR_FOLLOWUP = [
    "Tell me more",
    "Continue to report →",
    "I need human support",
]
_QR_AFTER_FOLLOWUP = [
    "Continue to report →",
    "I need human support",
    "I have more to tell",
]

# ── Per-category scripted responses ──────────────────────────────────────────

_CATEGORY_REPLIES: dict[str, tuple[str, list[str]]] = {
    HARM_CATEGORIES[0]: (
        "I'm really glad you reached out. You are not alone, and what you are feeling matters. "
        "Please know that help is available right now — you can call 116 (the Child Helpline) "
        "or tell a trusted adult nearby.\n\n"
        "Can you tell me a little about what is happening? I'm here to listen.",
        _QR_FOLLOWUP,
    ),
    HARM_CATEGORIES[1]: (
        "That is not okay, and it is not your fault at all. "
        "No one has the right to ask you for pictures, money, or personal secrets.\n\n"
        "Can you tell me more about who is asking and what they are saying to you? "
        "You do not have to share anything that feels too private.",
        _QR_FOLLOWUP,
    ),
    HARM_CATEGORIES[2]: (
        "I believe you, and I want you to know that what you are describing is serious. "
        "You deserve to be safe and to be treated with respect.\n\n"
        "Can you tell me more about what is happening and who is involved? "
        "Everything you share helps us make sure you get the right support.",
        _QR_FOLLOWUP,
    ),
    HARM_CATEGORIES[3]: (
        "That sounds really hurtful, and it is not okay for anyone to treat you that way — "
        "online or offline.\n\n"
        "Can you describe what they are doing or saying? "
        "For example, are they sending mean messages, spreading rumors, "
        "or pretending to be someone they are not?",
        _QR_FOLLOWUP,
    ),
    HARM_CATEGORIES[4]: (
        "I'm glad you felt you could tell me. "
        "Feeling uncomfortable about something online is a good reason to reach out.\n\n"
        "Can you describe what you have seen or what has been happening? "
        "There is no need to share anything that makes you feel worse.",
        _QR_FOLLOWUP,
    ),
}

# Simple (Under 10) variants
_CATEGORY_REPLIES_SIMPLE: dict[str, tuple[str, list[str]]] = {
    HARM_CATEGORIES_SIMPLE[0]: (
        "I'm here with you. You are safe talking to me. "
        "Can you tell me what is making you feel unsafe?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
    HARM_CATEGORIES_SIMPLE[1]: (
        "That is not nice of them to ask. You do not have to give anyone pictures or money. "
        "Can you tell me who is asking you?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
    HARM_CATEGORIES_SIMPLE[2]: (
        "I'm sorry that is happening. You deserve to feel safe. "
        "Can you tell me who is hurting you?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
    HARM_CATEGORIES_SIMPLE[3]: (
        "Being mean to someone is wrong. I'm sorry this is happening to you. "
        "Can you tell me what they are saying or doing?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
    HARM_CATEGORIES_SIMPLE[4]: (
        "It's okay to tell me. What did you see online that upset you?",
        ["Tell me more", "I need help", "Talk to someone"],
    ),
}

# Follow-up replies (state == DESCRIBE_PROBLEM)
_FOLLOWUP_REPLIES: dict[str, tuple[str, list[str]]] = {
    HARM_CATEGORIES[0]: (
        "Thank you for trusting me with this. I can hear that things are really hard right now.\n\n"
        "You have taken an important step by reaching out. "
        "A trained safeguarding officer will be able to review what you share and make sure "
        "you get the right support.\n\n"
        "Would you like to put together a report so someone can look into this properly?",
        _QR_REPORT_OR_HUMAN,
    ),
    HARM_CATEGORIES[1]: (
        "Thank you for sharing that. This is exactly the kind of thing a safeguarding officer "
        "needs to know about.\n\n"
        "What you have described sounds like it could be grooming or exploitation. "
        "You have done nothing wrong by talking about it.\n\n"
        "Would you like to submit a report so this can be investigated?",
        _QR_REPORT_OR_HUMAN,
    ),
    HARM_CATEGORIES[2]: (
        "Thank you for being so brave in sharing this. "
        "What you are describing is something that should never happen to you.\n\n"
        "A safeguarding officer can look into this confidentially and help keep you safe. "
        "Because an adult in authority is involved, your report may be referred to an "
        "independent organization.\n\n"
        "Would you like to submit a report?",
        _QR_REPORT_OR_HUMAN,
    ),
    HARM_CATEGORIES[3]: (
        "Thank you for explaining. Cyberbullying and impersonation are serious, "
        "and you were right to report it.\n\n"
        "A report will help a safeguarding officer look into what is happening "
        "and advise on next steps — including how to block and report the person involved.\n\n"
        "Shall we put a report together?",
        _QR_REPORT_OR_HUMAN,
    ),
    HARM_CATEGORIES[4]: (
        "Thank you for telling me. Even if you are not sure exactly what is wrong, "
        "it is always good to report something that makes you feel uncomfortable.\n\n"
        "A safeguarding officer can review what you have described and advise you. "
        "You will not get into trouble for reporting.\n\n"
        "Would you like to submit a report?",
        _QR_REPORT_OR_HUMAN,
    ),
}

# Special quick-reply actions
_SPECIAL_REPLIES: dict[str, tuple[str, list[str]]] = {
    "Continue to report →": (
        "Great. I've put together a summary of what you've shared. "
        "You can review it on the next screen, make any changes, and then submit it.\n\n"
        "A trained safeguarding officer will receive your report.",
        ["Go to report review →", "Keep chatting"],
    ),
    "Go to report review →": (
        "__navigate_report__",  # special signal to the chat screen
        [],
    ),
    "I need human support": (
        "A safeguarding officer can speak with you directly. "
        "You can also call the Child Helpline on 116 at any time — it is free and confidential.\n\n"
        "Would you like me to connect you now?",
        ["Yes, connect me →", "No, keep chatting"],
    ),
    "Yes, connect me →": (
        "__navigate_help__",
        [],
    ),
    "Tell me more about what happens next": (
        "Once you submit your report, a trained safeguarding officer will review it. "
        "They will follow up with you, or with the relevant support organization, "
        "as quickly as they can.\n\n"
        "You will receive a case code that you can use to check the status of your report. "
        "Nothing will be shared with a parent, teacher, or guardian without your knowledge, "
        "unless there is an immediate risk to your safety.",
        _QR_REPORT_OR_HUMAN,
    ),
    "I have more to tell": (
        "Of course — take your time. Tell me as much or as little as you feel comfortable with.",
        ["Continue to report →", "I need human support"],
    ),
    "I need help": (
        "I'm here. Can you tell me a little more about what is happening so I can help?",
        ["Tell me more", "I need someone to talk to", "Continue to report →"],
    ),
    "I need someone to talk to": (
        "You can call 116 now. It's free and someone will listen. "
        "Or you can keep talking to me here and I will help you make a report.",
        ["Keep chatting", "Continue to report →"],
    ),
    "Keep chatting": (
        "I'm here. What would you like to talk about?",
        HARM_CATEGORIES,
    ),
    "Talk to someone": (
        "__navigate_help__",
        [],
    ),
    "No, keep chatting": (
        "That's okay. I'm still here. "
        "Whenever you are ready, we can put together a report.",
        ["Continue to report →", "Tell me more"],
    ),
}

_DEFAULT_REPLY = (
    "Thank you for sharing that with me. I'm listening and I'm here to help.\n\n"
    "Can you tell me a little more about what has been happening, "
    "or would you like to go ahead and make a report?",
    ["Continue to report →", "Tell me more", "I need human support"],
)

_DEFAULT_REPLY_SIMPLE = (
    "I'm here. Can you tell me more about what is happening?",
    ["Tell me more", "I need help", "Talk to someone"],
)


# ── ConversationService ───────────────────────────────────────────────────────

class ConversationService:
    """Manages conversation state and multi-turn message routing."""

    def process_message(self, session_id: str, text: str) -> tuple[str, list[str]]:
        """
        Process a message and return (reply_text, quick_replies).
        Falls back to rule-based demo responses if backend is offline.
        Returns special sentinel strings for navigation:
          "__navigate_report__"  → chat screen navigates to /report
          "__navigate_help__"    → chat screen navigates to /help
        """
        session = session_manager.get_session(session_id)
        if session is None:
            session = session_manager.create_session(session_id)

        is_young = session.age_bracket == "Under 10"

        # ── Try live backend first ────────────────────────────────────────────
        response = api_client.send_message(session_id, text, session.language)
        if not response.get("demo", True):
            reply = response.get("reply_text", "")
            options = response.get("options", [])
            new_state = response.get("state", session.state)
            session_manager.update_session(session_id, state=new_state)
            return reply, options

        # ── Demo / rule-based fallback ────────────────────────────────────────
        return self._demo_reply(session_id, text, is_young)

    def _demo_reply(
        self, session_id: str, text: str, is_young: bool
    ) -> tuple[str, list[str]]:
        session = session_manager.get_session(session_id)
        state = session.state if session else "WELCOME"

        # ── Initial greeting ──────────────────────────────────────────────────
        if text == "__init__":
            session_manager.update_session(session_id, state="CHAT_READY")
            if is_young:
                return (
                    "Hi there! 👋 I'm Habari. I'm here to help you if something is "
                    "worrying you online.\n\nWhat would you like to talk about?",
                    HARM_CATEGORIES_SIMPLE,
                )
            return (
                "Hello! I'm Habari. I'm here to listen and to help you if something "
                "is worrying you online.\n\n"
                "What would you like to talk about today?",
                HARM_CATEGORIES,
            )

        # ── Normalize simple → full category ─────────────────────────────────
        normalized = _SIMPLE_TO_FULL.get(text, text)

        # ── Special action replies (quick-reply buttons) ──────────────────────
        if text in _SPECIAL_REPLIES or normalized in _SPECIAL_REPLIES:
            lookup_key = text if text in _SPECIAL_REPLIES else normalized
            reply, qr = _SPECIAL_REPLIES[lookup_key]
            if reply == "__navigate_report__":
                session_manager.update_session(session_id, state="REPORT_REVIEW")
            elif reply == "__navigate_help__":
                session_manager.update_session(session_id, state="HUMAN_SUPPORT")
            elif lookup_key == "Continue to report →":
                # Immediately advance to REPORT_REVIEW so the screen can route there
                session_manager.update_session(session_id, state="REPORT_REVIEW")
            return reply, qr

        # ── Harm category selected (CHAT_READY state) ─────────────────────────
        if state == "CHAT_READY":
            if normalized in _CATEGORY_REPLIES:
                session_manager.update_session(session_id, state="PICK_HARM")
                # Store the harm category in session for report building
                _store_harm_category(session_id, normalized)
                if is_young and text in _CATEGORY_REPLIES_SIMPLE:
                    return _CATEGORY_REPLIES_SIMPLE[text]
                return _CATEGORY_REPLIES[normalized]

        # ── Child describing problem (PICK_HARM state) ────────────────────────
        if state == "PICK_HARM":
            session_manager.update_session(session_id, state="DESCRIBE_PROBLEM")
            # Look up a follow-up based on stored harm category
            stored_harm = _get_stored_harm(session_id)
            if stored_harm and stored_harm in _FOLLOWUP_REPLIES:
                return _FOLLOWUP_REPLIES[stored_harm]
            return _DEFAULT_REPLY if not is_young else _DEFAULT_REPLY_SIMPLE

        # ── Additional description after first follow-up ──────────────────────
        if state == "DESCRIBE_PROBLEM":
            session_manager.update_session(session_id, state="REPORT_REVIEW")
            return (
                "Thank you — that is really helpful. "
                "I've noted what you've shared.\n\n"
                "Whenever you feel ready, you can review and submit your report. "
                "Take your time.",
                _QR_AFTER_FOLLOWUP,
            )

        # ── After report review has been offered ─────────────────────────────
        if state == "REPORT_REVIEW":
            return (
                "Your report is ready to review. "
                "Click 'Continue to report →' whenever you are ready.",
                ["Continue to report →", "I need human support"],
            )

        # ── Fallback ──────────────────────────────────────────────────────────
        if is_young:
            return _DEFAULT_REPLY_SIMPLE
        return _DEFAULT_REPLY


def _store_harm_category(session_id: str, category: str) -> None:
    """Persist the selected harm category on the session."""
    session_manager.update_session(session_id, harm_category=category)


def _get_stored_harm(session_id: str) -> Optional[str]:
    """Retrieve the stored harm category — check session field, then message history."""
    session = session_manager.get_session(session_id)
    if session is None:
        return None
    # Direct field (fastest path)
    if session.harm_category:
        return session.harm_category
    # Fallback: walk child messages
    for msg in session.messages:
        if msg.role == "child":
            if msg.text in HARM_CATEGORIES:
                return msg.text
            normalized = _SIMPLE_TO_FULL.get(msg.text)
            if normalized:
                return normalized
    return None


# Module-level singleton
conversation_service = ConversationService()
