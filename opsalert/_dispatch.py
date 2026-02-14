"""Dispatch — fire-and-forget alert creation.

Auto-detects async (FastAPI) vs sync (Celery) context.
Never raises — all failures logged, caller unaffected.
Acquires own session via configured session_factory.
Auto-enriches context with runtime debugging info.
"""
import asyncio
import logging
from typing import Any

from opsalert._config import get_config
from opsalert._enrichment import enrich_context
from opsalert.store import fire_alert

logger = logging.getLogger(__name__)


async def _fire(
    severity: str,
    category: str,
    message: str,
    source: str | None,
    context: dict[str, Any] | None,
) -> None:
    """Internal async implementation — acquires session and fires alert."""
    try:
        cfg = get_config()
        async with cfg.session_factory() as session:
            await fire_alert(
                session,
                severity=severity,
                category=category,
                message=message,
                source=source,
                context=context,
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to fire alert: severity=%s category=%s", severity, category)


def _fire_sync(
    severity: str,
    category: str,
    message: str,
    source: str | None,
    context: dict[str, Any] | None,
) -> None:
    """Fire an alert from any context (sync or async).

    Tries to get the running event loop first (FastAPI context),
    falls back to creating a new one (Celery/sync context).
    Never raises — all failures are logged, caller unaffected.

    No-ops when:
    - testing mode is enabled (alerts would leak outside test transaction)
    - configure() hasn't been called (e.g. test suite without startup)
    """
    try:
        cfg = get_config()
    except RuntimeError:
        # Not configured — silently skip rather than disrupting caller
        return
    if cfg.testing:
        return

    context = enrich_context(context)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_fire(severity, category, message, source, context))
    except RuntimeError:
        try:
            asyncio.run(_fire(severity, category, message, source, context))
        except Exception:
            logger.exception(
                "Failed to run alert fire: severity=%s category=%s", severity, category
            )


def warn(
    category: str,
    *,
    message: str,
    source: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Fire a WARN alert. For unexpected but non-breaking issues."""
    from opsalert.types import AlertSeverity

    _fire_sync(AlertSeverity.WARN, category, message, source, context)


def error(
    category: str,
    *,
    message: str,
    source: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Fire an ERROR alert. For something that failed that shouldn't have."""
    from opsalert.types import AlertSeverity

    _fire_sync(AlertSeverity.ERROR, category, message, source, context)


def critical(
    category: str,
    *,
    message: str,
    source: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Fire a CRITICAL alert. For infrastructure-level problems."""
    from opsalert.types import AlertSeverity

    _fire_sync(AlertSeverity.CRITICAL, category, message, source, context)
