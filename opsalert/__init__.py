"""opsalert — standalone operational alerting.

Fire-and-forget alerts with dashboard queries and pluggable delivery.

Usage::

    import opsalert

    # Configure once at startup
    opsalert.configure(session_factory=my_session_factory)

    # Fire alerts from anywhere
    opsalert.warn("sendgrid_delivery", message="SendGrid 429", source="email")
    opsalert.error("sendgrid_delivery", message="SendGrid 500", source="email")
    opsalert.critical("startup_failure", message="DB pool exhausted")
"""
from opsalert._config import configure, get_config, reset_config
from opsalert._dispatch import warn, error, critical
from opsalert.model import Alert, OpsAlertBase
from opsalert.store import fire_alert
from opsalert.query import (
    query_categories,
    query_messages,
    query_occurrences,
    query_aggregates,
    query_next_fix,
    delete_by_category,
    delete_by_id,
)
from opsalert.delivery import deliver_alerts
from opsalert.cleanup import cleanup_alerts
from opsalert.transport import Transport, CallableTransport, LogTransport, WebhookTransport
from opsalert.types import AlertSeverity, AlertMessage, IMMEDIATE_SEVERITIES, DIGEST_SEVERITIES

__all__ = [
    # Configuration
    "configure",
    "get_config",
    "reset_config",
    # Fire API
    "warn",
    "error",
    "critical",
    # Direct store access
    "fire_alert",
    # Query API
    "query_categories",
    "query_messages",
    "query_occurrences",
    "query_aggregates",
    "query_next_fix",
    # Delete API
    "delete_by_category",
    "delete_by_id",
    # Sweeper entry points
    "deliver_alerts",
    "cleanup_alerts",
    # Transport
    "Transport",
    "CallableTransport",
    "LogTransport",
    "WebhookTransport",
    # Model (for Alembic integration)
    "Alert",
    "OpsAlertBase",
    # Types
    "AlertSeverity",
    "AlertMessage",
    "IMMEDIATE_SEVERITIES",
    "DIGEST_SEVERITIES",
]
