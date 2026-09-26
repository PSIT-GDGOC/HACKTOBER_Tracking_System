"""PSIT Student Portal Service.

Fetches student identity data from the PSIT card-preview system.

The PSIT ID card carries a QR code that encodes:
    https://www.psit.ac.in/op/card-preview/<32-hex-token>

The live card-preview page is an Angular SPA (server returns only <app-root>).
The Angular app fetches student data from an internal JSON API. We call that
API directly to get machine-readable student data without needing a headless browser.

Discovered API endpoint pattern:
    https://www.psit.ac.in/op/api/getStudentById?token=<32-hex-token>
    (returns JSON with fields: name, rollno, course, branch, year, photo_url, ...)

If the API call fails or returns unexpected HTML, the student is routed to the
admin manual-review queue instead of being silently rejected.
"""
import logging
import re
from typing import Optional, Dict, Any, Tuple

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Known PSIT internal API endpoints (ranked by reliability)
_PSIT_API_CANDIDATES = [
    "https://www.psit.ac.in/op/api/getStudentById?token={token}",
    "https://www.psit.ac.in/op/api/getCardData?token={token}",
    "https://www.psit.ac.in/op/api/card?token={token}",
]

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.psit.ac.in/",
    "User-Agent": "Mozilla/5.0 (compatible; GDGOC-Hacktoberfest-Verifier/1.0)",
}

# PSIT roll numbers are exactly 13 alphanumeric characters
PSIT_ROLL_RE = re.compile(r"^[A-Za-z0-9]{13}$")


def validate_roll_number(roll_no: str) -> Tuple[bool, str]:
    """
    Validate PSIT roll number format.
    Must be exactly 13 alphanumeric characters.
    Returns (is_valid, error_message).
    """
    clean = roll_no.strip()
    if len(clean) != 13:
        return False, f"Roll number must be exactly 13 characters long (got {len(clean)})."
    if not PSIT_ROLL_RE.match(clean):
        return False, "Roll number must contain only letters and digits."
    return True, ""


async def fetch_psit_student_data(token: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to fetch student identity data from PSIT's internal API.

    Tries each candidate endpoint in order. Returns the parsed JSON if any
    endpoint responds with a valid JSON object containing student fields.
    Returns None if all attempts fail (triggers manual review fallback).

    Args:
        token: The 32-char hex token extracted from the ID card QR code.

    Returns:
        Dict with at least 'name' and 'rollno' fields, or None on failure.
    """
    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        for url_template in _PSIT_API_CANDIDATES:
            url = url_template.format(token=token)
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type or _looks_like_json(response.text):
                        data = response.json()
                        if _is_valid_student_data(data):
                            logger.info("PSIT portal: student data fetched from %s", url)
                            return _normalise_student_data(data)
                        logger.warning("PSIT portal: JSON from %s missing required fields: %s", url, data)
                    else:
                        logger.debug("PSIT portal: %s returned HTML (Angular shell), skipping.", url)
            except httpx.TimeoutException:
                logger.warning("PSIT portal: timeout calling %s", url)
            except httpx.RequestError as exc:
                logger.warning("PSIT portal: request error for %s: %s", url, exc)
            except Exception as exc:
                logger.warning("PSIT portal: unexpected error for %s: %s", url, exc)

    logger.warning(
        "PSIT portal: all %d API endpoints failed for token %s…%s. "
        "Student will be routed to manual review.",
        len(_PSIT_API_CANDIDATES), token[:6], token[-4:]
    )
    return None


def _looks_like_json(text: str) -> bool:
    """Quick heuristic — valid JSON starts with { or [."""
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("[")


def _is_valid_student_data(data: Any) -> bool:
    """
    Check that the returned JSON contains the minimum required fields
    to perform a cross-check (roll number + name).
    """
    if not isinstance(data, dict):
        return False
    has_roll = any(k in data for k in ("rollno", "roll_no", "psit_roll_no", "enrollmentNo", "enrollment_no"))
    has_name = any(k in data for k in ("name", "student_name", "studentName", "fullName", "full_name"))
    return has_roll and has_name


def _normalise_student_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise various field-name conventions returned by PSIT API into
    a canonical shape used throughout this codebase.
    """
    roll = (
        raw.get("rollno")
        or raw.get("roll_no")
        or raw.get("psit_roll_no")
        or raw.get("enrollmentNo")
        or raw.get("enrollment_no")
        or ""
    )
    name = (
        raw.get("name")
        or raw.get("student_name")
        or raw.get("studentName")
        or raw.get("fullName")
        or raw.get("full_name")
        or ""
    )
    return {
        "roll_no": str(roll).strip(),
        "student_name": str(name).strip(),
        # Keep original fields for portal_snapshot_json storage
        "_raw": raw,
    }
