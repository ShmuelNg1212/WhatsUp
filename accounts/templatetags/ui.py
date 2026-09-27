"""Presentation-only helpers for templates. Load with {% load ui %}."""

import re

from django import template

register = template.Library()

# Tailwind class pairs for initials avatars (see doc/wiki/design-system.md).
AVATAR_TONES = (
    "bg-brand-100 text-brand-700",
    "bg-sage-200 text-sage-800",
    "bg-sky-100 text-sky-800",
    "bg-amber-100 text-amber-800",
    "bg-violet-100 text-violet-800",
    "bg-sage-300 text-sage-900",
)


@register.filter
def avatar_tone(user):
    """A stable colour pair for a user, so their avatar looks the same everywhere."""
    return AVATAR_TONES[(getattr(user, "pk", None) or 0) % len(AVATAR_TONES)]


@register.filter
def initials(user):
    """'Ada Lovelace' → 'AL'; 'PeterYoung' → 'PY'; 'bob' → 'B'."""
    first, last = getattr(user, "first_name", ""), getattr(user, "last_name", "")
    if first and last:
        return (first[0] + last[0]).upper()
    name = getattr(user, "username", "") or "?"
    parts = [p for p in re.split(r"[\W_]+|(?<=[a-z])(?=[A-Z])", name) if p]
    return "".join(p[0] for p in parts[:2]).upper() or name[0].upper()
