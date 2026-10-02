"""
─────────────────────────────────────────────────────────────────────────────
File        : core/services/cloudinary_service.py
Purpose     : Cloudinary storage uploader with local filesystem fallback.

Uploads generated prescription PDF files to Cloudinary cloud storage.
If Cloudinary credentials are not set in environment or network upload fails,
gracefully falls back to local disk storage (data/prescriptions/).
─────────────────────────────────────────────────────────────────────────────
"""

import io
import os
from typing import Optional, Tuple
import cloudinary
import cloudinary.uploader

from common.logger import get_logger

logger = get_logger(__name__)

def get_local_prescription_dir() -> str:
    override = os.getenv("LOCAL_PRESCRIPTION_DIR")
    if override:
        return override
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "prescriptions",
    )


LOCAL_PRESCRIPTION_DIR = get_local_prescription_dir()




def is_cloudinary_configured() -> bool:
    """Check if Cloudinary environment variables are fully present."""
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    return bool(cloud_name and api_key and api_secret)


def configure_cloudinary():
    """Configure Cloudinary SDK if credentials exist."""
    if is_cloudinary_configured():
        cloudinary.config(
            cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
            api_key=os.environ.get("CLOUDINARY_API_KEY"),
            api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
            secure=True,
        )


async def upload_prescription_pdf(
    pdf_bytes: bytes,
    prescription_id: str,
) -> Tuple[str, Optional[str]]:
    """
    Uploads prescription PDF bytes to Cloudinary or saves locally as fallback.

    Args:
        pdf_bytes: Raw binary bytes of generated PDF.
        prescription_id: MongoDB string ObjectId of prescription.

    Returns:
        Tuple[str, Optional[str]]: (pdf_url, cloudinary_public_id)
    """
    if is_cloudinary_configured():
        try:
            configure_cloudinary()
            logger.info("Uploading prescription %s PDF to Cloudinary...", prescription_id)
            result = cloudinary.uploader.upload(
                file=io.BytesIO(pdf_bytes),
                public_id=f"citycare_prescriptions/{prescription_id}",
                resource_type="raw",
                format="pdf",
                overwrite=True,
            )
            secure_url = result.get("secure_url") or result.get("url")
            public_id = result.get("public_id")
            logger.info("Cloudinary upload successful! URL: %s", secure_url)
            return secure_url, public_id
        except Exception as err:
            logger.warning("Cloudinary upload failed for prescription %s: %s. Falling back to local storage.", prescription_id, str(err))

    # ── Local Disk Storage Fallback ──
    local_dir = get_local_prescription_dir()
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, f"{prescription_id}.pdf")
    with open(local_path, "wb") as f:
        f.write(pdf_bytes)

    local_url = f"/api/v1/patient/prescriptions/{prescription_id}/pdf-file"
    logger.info("Prescription PDF stored locally at %s. Serving URL: %s", local_path, local_url)
    return local_url, None
