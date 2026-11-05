"""Tests for HabariApiClient — backend communication and fallback behavior."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import httpx
from unittest.mock import patch, MagicMock
from services.api_client import HabariApiClient


def make_client(base_url: str = "http://127.0.0.1:8000") -> HabariApiClient:
    client = HabariApiClient()
    client.base_url = base_url
    return client


def _mock_httpx_client(method: str, return_value=None, side_effect=None):
    """Return a context-manager mock for httpx.Client that stubs one HTTP method."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    method_mock = getattr(mock_ctx, method)
    if side_effect is not None:
        method_mock.side_effect = side_effect
    else:
        method_mock.return_value = return_value
    return mock_ctx


# ── send_message ──────────────────────────────────────────────────────────────

def test_send_message_success():
    expected = {"reply_text": "Hello", "options": [], "state": "CHAT_READY"}
    resp = MagicMock()
    resp.json.return_value = expected
    resp.raise_for_status = MagicMock()

    ctx = _mock_httpx_client("post", return_value=resp)
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("sess-1", "hello", "en")

    assert result == expected


def test_send_message_connect_error_returns_demo():
    ctx = _mock_httpx_client("post", side_effect=httpx.ConnectError("refused"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("sess-1", "hello", "en")

    assert result.get("demo") is True
    assert "reply_text" in result


def test_send_message_timeout_returns_demo():
    ctx = _mock_httpx_client("post", side_effect=httpx.TimeoutException("timeout"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("sess-1", "hello", "en")

    assert result.get("demo") is True


def test_send_message_http_500_returns_demo():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    ctx = _mock_httpx_client("post", return_value=resp)
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("sess-1", "hello", "en")

    assert result.get("demo") is True


def test_send_message_demo_has_options():
    ctx = _mock_httpx_client("post", side_effect=httpx.ConnectError("x"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("s", "hi", "en")

    assert isinstance(result.get("options"), list)
    assert len(result["options"]) > 0


def test_send_message_demo_has_helpline_hint():
    ctx = _mock_httpx_client("post", side_effect=httpx.ConnectError("x"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().send_message("s", "hi", "en")

    assert "116" in result.get("reply_text", "")


# ── get_case_status ───────────────────────────────────────────────────────────

def test_get_case_status_success():
    expected = {"case_code": "AB-123456", "status": "RECEIVED"}
    resp = MagicMock()
    resp.json.return_value = expected
    resp.raise_for_status = MagicMock()

    ctx = _mock_httpx_client("get", return_value=resp)
    with patch("httpx.Client", return_value=ctx):
        result = make_client().get_case_status("AB-123456")

    assert result == expected


def test_get_case_status_connect_error_returns_demo():
    ctx = _mock_httpx_client("get", side_effect=httpx.ConnectError("refused"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().get_case_status("AB-123456")

    assert result.get("demo") is True


def test_get_case_status_timeout_returns_demo():
    ctx = _mock_httpx_client("get", side_effect=httpx.TimeoutException("timeout"))
    with patch("httpx.Client", return_value=ctx):
        result = make_client().get_case_status("AB-123456")

    assert result.get("demo") is True


def test_get_case_status_404_returns_demo():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    ctx = _mock_httpx_client("get", return_value=resp)
    with patch("httpx.Client", return_value=ctx):
        result = make_client().get_case_status("NOTFOUND")

    assert result.get("demo") is True


# ── Demo mode isolation ───────────────────────────────────────────────────────

def test_demo_reply_is_independent_copy():
    """Two demo replies must not share the same dict object."""
    ctx = _mock_httpx_client("post", side_effect=httpx.ConnectError("x"))
    c = make_client()
    with patch("httpx.Client", return_value=ctx):
        r1 = c.send_message("s1", "hi", "en")
    ctx2 = _mock_httpx_client("post", side_effect=httpx.ConnectError("x"))
    with patch("httpx.Client", return_value=ctx2):
        r2 = c.send_message("s2", "hi", "en")

    assert r1 is not r2  # independent copies — mutating one must not affect the other


def test_send_message_passes_correct_payload():
    """The client must include session_id, text, and language in its POST body."""
    resp = MagicMock()
    resp.json.return_value = {"reply_text": "ok", "options": [], "state": "CHAT_READY"}
    resp.raise_for_status = MagicMock()

    ctx = _mock_httpx_client("post", return_value=resp)
    with patch("httpx.Client", return_value=ctx):
        make_client().send_message("my-sess", "test text", "lg")

    call_kwargs = ctx.post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
    assert payload.get("session_id") == "my-sess"
    assert payload.get("text") == "test text"
    assert payload.get("language") == "lg"
