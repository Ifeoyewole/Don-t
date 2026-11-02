import base64

import pytest

import stage_remote_archive


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_access_secret_uses_authorized_session_without_environment(monkeypatch):
    monkeypatch.setattr(stage_remote_archive.google.auth, "default", lambda scopes: (object(), None))
    requested = {}

    class Session:
        def __init__(self, credentials):
            requested["credentials"] = credentials

        def get(self, url, timeout):
            requested.update(url=url, timeout=timeout)
            return Response({"payload": {"data": base64.b64encode(b"private").decode()}})

    monkeypatch.setattr(stage_remote_archive, "AuthorizedSession", Session)
    assert stage_remote_archive.access_secret("project-1", "archive-password") == "private"
    assert requested["url"].endswith(
        "/projects/project-1/secrets/archive-password/versions/latest:access"
    )
    assert requested["timeout"] == 30


@pytest.mark.parametrize("secret", ["../secret", "secret/name", "secret:latest", ""])
def test_access_secret_rejects_unsafe_identifier(secret):
    with pytest.raises(ValueError):
        stage_remote_archive.access_secret("project-1", secret)
