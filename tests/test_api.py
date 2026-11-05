import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import httpx
from unittest.mock import patch, MagicMock
from services.api_client import HabariApiClient


def make_client(base_url="http://127.0.0.1:8000"):
    client = HabariApiClient()
    client.base_url = base_url
    return client


# ---- send_message ----

def test_send_message_success():
    expected = {"reply_text": "Hello", "options": [], "state": "CHAT_READY"}
    mock_response = MagicMock()
    mock_response.json.return_value = expected
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = mock_response
        mock_client_cls.return_value = mock_ctx

        client = make_client()
        result = client.send_message("sess-1", "hello", "en")

    assert result == expected


def test_send_message_connect_error_returns_demo():
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.side_effect = httpx.ConnectError("refused")
        mock_client_cls.return_value = mock_ctx

        client = make_client()
        result = client.send_message("sess-1", "hello", "en")

    assert result.get("demo") is True


def test_send_message_http_500_returns_demo():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = mock_response
        mock_client_cls.return_value = mock_ctx

        client = make_client()
        result = client.send_message("sess-1", "hello", "en")

    assert result.get("demo") is True


# ---- get_case_status ----

def test_get_case_status_success():
    expected = {"case_code": "ABC123", "status": "RECEIVED"}
    mock_response = MagicMock()
    mock_response.json.return_value = expected
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_response
        mock_client_cls.return_value = mock_ctx

        client = make_client()
        result = client.get_case_status("ABC123")

    assert result == expected


def test_get_case_status_connect_error_returns_demo():
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.side_effect = httpx.ConnectError("refused")
        mock_client_cls.return_value = mock_ctx

        client = make_client()
        result = client.get_case_status("ABC123")

    assert result.get("demo") is True
