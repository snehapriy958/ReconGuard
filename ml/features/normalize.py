"""
ReconLens — normalization utilities.

Preserves raw values alongside normalized ones (never destroys the original),
per the design rule that normalization is an input to similarity features,
not a replacement for the source data.
"""

from __future__ import annotations

import re
import unicodedata

_LEGAL_SUFFIXES = [
    "private limited", "pvt limited", "pvt ltd", "private ltd",
    "limited", "ltd", "llp", "inc", "incorporated", "corp", "corporation",
]

_PUNCT_RE = re.compile(r"[.,\-_/\\&()'\"]+")
_WS_RE = re.compile(r"\s+")


def normalize_vendor(raw: str | None) -> str:
    """Lowercase, unicode-normalize, strip punctuation/whitespace noise, and
    drop a common legal suffix IF one is present as a trailing token — this
    is deliberately conservative: it removes noise that doesn't distinguish
    entities, but does not collapse genuinely different names together.
    """
    if raw is None or (isinstance(raw, float)):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()

    # Strip exactly one trailing legal-suffix token sequence, longest match first,
    # so "reliance industries pvt ltd" -> "reliance industries" but we don't
    # accidentally eat a suffix that's actually part of a distinguishing name.
    for suffix in sorted(_LEGAL_SUFFIXES, key=len, reverse=True):
        if s.endswith(" " + suffix):
            s = s[: -(len(suffix) + 1)].strip()
            break
        if s == suffix:
            s = ""
            break
    return s


def normalize_reference(raw: str | None) -> str:
    """Uppercase, strip whitespace/separators. Does NOT treat empty as a
    normal value — callers must check for emptiness explicitly via the
    is_missing_reference helper before comparing, so 'missing == missing'
    can never be silently scored as a match.
    """
    if raw is None or (isinstance(raw, float)):
        return ""
    s = str(raw).strip().upper()
    s = re.sub(r"[\s\-_/]+", "", s)
    return s


def is_missing_reference(raw: str | None) -> bool:
    if raw is None:
        return True
    if isinstance(raw, float):
        return True  # NaN from pandas
    return str(raw).strip() == ""
