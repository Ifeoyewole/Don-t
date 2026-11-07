# Inspect View — commercial permission and production status

**Record date:** 2026-11-07  
**Source of new claim:** JointInspect project owner, communicated in the development discussion.  
**Legal-document status:** The project owner reports direct commercial authorization
from the rights holders, but the agreement/confirmation is not yet archived
in this repository. The provider's server is currently unavailable according
to the owner, and the owner is seeking renewed access to the agreement.

## Separate facts and flags

| Dimension | Status | Evidence or limitation |
|---|---|---|
| Permission to use Inspect View commercially | **YES — PROJECT-OWNER REPORTED** | Owner reports direct go-ahead from rights holders; independent documentary verification pending |
| Permission for commercial production deployment | **YES — PROJECT-OWNER REPORTED** | Same owner-reported authorization; no signed grant or exact terms available in this repository |
| Inspect View was deployed to the production Cloud Run service | **TRUE — HISTORICAL DEPLOYMENT RECORD** | `docs/ml/deployments/INSPECT_VIEW_2026-11-04.md` documents the revision and checks; this is not live status verification on 2026-11-07 |
| General Sewer-ML public dataset license | **CC BY-NC-SA 4.0** | The upstream published license remains unchanged. The owner-reported private permission may create a separate right, but its scope has not been independently verified |
| Written commercial permission terms on file | **PENDING** | Obtain rights-holder identity, permitted uses, specific dataset/derivative/model scope, dates, whether sublicense/redistribution is allowed, and evidence reference |
| Locked held-out Inspect View defect accuracy | **NOT YET VERIFIED** | No performance approval implied; unsupported classes and fail-closed engineering gates remain |
| Engineering model `production_approved` | **FALSE — VALIDATION GATE** | This is specifically engineering reliability acceptance, not denial of owner-reported commercial permission |
| Combined Inspect View + SAM 2.1 production inference | **NOT YET ENABLED** | Research adapter/test stage; no commercial deployment of the new fusion asserted |

## Intended production architecture

```
INSPECT VIEW (commercial use permitted as reported by owner)
     |
     |--- advisory condition/class evidence and version/provenance
     |
SAM 2.1 (official Meta checkpoint; Apache-2.0 publisher claim)
     |
     |--- promptable image masks / region suggestions
     v
JOINTINSPECT (original OpenCV) -> rough seam / circle / ellipse pixel geometry
     |
     v
SERVER-OWNED SPATIAL CALIBRATION -> authorized mm where geometry is reliable
     |
     v
INSPECTOR REVIEW -> evidence report; unsupported classes never generate PASS
```

The model-combination goal is not to remove Inspect View, retrain it from
scratch unnecessarily, or assume SAM 2.1 is a sewer defect classifier. Keep
each model's identity and exact weight provenance in the fusion result.

## Required rights-verification follow-up (without blocking local research)

1. Recover the owner/rightsholder correspondence or signed agreement when their
   server is accessible again; store the signed evidence outside Git and add a
   private evidence/ticket ID to the release manifest.
2. Determine whether the grant covers only Inspect View's implementation,
   its r5 checkpoint, Sewer-ML-derived ancestors, underlying licensed dataset
   training/deployment, derivatives, commercial customers, and any distribution
   to third parties. Those are distinct rights.
3. Preserve mandatory copyright/attribution and third-party notices. The
   publicly posted Sewer-ML CC BY-NC-SA license has not changed.
4. An authorized human reviewer may set a dedicated **rights-verified** flag
   after reading the real terms. Automated rules must not mistake this
   project-owner report for independently verified legal evidence.
5. Keep model accuracy, missing-class validation, camera calibration, and
   deployment readiness separately gated. Neither a license grant nor a loaded
   checkpoint proves engineering reliability.

**This record corrects an earlier assumption:** documentation must no longer
categorically claim that Inspect View lacks commercial permission. It should
state **owner-reported commercial authorization**, plus the above limitations.
Do not globally replace every `production_approved=false`, because those
flags are also used for accuracy/release gating and other unrelated datasets.
