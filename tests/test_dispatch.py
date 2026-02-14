"""Tests for the fire API — warn/error/critical dispatch."""
import asyncio
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

import opsalert
from opsalert.model import Alert
from opsalert.types import AlertSeverity
from opsalert._dispatch import _fire


class TestFireAPI:
    """Test the public warn/error/critical functions."""

    async def test_warn_creates_alert(self, session, session_factory):
        """opsalert.warn() creates an alert row with WARN severity."""
        opsalert.configure(session_factory=session_factory)

        await _fire(AlertSeverity.WARN, "test_category", "test message", "test_source", {"key": "value"})

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        assert alert.severity == "warn"
        assert alert.category == "test_category"
        assert alert.message == "test message"
        assert alert.source == "test_source"
        assert '"key"' in alert.context_json

    async def test_error_creates_alert(self, session, session_factory):
        """opsalert.error() creates an alert with ERROR severity."""
        opsalert.configure(session_factory=session_factory)

        await _fire(AlertSeverity.ERROR, "test_category", "error msg", None, None)

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        assert alert.severity == "error"
        assert alert.context_json is None

    async def test_critical_creates_alert(self, session, session_factory):
        """opsalert.critical() creates an alert with CRITICAL severity."""
        opsalert.configure(session_factory=session_factory)

        await _fire(AlertSeverity.CRITICAL, "infra", "DB pool exhausted", None, {"pool_size": 10})

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        assert alert.severity == "critical"
        assert alert.category == "infra"

    async def test_multiple_fires_create_separate_rows(self, session, session_factory):
        """Each fire call creates a separate row — no dedup at write time."""
        opsalert.configure(session_factory=session_factory)

        for i in range(3):
            await _fire(AlertSeverity.WARN, "cat", f"msg {i}", None, None)

        result = await session.execute(select(Alert))
        alerts = result.scalars().all()
        assert len(alerts) == 3


class TestTestingMode:
    """Test that testing=True suppresses all alert fires."""

    def test_testing_mode_noop(self, session_factory):
        """When testing=True, _fire_sync is a no-op."""
        opsalert.configure(session_factory=session_factory, testing=True)

        # This should not raise or create anything
        opsalert.warn("cat", message="should be suppressed")

    async def test_testing_mode_no_rows(self, session, session_factory):
        """Testing mode doesn't create any rows."""
        opsalert.configure(session_factory=session_factory, testing=True)

        opsalert.warn("cat", message="suppressed")

        result = await session.execute(select(Alert))
        assert result.scalars().all() == []


class TestConfigRequired:
    """Test that configure() must be called before use."""

    def test_fire_without_configure_is_noop(self):
        """Calling warn/error/critical without configure() silently no-ops."""
        # Should not raise — dispatch functions never disrupt caller
        opsalert.warn("cat", message="test")
        opsalert.error("cat", message="test")
        opsalert.critical("cat", message="test")

    async def test_get_config_without_configure_raises(self):
        """get_config() raises RuntimeError if not configured."""
        with pytest.raises(RuntimeError, match="opsalert.configure"):
            opsalert.get_config()


class TestEnrichment:
    """Test that auto-enrichment adds debugging info."""

    async def test_caller_enrichment(self, session, session_factory):
        """Enriched context includes _caller with module:function:line."""
        opsalert.configure(session_factory=session_factory)

        await _fire(
            AlertSeverity.WARN, "cat", "msg", None,
            opsalert._dispatch.enrich_context({"user_key": "user_val"})
        )

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        import json
        ctx = json.loads(alert.context_json)
        assert "user_key" in ctx
        assert "_caller" in ctx
        # _caller should be from THIS test module, not from dispatch internals
        assert "test_dispatch" in ctx["_caller"]

    async def test_exception_enrichment(self, session, session_factory):
        """When called during exception handling, captures exc info."""
        opsalert.configure(session_factory=session_factory)

        try:
            raise ValueError("test boom")
        except ValueError:
            ctx = opsalert._dispatch.enrich_context(None)

        await _fire(AlertSeverity.ERROR, "cat", "msg", None, ctx)

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        import json
        ctx = json.loads(alert.context_json)
        assert ctx["_exc_type"] == "ValueError"
        assert "test boom" in ctx["_exc_message"]
        assert "_traceback" in ctx

    async def test_enrichment_preserves_caller_data(self, session, session_factory):
        """Caller-provided context keys are preserved alongside enrichment."""
        opsalert.configure(session_factory=session_factory)

        ctx = opsalert._dispatch.enrich_context({"my_key": "my_val", "status_code": 500})

        await _fire(AlertSeverity.WARN, "cat", "msg", None, ctx)

        result = await session.execute(select(Alert))
        alert = result.scalar_one()
        import json
        stored = json.loads(alert.context_json)
        assert stored["my_key"] == "my_val"
        assert stored["status_code"] == 500
        assert "_caller" in stored

    async def test_enrichment_with_none_context(self, session, session_factory):
        """Enrichment works when caller passes None context."""
        opsalert.configure(session_factory=session_factory)

        ctx = opsalert._dispatch.enrich_context(None)

        assert "_caller" in ctx
        assert isinstance(ctx, dict)


class TestFireFailureHandling:
    """Test that fire never raises, even on errors."""

    async def test_fire_logs_on_session_error(self, session_factory):
        """If the session factory fails, _fire logs but doesn't raise."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def bad_factory():
            raise ConnectionError("DB is down")
            yield  # pragma: no cover

        opsalert.configure(session_factory=bad_factory)

        # Should not raise
        await _fire(AlertSeverity.ERROR, "cat", "msg", None, None)
