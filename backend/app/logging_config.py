"""
Logging configuration for HacktoberFest Backend v2.

Critical Rule: `portal_snapshot_json` and `id_card_image_url` (plus `qr_token`)
must NEVER appear in log output. This filter is applied globally to every
logging handler so that no sensitive verification data leaks into logs,
regardless of which service or component emits the record.
"""
import logging
import re

# Sensitive field patterns — any of these keys and their values are scrubbed from log messages
_SENSITIVE_PATTERNS = [
    # Match JSON or Python dict key-value patterns: "key": "value" or 'key': 'value' or {...}
    re.compile(r'[\'"]portal_snapshot_json[\'"]\s*:\s*(\{[^}]*\}|[\'"][^\'"]*[\'"]|\[.*?\]|null|None)', re.DOTALL),
    re.compile(r'[\'"]id_card_image_url[\'"]\s*:\s*[\'"][^\'"]*[\'"]'),
    re.compile(r'[\'"]qr_token[\'"]\s*:\s*[\'"][^\'"]*[\'"]'),
    # Match kwargs-style: key=value
    re.compile(r'portal_snapshot_json\s*=\s*\S+'),
    re.compile(r'id_card_image_url\s*=\s*\S+'),
    re.compile(r'qr_token\s*=\s*\S+'),
    # Match Supabase storage path patterns
    re.compile(r'id-cards/[^\s\'"]+'),
    re.compile(r'id_cards/[^\s\'"]+'),
]

_REDACTION = "[REDACTED]"


def _scrub_message(message: str) -> str:
    """Replace any sensitive field occurrences in a log message with [REDACTED]."""
    for pattern in _SENSITIVE_PATTERNS:
        message = pattern.sub(_REDACTION, message)
    return message


class SensitiveDataFilter(logging.Filter):
    """
    Python logging Filter that scrubs sensitive v2 verification data from every log record.
    Applied globally so that ALL handlers (console, file, Supabase log drain) are protected.

    Fields protected:
      - id_card_image_url   (Supabase Storage path — must never be logged)
      - portal_snapshot_json (PSIT portal response — contains PII; purged post-event)
      - qr_token            (Raw QR payload — contains institutional ID data)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Scrub the main message
        record.msg = _scrub_message(str(record.msg))

        # Scrub any string args that will be interpolated into the message
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _scrub_message(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _scrub_message(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )

        return True  # Always pass — we scrub but never drop records


def configure_logging() -> None:
    """
    Configure global logging with the SensitiveDataFilter applied to the root logger.
    Call this once at application startup (from main.py).
    """
    sensitive_filter = SensitiveDataFilter()

    root_logger = logging.getLogger()
    root_logger.addFilter(sensitive_filter)

    # Also apply to every existing handler
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)

    # And to our app's logger specifically
    app_logger = logging.getLogger("app")
    app_logger.addFilter(sensitive_filter)
