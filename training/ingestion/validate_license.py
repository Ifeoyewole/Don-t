"""Conservative license-name screening for dataset ingestion.

A static screen CANNOT establish provenance, ownership, or legal clearance.
Unknown license names, noncommercial terms, copyleft for a proprietary target,
and undeclared privately owned sources all fail closed.
"""

from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel


class LicenseAuditResult(BaseModel):
    is_commercial_valid: bool
    commercial_training_allowed: bool
    commercial_deployment_allowed: bool
    viral_copyleft_detected: bool
    attribution_required: bool
    required_attribution_notice: str
    rejection_reasons: List[str]


def audit_license(
    license_name: str,
    license_text: str = "",
    *,
    approved_owned_source: bool = False,
    rights_document_reference: str | None = None,
) -> LicenseAuditResult:
    """Evaluate conservative license terms, never defaulting unknown to valid.

    IMPORTANT: approved_owned_source is a separate internal-record assertion;
    it is not verified legal title. The commercial model gate requires an
    independent signed evidence review before production promotion.
    """
    label = (license_name or "").lower().strip()
    terms = label + " " + (license_text or "").lower()
    restrictions = [
        r"non[\s-]?commercial", r"noncommerical", r"not for commercial",
        r"research[\s-]+(use[\s-]+)?only", r"academic[\s-]+only",
        r"\bcc[\s-]*by[\s-]*nc\b", r"\bcc[\s-]*by[\s-]*nd\b",
    ]
    copyleft = [
        r"\bagpl\b", r"\bgpl(?:v|[\s-])?\d?\b",
        r"\bshare[\s-]?alike\b", r"\bcc[\s-]*by[\s-]*sa\b",
    ]
    has_restricted = any(re.search(p, terms) for p in restrictions)
    has_copyleft = any(re.search(p, terms) for p in copyleft)
    permissive = any(
        re.search(p, label) for p in (
            r"\bapache[\s-]*(?:license[\s,]*)?(?:2(?:\.0)?)\b",
            r"\bmit\s*(?:license)?\b",
            r"\bbsd[\s-]*(?:2|3)[\s-]*clause\b",
            r"\bisc\s*(?:license)?\b",
            r"\bcc[\s-]*by[\s-]*4(?:\.0)?\b",
            r"\bcreative commons attribution 4(?:\.0)?\b",
            r"\bcc0[\s-]*1(?:\.0)?\b",
            r"\bpublic domain\b",
        )
    )
    is_owned = "proprietary" in label or "in-house" in label
    has_owned_evidence = bool(
        approved_owned_source and isinstance(rights_document_reference, str)
        and rights_document_reference.strip()
        and rights_document_reference.strip().lower() not in
        {"pending", "unknown", "none", "n/a"}
    )
    permitted_name = permissive or (is_owned and has_owned_evidence)
    reasons: list[str] = []
    if has_restricted:
        reasons.append("Noncommercial, no-derivatives, or research-only restriction detected.")
    if has_copyleft:
        reasons.append("Copyleft/share-alike detected; proprietary deployment not pre-cleared.")
    if not permitted_name:
        reasons.append("License not on documented permissive allowlist or owned rights not evidenced.")
    approved = permitted_name and not has_restricted and not has_copyleft
    attribution = approved and (not is_owned and not re.search(r"\bcc0\b|public domain", label))
    return LicenseAuditResult(
        is_commercial_valid=approved,
        commercial_training_allowed=approved,
        commercial_deployment_allowed=approved,
        viral_copyleft_detected=has_copyleft,
        attribution_required=bool(attribution),
        required_attribution_notice=(f"Preserve applicable attribution/license notices: {license_name}."
                                     if attribution else ""),
        rejection_reasons=reasons,
    )
