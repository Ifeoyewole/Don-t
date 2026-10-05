"""License Validation Module for Commercial Ingestion.

Audits license clauses, terms, and conditions before any asset can enter quarantine review:
1. Detects Non-Commercial riders (CC-NC, academic-only, research-use-only).
2. Verifies commercial training and deployment permissions.
3. Detects Viral Copyleft riders (GPL, AGPL, CC-BY-SA) that could compromise proprietary IP.
4. Validates required attribution clauses.
"""

from typing import Dict, List, Tuple
from pydantic import BaseModel


class LicenseAuditResult(BaseModel):
    is_commercial_valid: bool
    commercial_training_allowed: bool
    commercial_deployment_allowed: bool
    viral_copyleft_detected: bool
    attribution_required: bool
    required_attribution_notice: str
    rejection_reasons: List[str]


def audit_license(license_name: str, license_text: str = "") -> LicenseAuditResult:
    """Performs static and textual clause analysis on a proposed dataset license."""
    lic_lower = (license_name + " " + license_text).lower()
    reasons = []

    # 1. Non-commercial detection
    nc_patterns = ["non-commercial", "noncommercial", "academic only", "research only", "not for commercial"]
    has_nc = any(p in lic_lower for p in nc_patterns)
    if has_nc:
        reasons.append("Non-commercial restriction detected in license terms.")

    # 2. Viral copyleft detection
    copyleft_patterns = ["agpl", "gpl v", "gpl-", "share-alike", "sharealike", "cc-by-sa"]
    has_copyleft = any(p in lic_lower for p in copyleft_patterns)
    if has_copyleft:
        reasons.append("Viral copyleft or share-alike restriction detected.")

    # 3. Commercial approval verification
    commercial_ok = not has_nc and not has_copyleft

    # 4. Attribution check
    attr_patterns = ["cc-by", "mit", "apache", "attribution", "bsd"]
    attr_required = any(p in lic_lower for p in attr_patterns) and not ("cc0" in lic_lower or "public domain" in lic_lower or "in-house" in lic_lower)

    return LicenseAuditResult(
        is_commercial_valid=commercial_ok,
        commercial_training_allowed=commercial_ok,
        commercial_deployment_allowed=commercial_ok,
        viral_copyleft_detected=has_copyleft,
        attribution_required=attr_required,
        required_attribution_notice=f"Dataset licensed under {license_name}." if attr_required else "",
        rejection_reasons=reasons,
    )
