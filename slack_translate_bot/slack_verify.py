"""Verify that incoming HTTP requests are signed by Slack (HMAC-SHA256)."""

import hashlib
import hmac
import time
from typing import Optional

from . import config


def verify_slack_request(
    body: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    max_age_seconds: Optional[int] = None,
) -> bool:
    """
    Verify the request using X-Slack-Signature and X-Slack-Request-Timestamp.
    Returns True if the request is valid and not too old (replay protection).
    """
    if not config.SLACK_SIGNING_SECRET or not signature or not timestamp:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    max_age = max_age_seconds if max_age_seconds is not None else config.SLACK_REQUEST_MAX_AGE_SECONDS
    if abs(time.time() - ts) > max_age:
        return False
    sig_basestring = f"v0:{timestamp}:".encode("utf-8") + body
    computed = "v0=" + hmac.new(
        config.SLACK_SIGNING_SECRET.encode("utf-8"),
        sig_basestring,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)
