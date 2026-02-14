"""Store — create one alert row per occurrence.

Every call creates a new Alert record. No deduplication at the data layer;
grouping is done at query time via ``category`` and ``message`` fields.
"""
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from opsalert.model import Alert

logger = logging.getLogger(__name__)


async def fire_alert(
    session: "AsyncSession",
    *,
    severity: str,
    category: str,
    message: str,
    source: str | None = None,
    context: dict[str, Any] | None = None,
) -> Alert:
    """Create an alert record. Every call creates one row."""
    alert = Alert(
        severity=severity,
        category=category,
        message=message,
        source=source,
        context_json=json.dumps(context) if context else None,
    )
    session.add(alert)
    await session.flush()
    return alert
