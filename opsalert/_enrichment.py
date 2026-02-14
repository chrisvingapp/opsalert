"""Auto-enrichment — capture runtime debugging info into alert context.

Adds underscore-prefixed keys (won't collide with caller-provided data):
- _caller: module:function:line of the code that fired the alert
- _exc_type, _exc_message, _traceback: active exception info (if any)
- _task_name, _task_id: Celery task info (if running inside a task)
"""
import sys
import traceback as tb_module
from typing import Any

# Module names to skip when walking the stack to find the caller.
# Both this module and _dispatch.py are internal to the package.
_SKIP_MODULES = frozenset({__name__, "opsalert._dispatch", "opsalert"})


def enrich_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Auto-capture runtime debugging info into alert context."""
    enriched = dict(context) if context else {}

    # --- Caller frame ---
    # Walk the stack past this package to find the actual call site.
    frame = sys._getframe()
    try:
        f = frame
        while f is not None:
            module_name = f.f_globals.get("__name__", "")
            if module_name not in _SKIP_MODULES:
                enriched["_caller"] = (
                    f"{module_name}:{f.f_code.co_name}:{f.f_lineno}"
                )
                break
            f = f.f_back
    finally:
        del frame

    # --- Active exception ---
    exc_info = sys.exc_info()
    if exc_info[1] is not None:
        enriched["_exc_type"] = type(exc_info[1]).__name__
        enriched["_exc_message"] = str(exc_info[1])[:500]
        if exc_info[2]:
            enriched["_traceback"] = "".join(
                tb_module.format_tb(exc_info[2])
            )[-2000:]

    # --- Celery task ---
    try:
        from celery import current_task

        if current_task and current_task.request:
            enriched["_task_name"] = current_task.name
            enriched["_task_id"] = current_task.request.id
    except Exception:
        pass

    return enriched
