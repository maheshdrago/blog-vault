"""Tests for privacy boundaries applied before Langfuse export."""

from backend.app.telemetry import mask_trace_data


def test_mask_trace_data_redacts_content_and_credentials() -> None:
    """Auth values and authored HTML must never enter trace payloads."""
    masked = mask_trace_data(
        {
            "slug": "safe-post",
            "html": "<p>private draft</p>",
            "nested": {
                "authorization": "Bearer private-value",
                "message": "request used github_pat_secret-value",
            },
        }
    )

    assert masked == {
        "slug": "safe-post",
        "html": "[REDACTED]",
        "nested": {
            "authorization": "[REDACTED]",
            "message": "request used [REDACTED]",
        },
    }
