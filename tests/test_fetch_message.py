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
    """When message is not in channel history, fetch channel parents then replies with parent ts."""
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_config.SLACK_USER_TOKEN = ""
    # Call 1: history (oldest/latest) -> empty. Call 2: history (limit=50) -> one parent. Call 3: replies(parent_ts) -> thread.
    history_empty = type("R", (), {"status_code": 200, "json": lambda *a, **k: {"ok": True, "messages": []}})()
    history_parents = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {"ok": True, "messages": [{"ts": "123.0", "reply_count": 1}]},
    })()
    replies_resp = type("R", (), {
        "status_code": 200,
        "json": lambda *a, **k: {
            "ok": True,
            "messages": [
                {"ts": "123.0", "text": "Parent"},
                {"ts": "456.0", "thread_ts": "123.0", "text": "Thread reply to translate"},
            ],
        },
    })()
    mock_post.side_effect = [history_empty, history_parents, replies_resp]
    text, reply_ts = _fetch_message("C123", "456.0")
    assert text == "Thread reply to translate"
    assert reply_ts == "123.0"
    assert mock_post.call_count == 3
    # Third call is conversations.replies with parent ts
    assert mock_post.call_args_list[2].kwargs["json"].get("ts") == "123.0"


@patch("slack_translate_bot.main.config")
def test_fetch_message_returns_none_without_token(mock_config):
    """Returns None when no token is set."""
    mock_config.SLACK_BOT_TOKEN = ""
    mock_config.SLACK_USER_TOKEN = ""
    assert _fetch_message("C123", "123.0") == (None, None)
