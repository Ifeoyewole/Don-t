"""Read-only GCP diagnostics for JointInspect. Never prints credentials or log payloads."""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SAFE_ENV = {
    "PRIMARY_CONDITION_CLASSIFIER",
    "VERTEX_INSPECTION_MODEL",
    "VERTEX_INSPECTION_LOCATION",
    "VERTEX_SEMANTIC_GATE_ENABLED",
    "WRC_BASELINE_ENABLED",
    "JOINTINSPECT_PREVIEW_ENABLED",
}
PRESENCE_ONLY_ENV = {"WRC_BASELINE_PATH", "JOINTINSPECT_PREVIEW_MODEL_PATH"}


def _run_json(args: list[str]) -> object:
    # No shell. No raw stdout/stderr in CI logs: cloud API errors may include
    # request details, resource names, or confidential audit-log messages.
    try:
        result = subprocess.run(args, check=False, text=True, capture_output=True, timeout=35)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"GCP read command could not complete ({type(exc).__name__})") from None
    if result.returncode:
        raise RuntimeError(f"GCP read command failed (exit {result.returncode}; permissions or resource may be missing)")
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Unexpected GCP read response (not JSON)") from None


def _get_containers(service: dict) -> list[dict]:
    v1 = (((service.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers")
    v2 = ((service.get("template") or {}).get("containers"))
    return v1 or v2 or []


def summarize_service(service: dict, service_name: str) -> list[str]:
    status = service.get("status") or {}
    containers = _get_containers(service)
    env = {}
    for container in containers:
        for entry in container.get("env") or []:
            name = entry.get("name")
            if name in SAFE_ENV:
                if "value" in entry:
                    env[name] = str(entry["value"])[:100]
                else:
                    env[name] = "set via secret/reference (value withheld)"
            elif name in PRESENCE_ONLY_ENV:
                env[name] = "configured (value withheld)"
    lines = [
        f"Service: {service_name}",
        f"Ready revision: {status.get('latestReadyRevisionName') or service.get('latestReadyRevision') or 'unknown'}",
        f"Latest revision: {status.get('latestCreatedRevisionName') or service.get('latestCreatedRevision') or 'unknown'}",
        "Non-secret model configuration (live Cloud Run service spec):",
    ]
    for key in sorted(SAFE_ENV | PRESENCE_ONLY_ENV):
        lines.append(f"- {key}: {env.get(key, 'unset (application default may apply)')}")
    lines.append("Note: deployment env configuration is not proof model weights loaded or Vertex request succeeded.")
    return lines


def summarize_logs(logs: list[dict]) -> list[str]:
    severities = collections.Counter(str(log.get("severity") or "UNKNOWN") for log in logs)
    status_codes = collections.Counter(str((log.get("httpRequest") or {}).get("status") or "n/a") for log in logs)
    return [
        f"Error-level Cloud Run entries sampled (last 12h, max 40): {len(logs)}",
        f"Severities (no log messages): {dict(severities)}",
        f"HTTP status codes (no request bodies): {dict(status_codes)}",
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "region", "service"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--summary", type=Path, help="GitHub Actions step summary destination")
    args = p.parse_args(argv)
    if any(not IDENTIFIER.fullmatch(getattr(args, k)) for k in ("project", "region", "service")):
        p.error("Invalid GCP resource identifier")
    project, region, service = args.project, args.region, args.service

    lines = ["# JointInspect — GCP read-only diagnosis", "", f"Project: {project}", f"Region: {region}", ""]
    try:
        raw = _run_json([
            "gcloud", "run", "services", "describe", service, "--project", project,
            "--region", region, "--format=json",
        ])
        if not isinstance(raw, dict):
            raise RuntimeError("Invalid Cloud Run service response type")
        lines += summarize_service(raw, service)
        lines += ["", "## Recent error counts"]
        logs = _run_json([
            "gcloud", "logging", "read",
            f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service}" AND severity>=ERROR',
            "--project", project, "--freshness=12h", "--limit=40",
            "--format=json(timestamp,severity,httpRequest.status)",
        ])
        if not isinstance(logs, list):
            raise RuntimeError("Invalid Logging response type")
        lines += summarize_logs(logs)
        lines += ["", "Model load failures require runtime health and private deployment logs for root-cause verification."]
    except RuntimeError as exc:
        lines += ["", f"Read-only diagnostic failure: {exc}"]
        print("\n".join(lines))
        if args.summary:
            args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    output = "\n".join(lines) + "\n"
    print(output)
    if args.summary:
        args.summary.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
