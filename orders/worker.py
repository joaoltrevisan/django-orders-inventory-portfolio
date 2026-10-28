"""Signal coordination and observational metrics for the optional expiry worker."""

import signal
from collections import Counter
from contextlib import contextmanager

from django.db.models import Count, Min

from .models import Order
from .reservations import database_now


@contextmanager
def stop_on_signals(event):
    previous = {}
    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, lambda *_: event.set())
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def backlog_observation():
    at = database_now()
    values = Order.objects.filter(
        status=Order.Status.PENDING_PAYMENT, reservation_expires_at__lte=at
    ).aggregate(count=Count("id"), oldest=Min("reservation_expires_at"))
    oldest = values["oldest"]
    return {
        "as_of": at.isoformat(),
        "due_pending_count": values["count"],
        "oldest_deadline": oldest.isoformat() if oldest else None,
        "oldest_overdue_seconds": max(0.0, (at - oldest).total_seconds()) if oldest else None,
        "observation_only": True,
    }


def batch_summary(report):
    if report is None:
        return None
    return {
        "passed": report["passed"],
        "attempted_count": len(report["attempted_order_ids"]),
        "expired_count": len(report["expired_order_ids"]),
        "selected_skipped_count": len(report["skipped_order_ids"]),
        "failure_codes": dict(Counter(row["code"] for row in report["failures"])),
        "stopped": report["stopped"],
        "locked_skips_not_enumerated": True,
    }
