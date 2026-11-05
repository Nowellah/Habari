import os
import httpx
from typing import Any


_DEMO_REPLY = {
    "demo": True,
    "reply_text": (
        "I'm here to help you. In demo mode the live backend is not connected, "
        "but you can still explore how Habari works. "
        "Please remember: if you are in danger right now, call 116 or 999."
    ),
    "options": [
        "I am in danger or thinking about hurting myself.",
        "Someone is asking me for pictures, money, or secrets.",
        "An adult in charge is hurting me.",
        "Someone is being mean to me or pretending to be someone else.",
        "Something online is making me uncomfortable.",
    ],
    "state": "CHAT_READY",
}

_DEMO_STATUS = {
    "demo": True,
    "case_code": "DEMO-0000",
    "status": "RECEIVED",
    "message": "Status information is not available in demo mode.",
}


class HabariApiClient:
    """HTTP client for the HABARI Django backend."""

    def __init__(self) -> None:
        self.base_url = os.getenv("DJANGO_API_URL", "http://127.0.0.1:8000").rstrip("/")
        self.timeout = 10.0

    def _demo_reply(self) -> dict[str, Any]:
        return dict(_DEMO_REPLY)

    def _demo_status(self) -> dict[str, Any]:
        return dict(_DEMO_STATUS)

    def send_message(self, session_id: str, text: str, language: str = "en") -> dict[str, Any]:
        """POST /api/channel/web — returns demo dict if backend unreachable."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/channel/web",
                    json={"session_id": session_id, "text": text, "language": language},
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return self._demo_reply()
        except Exception:
            return self._demo_reply()

    def get_case_status(self, case_code: str) -> dict[str, Any]:
        """GET /api/cases/{case_code}/status — returns demo dict if backend unreachable."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.base_url}/api/cases/{case_code}/status")
                resp.raise_for_status()
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return self._demo_status()
        except Exception:
            return self._demo_status()


# Module-level singleton
api_client = HabariApiClient()
