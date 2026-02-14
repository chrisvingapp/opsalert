"""Tests for transport implementations."""
import json
from unittest.mock import patch, MagicMock

import pytest

from opsalert.transport import CallableTransport, LogTransport, WebhookTransport
from opsalert.types import AlertMessage


def _make_message(**overrides) -> AlertMessage:
    """Create a test AlertMessage."""
    defaults = {
        "subject": "[ERROR] test: something failed",
        "html_body": "<p>Test</p>",
        "text_body": "Test alert",
        "severity": "error",
        "category": "test",
        "alert_count": 1,
    }
    defaults.update(overrides)
    return AlertMessage(**defaults)


class TestCallableTransport:
    """Test CallableTransport wrapping a host-app function."""

    def test_calls_send_fn(self):
        """Delegates to the provided function."""
        calls = []

        def mock_send(message, *, to, from_addr, from_name):
            calls.append((message, to, from_addr, from_name))
            return True

        transport = CallableTransport(mock_send)
        msg = _make_message()
        result = transport.send(msg, to="ops@test.com", from_addr="alert@test.com", from_name="Alerts")

        assert result is True
        assert len(calls) == 1
        assert calls[0][0] is msg
        assert calls[0][1] == "ops@test.com"

    def test_returns_false_on_fn_failure(self):
        """Returns False when the function returns False."""
        transport = CallableTransport(lambda *a, **kw: False)
        result = transport.send(_make_message(), to="a", from_addr="b", from_name="c")
        assert result is False

    def test_catches_exceptions(self):
        """Never raises — returns False on exception."""
        def boom(*a, **kw):
            raise ConnectionError("network down")

        transport = CallableTransport(boom)
        result = transport.send(_make_message(), to="a", from_addr="b", from_name="c")
        assert result is False


class TestLogTransport:
    """Test LogTransport for development."""

    def test_returns_true(self):
        """Always returns True."""
        transport = LogTransport()
        result = transport.send(_make_message(), to="dev@test.com", from_addr="a", from_name="b")
        assert result is True

    def test_logs_message(self, caplog):
        """Logs the alert at WARNING level."""
        import logging
        with caplog.at_level(logging.WARNING):
            transport = LogTransport()
            transport.send(
                _make_message(severity="critical", category="infra"),
                to="ops@test.com",
                from_addr="a",
                from_name="b",
            )

        assert "CRITICAL" in caplog.text
        assert "infra" in caplog.text


class TestWebhookTransport:
    """Test WebhookTransport with mocked urllib."""

    @patch("opsalert.transport.urllib.request.urlopen")
    def test_posts_json(self, mock_urlopen):
        """POSTs JSON payload to the configured URL."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        transport = WebhookTransport("https://hooks.example.com/alert")
        msg = _make_message(severity="error", category="sendgrid")
        result = transport.send(msg, to="ops@test.com", from_addr="a", from_name="b")

        assert result is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data)
        assert payload["severity"] == "error"
        assert payload["category"] == "sendgrid"

    @patch("opsalert.transport.urllib.request.urlopen")
    def test_returns_false_on_error(self, mock_urlopen):
        """Returns False on network error."""
        mock_urlopen.side_effect = ConnectionError("down")

        transport = WebhookTransport("https://hooks.example.com/alert")
        result = transport.send(_make_message(), to="a", from_addr="b", from_name="c")
        assert result is False

    @patch("opsalert.transport.urllib.request.urlopen")
    def test_custom_headers(self, mock_urlopen):
        """Custom headers are included in the request."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        transport = WebhookTransport(
            "https://hooks.example.com/alert",
            headers={"Authorization": "Bearer tok123"},
        )
        transport.send(_make_message(), to="a", from_addr="b", from_name="c")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer tok123"
