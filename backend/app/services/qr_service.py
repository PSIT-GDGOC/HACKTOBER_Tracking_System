"""QR Code Decode Service.

Decodes QR codes embedded in PSIT student ID card images using OpenCV and pyzbar.
All processing is fully server-side — the client NEVER sends a pre-decoded token.

Flow:
  image_bytes (raw JPG/PNG) → OpenCV grayscale + threshold → QR detection (cv2 + pyzbar)
  → find matching payload https://www.psit.ac.in/op/card-preview/<32-hex>
  → return the 32-char token
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# QR URL pattern — fixed prefix + exactly 32 lowercase hex characters
PSIT_QR_URL_PREFIX = "https://www.psit.ac.in/op/card-preview/"
PSIT_TOKEN_RE = re.compile(r"^https://www\.psit\.ac\.in/op/card-preview/([a-f0-9]{32})$", re.IGNORECASE)


def decode_qr_from_image(image_bytes: bytes) -> Optional[str]:
    """
    Decode the PSIT ID card QR code from raw image bytes.

    Tries multiple OpenCV pre-processing pipelines to maximise decode rate
    on photos taken with varying lighting, angle, and resolution.
    Uses OpenCV's native QRCodeDetector as primary and pyzbar as secondary engine.

    Returns:
        The 32-char hex token extracted from the PSIT card-preview URL,
        or None if no valid PSIT QR was found.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "QR scanning requires 'opencv-python-headless'. "
            "Run: pip install opencv-python-headless"
        ) from exc

    # Attempt to load pyzbar if available and functional on this OS
    pyzbar_mod = None
    try:
        from pyzbar import pyzbar as pzb  # type: ignore
        pyzbar_mod = pzb
    except (ImportError, OSError, FileNotFoundError, Exception) as exc:
        logger.debug("pyzbar not available or DLL missing (%s), using OpenCV native detector.", exc)

    # Decode raw bytes into a numpy array image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes. Ensure a valid JPEG or PNG is supplied.")

    detector = cv2.QRCodeDetector()

    # Pre-process image variants:
    # 1. Original
    # 2. Greyscale + OTSU binary
    # 3. Adaptive threshold
    # 4. Inverted binary
    # 5. Upscaled 2x
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    inv_binary = cv2.bitwise_not(binary)
    h, w = img.shape[:2]
    upscaled = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    variants = [img, grey, binary, adaptive, inv_binary, upscaled]

    # Engine 1: OpenCV native QRCodeDetector
    for variant in variants:
        try:
            data, _, _ = detector.detectAndDecode(variant)
            if data:
                match = PSIT_TOKEN_RE.match(data.strip())
                if match:
                    return match.group(1).lower()
        except Exception:
            pass

    # Engine 2: pyzbar (if available on system)
    if pyzbar_mod:
        for variant in variants:
            try:
                token = _try_decode_pyzbar(variant, pyzbar_mod)
                if token:
                    return token
            except Exception:
                pass

    logger.warning("QR decode: no valid PSIT card-preview QR found in uploaded image.")
    return None


def _try_decode_pyzbar(img, pyzbar) -> Optional[str]:
    """Run pyzbar on a single image variant and return the first matching PSIT token."""
    decoded_objects = pyzbar.decode(img)
    for obj in decoded_objects:
        raw = obj.data.decode("utf-8", errors="ignore").strip()
        match = PSIT_TOKEN_RE.match(raw)
        if match:
            return match.group(1).lower()  # always return lowercase hex
    return None


def validate_psit_qr_token(token: str) -> bool:
    """
    Validate that a decoded QR token is exactly 32 lowercase hex characters.
    Returns True if valid, False otherwise.
    """
    return bool(re.fullmatch(r"[a-f0-9]{32}", token.strip().lower()))


def build_psit_card_url(token: str) -> str:
    """Build the full PSIT card-preview URL from a 32-char token."""
    return f"{PSIT_QR_URL_PREFIX}{token.strip().lower()}"
