import threading
import uuid
from typing import Optional

from models.session import Session


class SessionManager:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create_session(self, session_id: Optional[str] = None) -> Session:
        sid = session_id or str(uuid.uuid4())
        session = Session(session_id=sid)
        with self._lock:
            self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update=kwargs)
            self._sessions[session_id] = updated
            return updated

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


# Module-level singleton
session_manager = SessionManager()
