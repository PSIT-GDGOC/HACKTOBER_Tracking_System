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

    Memory-optimized pipeline for containerized environments (Render 512MB RAM):
      1. Downscales phone photos (>1600px) saving >80% RAM per upload.
      2. Tries zxing-cpp directly on image with early exit.
      3. Evaluates OpenCV/pyzbar variants lazily (one-by-one) without holding 6 matrices in RAM.
      4. Explicitly cleans up intermediate buffers and triggers gc.collect().

    Returns:
        Extracted token string (32-hex token, roll number, or preview token),
        or None if no QR code could be read.
    """
    import gc
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
    del nparr  # Release buffer immediately

    if img is None:
        raise ValueError("Could not decode image bytes. Ensure a valid JPEG or PNG is supplied.")

    # 1. Downscale oversized smartphone photos (caps max dimension to 1600px)
    h, w = img.shape[:2]
    MAX_DIM = 1600
    if max(h, w) > MAX_DIM:
        scale = MAX_DIM / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        h, w = new_h, new_w

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
                    del img, grey
                    gc.collect()
                    return token

        # Try on grayscale
        barcodes_grey = zxingcpp.read_barcodes(grey, try_rotate=True, try_downscale=True, try_invert=True)
        if barcodes_grey:
            for b in barcodes_grey:
                token = extract_token_from_qr_text(b.text)
                if token:
                    logger.info("zxingcpp decoded QR on grayscale image: raw='%s' -> token='%s'", b.text, token)
                    del img, grey
                    gc.collect()
                    return token

        # Try with CLAHE (adaptive histogram equalization for glare / bad lighting)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced_grey = clahe.apply(grey)
        barcodes_enhanced = zxingcpp.read_barcodes(enhanced_grey, try_rotate=True, try_downscale=True, try_invert=True)
        del clahe, enhanced_grey
        if barcodes_enhanced:
            for b in barcodes_enhanced:
                token = extract_token_from_qr_text(b.text)
                if token:
                    logger.info("zxingcpp decoded QR on CLAHE image: raw='%s' -> token='%s'", b.text, token)
                    del img, grey
                    gc.collect()
                    return token

    except ImportError:
        logger.debug("zxingcpp not installed; falling back to OpenCV/pyzbar.")
    except Exception as exc:
        logger.warning("zxingcpp decode attempt error: %s", exc)

    # ── Lazy evaluation helper for OpenCV and pyzbar ──────────────────
    def _test_variant(variant) -> Optional[str]:
        # Engine 2: OpenCV native QRCodeDetector
        try:
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(variant)
            if data:
                tok = extract_token_from_qr_text(data)
                if tok:
                    logger.info("OpenCV QRCodeDetector decoded: raw='%s' -> token='%s'", data, tok)
                    return tok
        except Exception as exc:
            logger.debug("OpenCV QRCodeDetector error: %s", exc)

        # Engine 3: pyzbar (if available)
        try:
            from pyzbar import pyzbar as pzb  # type: ignore
            decoded_objects = pzb.decode(variant)
            for obj in decoded_objects:
                raw = obj.data.decode("utf-8", errors="ignore").strip()
                tok = extract_token_from_qr_text(raw)
                if tok:
                    logger.info("pyzbar decoded: raw='%s' -> token='%s'", raw, tok)
                    return tok
        except Exception:
            pass

        return None

    # Step A: Test grayscale and original BGR first
    for base in [grey, img]:
        found = _test_variant(base)
        if found:
            del img, grey
            gc.collect()
            return found

    # Step B: Test OTSU Binary
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    found = _test_variant(binary)
    if found:
        del img, grey, binary
        gc.collect()
        return found

    # Step C: Test Inverted Binary
    inv_binary = cv2.bitwise_not(binary)
    del binary
    found = _test_variant(inv_binary)
    if found:
        del img, grey, inv_binary
        gc.collect()
        return found
    del inv_binary

    # Step D: Test Adaptive Gaussian Threshold
    adaptive = cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    found = _test_variant(adaptive)
    if found:
        del img, grey, adaptive
        gc.collect()
        return found
    del adaptive

    # Step E: Only if image is unusually tiny (< 500px), upscale grayscale 2x
    if max(h, w) < 500:
        upscaled_grey = cv2.resize(grey, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        found = _test_variant(upscaled_grey)
        del upscaled_grey
        if found:
            del img, grey
            gc.collect()
            return found

    del img, grey
    gc.collect()
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
