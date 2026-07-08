"""
Shared UI vocabulary: tags, canonical statuses and their Polish display labels.

The DB stores canonical English statuses (see db.queries.CANONICAL_STATUSES,
matching the Lead model's documented values). The UI always displays Polish
via status_label() / format_func — never store a label in the DB.
"""

from db.queries import CANONICAL_STATUSES

AVAILABLE_TAGS = ["JDD", "OMH", "CONFIDENCE"]

STATUS_OPTIONS = list(CANONICAL_STATUSES)  # ["new", "sent", "opened", "replied", "bounced"]

STATUS_LABELS = {
    "new":     "nowy",
    "sent":    "wysłany",
    "opened":  "otwarty",
    "replied": "odpowiedział",
    "bounced": "odbitka",
}

STATUS_CLASS = {
    "new":     "lb-nowy",
    "sent":    "lb-sent",
    "opened":  "lb-opened",
    "replied": "lb-replied",
    "bounced": "lb-bounced",
}


def status_label(status: str) -> str:
    """Polish display label for a canonical status; unknown values pass through."""
    return STATUS_LABELS.get(status, status)
