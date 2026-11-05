"""Read-only GCP diagnostics must not print env secrets or raw log payloads."""

from scripts.ops.gcp_readonly_diagnostics import summarize_logs, summarize_service


def test_public_summary_only_whitelisted_settings():
    service = {
        "status": {
            "latestReadyRevisionName": "pipe-joint-api-00013-xyz",
            "latestCreatedRevisionName": "pipe-joint-api-00014-abc",
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [{
                        "env": [
                            {"name": "PRIMARY_CONDITION_CLASSIFIER", "value": "inspect_view"},
                            {"name": "VERTEX_INSPECTION_MODEL", "value": "gemini-3.1-pro-preview"},
                            {"name": "GOOGLE_API_KEY", "value": "TOP-SECRET-DO-NOT-LOG"},
                            {"name": "JOINTINSPECT_PREVIEW_MODEL_PATH", "value": "gs://private/model.ckpt"},
                        ],
                    }],
                },
            },
        },
    }
    output = "\n".join(summarize_service(service, "pipe-joint-api"))
    assert "inspect_view" in output
    assert "gemini-3.1-pro-preview" in output
    assert "TOP-SECRET-DO-NOT-LOG" not in output
    assert "gs://private/model.ckpt" not in output
    assert "configured (value withheld)" in output


def test_logs_hide_message_payloads():
    payloads = [
        {"severity": "ERROR", "httpRequest": {"status": 503}, "textPayload": "key=LEAK-ME-NOT"},
        {"severity": "CRITICAL", "jsonPayload": {"password": "HIDDEN-FOREVER"}},
    ]
    output = "\n".join(summarize_logs(payloads))
    assert "ERROR" in output
    assert "503" in output
    assert "LEAK-ME-NOT" not in output
    assert "HIDDEN-FOREVER" not in output
