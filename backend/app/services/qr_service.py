"""QR Code Decode Service.

Decodes QR codes embedded in PSIT student ID card images.
Multi-engine architecture:
  1. zxing-cpp (primary — high resilience to rotation, blur, skew, glare, contrast)
  2. OpenCV QRCodeDetector (secondary)
  3. pyzbar (optional fallback)

All processing is fully server-side — the client NEVER sends a pre-decoded token.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Flexible PSIT QR URL patterns
PSIT_QR_URL_PREFIX = "https://www.psit.ac.in/op/card-preview/"

# Matches http/https, with or without www, with 32-hex or alphanumeric token
PSIT_URL_TOKEN_RE = re.compile(
    r"https?://(?:www\.)?psit\.ac\.in/op/card-preview/([a-zA-Z0-9_\-\.]+)/?",
    re.IGNORECASE,
)

# Matches query string like ?token=... or &token=...
PSIT_QUERY_TOKEN_RE = re.compile(
    r"[?&](?:token|id|preview)=([a-zA-Z0-9_\-\.]+)",
    re.IGNORECASE,
)

# Generic 32-char hex token pattern
HEX_32_RE = re.compile(r"\b([a-f0-9]{32})\b", re.IGNORECASE)

# Standard 13-character PSIT roll number pattern (e.g. 2401640100099)
ROLL_13_RE = re.compile(r"\b([A-Za-z0-9]{13})\b")


def extract_token_from_qr_text(raw_text: str) -> Optional[str]:
    """
    Extract a usable PSIT token or student identifier from decoded QR text.
    Handles:
      - Full PSIT card preview URLs: https://www.psit.ac.in/op/card-preview/<32-hex>
      - URLs without www or with http
      - URLs with query parameters (?token=...)
      - Raw 32-hex token strings
      - 13-character roll numbers embedded in QR codes
      - Clean trimmed text
    """
    if not raw_text or not raw_text.strip():
        return None

    clean = raw_text.strip()

    # 1. Check exact card-preview URL match
    url_match = PSIT_URL_TOKEN_RE.search(clean)
    if url_match:
        return url_match.group(1).lower()

    # 2. Check URL with query parameter
    query_match = PSIT_QUERY_TOKEN_RE.search(clean)
    if query_match:
        return query_match.group(1).lower()

    # 3. Check for standalone 32-hex token anywhere in text
    hex_match = HEX_32_RE.search(clean)
    if hex_match:
        return hex_match.group(1).lower()

    # 4. Check for 13-character PSIT roll number
    roll_match = ROLL_13_RE.search(clean)
    if roll_match:
        return roll_match.group(1).upper()

    # 5. Return sanitized raw string if it has reasonable token length
    if 8 <= len(clean) <= 128:
        return clean

    return None


def decode_qr_from_image(image_bytes: bytes) -> Optional[str]:
    """
    Decode the PSIT ID card QR code from raw image bytes.

    Tries multiple scanning engines and image pre-processing pipelines:
      1. zxing-cpp (on original BGR, grayscale, and CLAHE enhanced)
      2. OpenCV QRCodeDetector (with 6 preprocessing variants)
      3. pyzbar (if available on the platform)

    Returns:
        Extracted token string (32-hex token, roll number, or preview token),
        or None if no QR code could be read.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "QR scanning requires 'opencv-python-headless'. "
            "Run: pip install opencv-python-headless"
        ) from exc

    # Decode raw bytes into a numpy array image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes. Ensure a valid JPEG or PNG is supplied.")

    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── Engine 1: zxing-cpp (Fastest and most robust) ─────────────────
    try:
        import zxingcpp  # type: ignore

        # Try on original BGR
        barcodes = zxingcpp.read_barcodes(img, try_rotate=True, try_downscale=True, try_invert=True)
        if barcodes:
            for b in barcodes:
                token = extract_token_from_qr_text(b.text)
                if token:
                    logger.info("zxingcpp decoded QR on original image: raw='%s' -> token='%s'", b.text, token)
                    return token

        # Try on grayscale
        barcodes_grey = zxingcpp.read_barcodes(grey, try_rotate=True, try_downscale=True, try_invert=True)
        if barcodes_grey:
            for b in barcodes_grey:
                token = extract_token_from_qr_text(b.text)
                if token:
                    logger.info("zxingcpp decoded QR on grayscale image: raw='%s' -> token='%s'", b.text, token)
                    return token

        # Try with CLAHE (adaptive histogram equalization for glare / bad lighting)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced_grey = clahe.apply(grey)
        barcodes_enhanced = zxingcpp.read_barcodes(enhanced_grey, try_rotate=True, try_downscale=True, try_invert=True)
        if barcodes_enhanced:
            for b in barcodes_enhanced:
                token = extract_token_from_qr_text(b.text)
                if token:
                    logger.info("zxingcpp decoded QR on CLAHE image: raw='%s' -> token='%s'", b.text, token)
                    return token

    except ImportError:
        logger.debug("zxingcpp not installed; falling back to OpenCV/pyzbar.")
    except Exception as exc:
        logger.warning("zxingcpp decode attempt error: %s", exc)

    # ── Pre-process image variants for OpenCV / pyzbar ────────────────
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    inv_binary = cv2.bitwise_not(binary)
    h, w = img.shape[:2]
    upscaled = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    variants = [img, grey, binary, adaptive, inv_binary, upscaled]

    # ── Engine 2: OpenCV native QRCodeDetector ─────────────────────────
    try:
        detector = cv2.QRCodeDetector()
        for variant in variants:
            data, _, _ = detector.detectAndDecode(variant)
            if data:
                token = extract_token_from_qr_text(data)
                if token:
                    logger.info("OpenCV QRCodeDetector decoded: raw='%s' -> token='%s'", data, token)
                    return token
    except Exception as exc:
        logger.debug("OpenCV QRCodeDetector error: %s", exc)

    # ── Engine 3: pyzbar (if available) ───────────────────────────────
    try:
        from pyzbar import pyzbar as pzb  # type: ignore
        for variant in variants:
            decoded_objects = pzb.decode(variant)
            for obj in decoded_objects:
                raw = obj.data.decode("utf-8", errors="ignore").strip()
                token = extract_token_from_qr_text(raw)
                if token:
                    logger.info("pyzbar decoded: raw='%s' -> token='%s'", raw, token)
                    return token
    except Exception:
        pass

    logger.warning("QR decode: no valid PSIT QR code could be extracted from uploaded image.")
    return None


def validate_psit_qr_token(token: str) -> bool:
    """
    Validate that a decoded QR token is a plausible PSIT token.
    Accepts 32-hex tokens, 13-character roll numbers, UUIDs, or alphanumeric tokens.
    """
    clean = token.strip()
    if not clean:
        return False
    # 32-char hex token
    if re.fullmatch(r"[a-f0-9]{32}", clean, re.IGNORECASE):
        return True
    # 13-char roll number
    if re.fullmatch(r"[A-Za-z0-9]{13}", clean):
        return True
    # UUID
    if re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", clean, re.IGNORECASE):
        return True
    # Alphanumeric token (between 6 and 64 characters)
    if re.fullmatch(r"[a-zA-Z0-9_\-\.]{6,64}", clean):
        return True
    return False


def build_psit_card_url(token: str) -> str:
    """Build the full PSIT card-preview URL from a token."""
    return f"{PSIT_QR_URL_PREFIX}{token.strip().lower()}"
