"""Tests for fire_alert store operation."""
import json

import pytest
from sqlalchemy import select

from opsalert.model import Alert
from opsalert.store import fire_alert
from opsalert.types import AlertSeverity


class TestFireAlert:
    """Test the fire_alert store function directly."""

    async def test_creates_row(self, session):
        """fire_alert creates a single row with all fields set."""
        alert = await fire_alert(
            session,
            severity=AlertSeverity.ERROR,
            category="sendgrid_delivery",
            message="SendGrid returned 500",
            source="email",
            context={"status_code": 500, "mail_id": 123},
        )
        await session.commit()

        assert alert.id is not None
        assert alert.severity == "error"
        assert alert.category == "sendgrid_delivery"
        assert alert.message == "SendGrid returned 500"
        assert alert.source == "email"
        assert alert.notified is False
        assert alert.created is not None

        ctx = json.loads(alert.context_json)
        assert ctx["status_code"] == 500
        assert ctx["mail_id"] == 123

    async def test_none_context(self, session):
        """fire_alert with no context stores NULL context_json."""
        alert = await fire_alert(
            session,
            severity=AlertSeverity.WARN,
            category="test",
            message="no context",
        )
        await session.commit()

        assert alert.context_json is None

    async def test_none_source(self, session):
        """fire_alert with no source stores NULL source."""
        alert = await fire_alert(
            session,
            severity=AlertSeverity.WARN,
            category="test",
            message="no source",
        )
        await session.commit()

        assert alert.source is None

    async def test_each_call_creates_new_row(self, session):
        """No dedup — each call produces a distinct row."""
        ids = []
        for _ in range(5):
            alert = await fire_alert(
                session,
                severity=AlertSeverity.WARN,
                category="same",
                message="same",
            )
            ids.append(alert.id)
        await session.commit()

        assert len(set(ids)) == 5

    async def test_context_with_nested_data(self, session):
        """Context can contain nested dicts and lists."""
        context = {
            "errors": [{"field": "name", "msg": "required"}],
            "metadata": {"request_id": "abc-123"},
        }
        alert = await fire_alert(
            session,
            severity=AlertSeverity.ERROR,
            category="validation",
            message="Validation failed",
            context=context,
        )
        await session.commit()

        stored = json.loads(alert.context_json)
        assert stored["errors"][0]["field"] == "name"
        assert stored["metadata"]["request_id"] == "abc-123"

    async def test_long_message_stored(self, session):
        """Messages up to 500 chars are stored."""
        long_msg = "x" * 500
        alert = await fire_alert(
            session,
            severity=AlertSeverity.WARN,
            category="test",
            message=long_msg,
        )
        await session.commit()

        assert alert.message == long_msg

    async def test_severity_values(self, session):
        """All three severity values are accepted."""
        for sev in AlertSeverity:
            alert = await fire_alert(
                session,
                severity=sev,
                category="test",
                message=f"severity {sev}",
            )
            assert alert.severity == sev.value

    async def test_notified_defaults_false(self, session):
        """New alerts default to notified=False."""
        alert = await fire_alert(
            session,
            severity=AlertSeverity.ERROR,
            category="test",
            message="test",
        )
        await session.commit()

        # Re-query to verify DB-level default
        result = await session.execute(select(Alert).where(Alert.id == alert.id))
        loaded = result.scalar_one()
        assert loaded.notified is False
