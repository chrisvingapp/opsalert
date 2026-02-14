"""Tests for TTL cleanup."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import opsalert
from opsalert.model import Alert
from opsalert.cleanup import cleanup_alerts


class TestCleanupAlerts:
    """Test age-based alert deletion."""

    async def test_deletes_old_alerts(self, session, session_factory):
        """Alerts older than max_age_days are deleted."""
        opsalert.configure(session_factory=session_factory, retention_max_age_days=30)

        # Old alert (45 days)
        old = Alert(
            severity="warn",
            category="cat",
            message="old",
            created=datetime.now(timezone.utc) - timedelta(days=45),
        )
        # Recent alert (5 days)
        recent = Alert(
            severity="warn",
            category="cat",
            message="recent",
            created=datetime.now(timezone.utc) - timedelta(days=5),
        )
        session.add_all([old, recent])
        await session.commit()

        result = await cleanup_alerts(session)
        await session.commit()

        assert result["deleted"] == 1

        remaining = (await session.execute(select(Alert))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].message == "recent"

    async def test_respects_max_age_setting(self, session, session_factory):
        """Uses the configured retention_max_age_days."""
        opsalert.configure(session_factory=session_factory, retention_max_age_days=7)

        # 10-day-old alert (should be deleted with 7-day retention)
        alert = Alert(
            severity="warn",
            category="cat",
            message="m",
            created=datetime.now(timezone.utc) - timedelta(days=10),
        )
        session.add(alert)
        await session.commit()

        result = await cleanup_alerts(session)
        await session.commit()

        assert result["deleted"] == 1

    async def test_no_deletions_when_all_recent(self, session, session_factory):
        """Returns deleted=0 when all alerts are within retention window."""
        opsalert.configure(session_factory=session_factory, retention_max_age_days=90)

        alert = Alert(
            severity="warn",
            category="cat",
            message="m",
            created=datetime.now(timezone.utc) - timedelta(days=30),
        )
        session.add(alert)
        await session.commit()

        result = await cleanup_alerts(session)
        assert result["deleted"] == 0

    async def test_empty_db(self, session, session_factory):
        """Returns deleted=0 when no alerts exist."""
        opsalert.configure(session_factory=session_factory)
        result = await cleanup_alerts(session)
        assert result["deleted"] == 0
