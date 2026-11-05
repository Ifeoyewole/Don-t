"""Stream one approved remote ZIP directly into GCS from a GCP worker."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from urllib.parse import urlsplit

import google.auth
import requests
from google.cloud import storage
from google.auth.transport.requests import AuthorizedSession
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SECRET_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def access_secret(project: str, secret: str, version: str = "latest") -> str:
    """Read a Secret Manager value without putting it in Batch environment data."""
    if not SECRET_NAME.fullmatch(secret) or not SECRET_NAME.fullmatch(version):
        raise ValueError("Secret and version must be simple Secret Manager identifiers")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    endpoint = (
        f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets/"
        f"{secret}/versions/{version}:access"
    )
    response = AuthorizedSession(credentials).get(endpoint, timeout=30)
    response.raise_for_status()
    encoded = response.json().get("payload", {}).get("data")
    if not encoded:
        raise RuntimeError(f"Secret Manager returned no payload for {secret}")
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def stage(url: str, project: str, bucket: str, object_name: str, max_bytes: int,
          reuse_existing: bool = False, username: str | None = None,
          password: str | None = None) -> dict:
    parsed = urlsplit(url)
    allowed_hosts = {"sciencedata.dk", "www.sciencedata.dk"}
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise ValueError("Archive URL must use HTTPS on an approved Sewer-ML host")
    if not object_name.endswith(".zip") or object_name.startswith("/") or ".." in object_name.split("/"):
        raise ValueError("A safe .zip GCS object path is required")

    digest = hashlib.sha256(url.encode()).hexdigest()
    blob = storage.Client(project=project).bucket(bucket).blob(object_name)
    if reuse_existing and blob.exists():
        blob.reload()
        if (blob.metadata or {}).get("source_url_sha256") != digest or not blob.size:
            raise RuntimeError(f"Existing archive provenance mismatch: gs://{bucket}/{object_name}")
        return {"gcs_uri": f"gs://{bucket}/{object_name}", "object": object_name,
                "generation": int(blob.generation), "bytes": int(blob.size),
                "source_url_sha256": digest, "reused": True}

    auth = (username or "sewer-ml", password) if password else None
    retry = Retry(
        total=6,
        connect=6,
        read=2,
        status=4,
        backoff_factor=5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    with session.get(url, stream=True, allow_redirects=False, timeout=(60, 900), auth=auth,
                     headers={"Accept-Encoding": "identity"}) as response:
        if response.is_redirect:
            raise RuntimeError("Archive redirects are not accepted; approve the final HTTPS URL explicitly")
        response.raise_for_status()
        length = int(response.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_bytes:
            raise RuntimeError(f"Archive size must be known and no larger than {max_bytes} bytes")
        blob.metadata = {"source_url_sha256": digest, "execution_allowed": "false"}
        blob.upload_from_file(response.raw, size=length, content_type="application/zip",
                              rewind=False, if_generation_match=0, timeout=900)
        blob.reload()
    return {"gcs_uri": f"gs://{bucket}/{object_name}", "object": object_name,
            "generation": int(blob.generation), "bytes": int(blob.size),
            "source_url_sha256": digest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--object", required=True)
    parser.add_argument("--max-bytes", type=int, default=50 * 1024**3)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--username", default="sewer-ml")
    parser.add_argument("--password-env", default="SEWER_ML_DOWNLOAD_PASSWORD")
    parser.add_argument("--password-secret")
    parser.add_argument("--password-secret-version", default="latest")
    parser.add_argument("--output", default="/workspace/staged-archive.json")
    args = parser.parse_args()
    password = (access_secret(args.project, args.password_secret, args.password_secret_version)
                if args.password_secret else os.environ.get(args.password_env))
    if not password:
        raise RuntimeError("Required archive credential is unavailable")
    result = stage(args.url, args.project, args.bucket, args.object, args.max_bytes,
                   reuse_existing=args.reuse_existing, username=args.username, password=password)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
