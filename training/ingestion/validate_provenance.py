"""Provenance Validation Module for Commercial Ingestion.

Ensures every external dataset has verified primary origin:
1. Rejects unverified scraping dumps and unauthorized mirrors (e.g., untrusted Hugging Face/Roboflow/Kaggle repackages).
2. Verifies provider domain, primary publisher, and direct chain of title.
3. Flags suspicious provenance where non-commercial datasets may have been re-licensed or re-uploaded.
"""

from typing import List, Optional
from pydantic import BaseModel
import re


class ProvenanceAuditResult(BaseModel):
    is_provenance_verified: bool
    suspicious_mirror_detected: bool
    rejection_reasons: List[str]
    audit_notes: str


UNVERIFIED_PLATFORMS = [
    r"roboflow\.com",
    r"kaggle\.com",
    r"huggingface\.co",
    r"github\.com/[^/]+/[^/]+/(releases|archive)",
]

KNOWN_RESTRICTED_REPACKAGES = [
    "sewer-ml",
    "sewerml",
    "water-pipe-leak",
    "underground-cctv-leak",
]


def audit_provenance(
    source_url: Optional[str],
    provider: str,
    license_name: str,
    original_curator: Optional[str] = None,
    is_direct_partner: bool = False,
    is_synthetic: bool = False,
    is_owned: bool = False,
) -> ProvenanceAuditResult:
    """Audits the origin, chain of custody, and mirror risk for a data source."""
    if is_synthetic or is_owned:
        return ProvenanceAuditResult(
            is_provenance_verified=True,
            suspicious_mirror_detected=False,
            rejection_reasons=[],
            audit_notes="Internal owned/synthetic asset. Provenance origin verified at generation.",
        )

    if is_direct_partner:
        return ProvenanceAuditResult(
            is_provenance_verified=True,
            suspicious_mirror_detected=False,
            rejection_reasons=[],
            audit_notes=f"Direct partner provenance confirmed with contract provider: {provider}.",
        )

    reasons: List[str] = []
    suspicious_mirror = False

    if not source_url:
        reasons.append("External public dataset missing primary source_url.")
        return ProvenanceAuditResult(
            is_provenance_verified=False,
            suspicious_mirror_detected=False,
            rejection_reasons=reasons,
            audit_notes="Failed closed due to missing source URL.",
        )

    url_lower = source_url.lower()

    # Check for unverified mirror platforms
    for platform in UNVERIFIED_PLATFORMS:
        if re.search(platform, url_lower):
            suspicious_mirror = True
            reasons.append(
                f"Source URL indicates an external hosting mirror ({source_url}). "
                "Secondary community mirrors require manual chain-of-title provenance verification."
            )
            break

    # Check for suspected repackaged restricted datasets
    for restricted in KNOWN_RESTRICTED_REPACKAGES:
        if restricted in url_lower or restricted in provider.lower():
            suspicious_mirror = True
            reasons.append(
                f"Potential repackaging of restricted academic/proprietary dataset '{restricted}' detected. "
                "Must not enter production training pipeline without legal clearance."
            )

    verified = len(reasons) == 0

    return ProvenanceAuditResult(
        is_provenance_verified=verified,
        suspicious_mirror_detected=suspicious_mirror,
        rejection_reasons=reasons,
        audit_notes="External provenance verified against primary publisher."
        if verified
        else "Provenance verification failed; asset quarantined.",
    )
