"""Regras de data/hora vindas do campo."""

from datetime import datetime, timedelta

from app.core.errors import UnprocessableError
from app.db.mixins import utcnow

# Tolerância para relógio de aparelho adiantado.
MAX_CLOCK_SKEW = timedelta(minutes=5)


def resolve_occurred_at(value: datetime | None) -> datetime:
    """Usa a hora informada (registro offline) ou agora; rejeita datas no futuro."""
    now = utcnow()
    if value is None:
        return now
    if value > now + MAX_CLOCK_SKEW:
        raise UnprocessableError("Data/hora no futuro.", code="future_timestamp")
    return value
