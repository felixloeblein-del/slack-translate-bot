"""
Tests for _fetch_message: channel messages and thread replies.
"""

from unittest.mock import patch

import pytest

from slack_translate_bot.main import _fetch_message


@patch("httpx.post")
@patch("slack_translate_bot.main.config")
def test_fetch_message_from_history(mock_config, mock_post):
    """Channel message is fetched via conversations.history."""
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "ok": True,
        "messages": [{"ts": "123.0", "text": "Hello world"}],
    }
    text, reply_ts = _fetch_message("C123", "123.0")
    assert text == "Hello world"
    assert reply_ts == "123.0"
    mock_post.assert_called_once()
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json.get("channel") == "C123"
    assert "oldest" in call_json  # history


@patch("httpx.post")
@patch("slack_translate_bot.main.config")
def test_fetch_message_from_replies_when_not_in_history(mock_config, mock_post):
    """When message is not in channel history, fetch it directly via conversations.replies(ts)."""
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_config.SLACK_USER_TOKEN = "xoxp-fake"
    # Call 1: history (oldest/latest) -> empty. Call 2: replies(ts) -> reply message.
    history_empty = type("R", (), {"status_code": 200, "json": lambda *a, **k: {"ok": True, "messages": []}})()
    replies_resp = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {
            "ok": True,
            "messages": [
                {"ts": "456.0", "thread_ts": "123.0", "text": "Thread reply to translate"},
            ],
        },
    })()
    mock_post.side_effect = [history_empty, replies_resp]
    text, reply_ts = _fetch_message("C123", "456.0")
    assert text == "Thread reply to translate"
    assert reply_ts == "123.0"
    assert mock_post.call_count == 2
    # Second call is conversations.replies with message ts
    replies_call = mock_post.call_args_list[1]
    assert replies_call.kwargs["json"].get("ts") == "456.0"
    assert replies_call.kwargs["headers"]["Authorization"] == "Bearer xoxp-fake"


@patch("httpx.post")
@patch("slack_translate_bot.main.config")
def test_fetch_message_falls_back_to_parent_discovery_on_invalid_arguments(mock_config, mock_post):
    """When replies(reply_ts) fails, resolve parent via history and fetch from replies(parent_ts)."""
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_config.SLACK_USER_TOKEN = "xoxp-fake"

    history_empty = type("R", (), {"status_code": 200, "json": lambda *a, **k: {"ok": True, "messages": []}})()
    replies_invalid = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {"ok": False, "error": "invalid_arguments"},
    })()
    history_parents = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {"ok": True, "messages": [{"ts": "123.0", "reply_count": 3}]},
    })()
    replies_parent = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {
            "ok": True,
            "messages": [
                {"ts": "123.0", "text": "Parent"},
                {"ts": "456.0", "thread_ts": "123.0", "text": "Thread reply via fallback"},
            ],
        },
    })()
    mock_post.side_effect = [history_empty, replies_invalid, history_parents, replies_parent]

    text, reply_ts = _fetch_message("C123", "456.0")
    assert text == "Thread reply via fallback"
    assert reply_ts == "123.0"
    assert mock_post.call_count == 4
    # Fallback history lookup should use user token when available.
    history_fallback_call = mock_post.call_args_list[2]
    assert history_fallback_call.kwargs["headers"]["Authorization"] == "Bearer xoxp-fake"
    # Final fallback replies call should anchor on the parent ts.
    replies_fallback_call = mock_post.call_args_list[3]
    assert replies_fallback_call.kwargs["json"].get("ts") == "123.0"


@patch("slack_translate_bot.main.config")
def test_fetch_message_returns_none_without_token(mock_config):
    """Returns None when no token is set."""
    mock_config.SLACK_BOT_TOKEN = ""
    mock_config.SLACK_USER_TOKEN = ""
    assert _fetch_message("C123", "123.0") == (None, None)
