"""
Tests for reaction-trigger edit handling (message_changed).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import slack_translate_bot.main as main_mod
from slack_translate_bot.main import app


@pytest.fixture(autouse=True)
def clear_processed_cache():
    main_mod._processed.clear()
    yield
    main_mod._processed.clear()


def _message_changed_payload(*, reactions):
    return {
        "type": "event_callback",
        "event": {
            "type": "message",
            "subtype": "message_changed",
            "channel": "C123",
            "event_ts": "1700000000.2222",
            "message": {
                "type": "message",
                "user": "U123",
                "ts": "111.001",
                "thread_ts": "111.000",
                "text": "Hello world",
                "edited": {"user": "U123", "ts": "1700000000.1111"},
                "reactions": reactions,
            },
            "previous_message": {
                "type": "message",
                "user": "U123",
                "ts": "111.001",
                "thread_ts": "111.000",
                "text": "Hello old",
            },
        },
    }


@patch("slack_translate_bot.main._post_thread_reply", return_value=True)
@patch("slack_translate_bot.main._translate_headline_and_body", return_value="Hallo Welt")
@patch("slack_translate_bot.main.verify_slack_request", return_value=True)
@patch("slack_translate_bot.main.config")
def test_message_changed_with_trigger_reaction_posts_updated_translation(
    mock_config, _mock_verify, mock_translate, mock_post_reply
):
    mock_config.TRANSLATE_TRIGGER = "reaction"
    mock_config.REACTION_TRIGGER_EMOJI = "de"
    mock_config.CHANNEL_IDS_LIST = []

    payload = _message_changed_payload(reactions=[{"name": "de", "count": 1}])
    with TestClient(app) as client:
        res = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )

    assert res.status_code == 200
    mock_translate.assert_called_once_with("Hello world")
    mock_post_reply.assert_called_once_with("C123", "111.000", "Hallo Welt")


@patch("slack_translate_bot.main._post_thread_reply", return_value=True)
@patch("slack_translate_bot.main._translate_headline_and_body", return_value="Hallo Welt")
@patch("slack_translate_bot.main.verify_slack_request", return_value=True)
@patch("slack_translate_bot.main.config")
def test_message_changed_without_trigger_reaction_is_skipped(
    mock_config, _mock_verify, mock_translate, mock_post_reply
):
    mock_config.TRANSLATE_TRIGGER = "reaction"
    mock_config.REACTION_TRIGGER_EMOJI = "de"
    mock_config.CHANNEL_IDS_LIST = []

    payload = _message_changed_payload(reactions=[{"name": "thumbsup", "count": 1}])
    with TestClient(app) as client:
        res = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )

    assert res.status_code == 200
    mock_translate.assert_not_called()
    mock_post_reply.assert_not_called()


@patch("slack_translate_bot.main._post_thread_reply", return_value=True)
@patch("slack_translate_bot.main._translate_headline_and_body", return_value="Hallo Welt")
@patch("slack_translate_bot.main.verify_slack_request", return_value=True)
@patch("slack_translate_bot.main.config")
def test_message_changed_same_edit_event_is_idempotent(
    mock_config, _mock_verify, _mock_translate, mock_post_reply
):
    mock_config.TRANSLATE_TRIGGER = "reaction"
    mock_config.REACTION_TRIGGER_EMOJI = "de"
    mock_config.CHANNEL_IDS_LIST = []

    payload = _message_changed_payload(reactions=[{"name": "de", "count": 1}])
    with TestClient(app) as client:
        res1 = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )
        res2 = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert mock_post_reply.call_count == 1


@patch("httpx.post")
@patch("slack_translate_bot.main._post_thread_reply", return_value=True)
@patch("slack_translate_bot.main._translate_headline_and_body", return_value="Hallo Welt")
@patch("slack_translate_bot.main.verify_slack_request", return_value=True)
@patch("slack_translate_bot.main.config")
def test_message_changed_fetches_reactions_when_not_in_payload(
    mock_config, _mock_verify, _mock_translate, mock_post_reply, mock_http_post
):
    mock_config.TRANSLATE_TRIGGER = "reaction"
    mock_config.REACTION_TRIGGER_EMOJI = "de"
    mock_config.CHANNEL_IDS_LIST = []
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_http_post.return_value.status_code = 200
    mock_http_post.return_value.json.return_value = {
        "ok": True,
        "type": "message",
        "message": {"reactions": [{"name": "de", "count": 1}]},
    }

    payload = _message_changed_payload(reactions=None)
    with TestClient(app) as client:
        res = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )

    assert res.status_code == 200
    assert mock_http_post.call_count == 1
    call = mock_http_post.call_args
    assert call.args[0] == "https://slack.com/api/reactions.get"
    assert call.kwargs["data"]["channel"] == "C123"
    assert call.kwargs["data"]["timestamp"] == "111.001"
    assert mock_post_reply.call_count == 1


@patch("httpx.post")
@patch("slack_translate_bot.main._post_thread_reply", return_value=True)
@patch("slack_translate_bot.main._translate_headline_and_body", return_value="Hallo Welt")
@patch("slack_translate_bot.main.verify_slack_request", return_value=True)
@patch("slack_translate_bot.main.config")
def test_message_changed_skips_when_live_reactions_do_not_include_trigger(
    mock_config, _mock_verify, mock_translate, mock_post_reply, mock_http_post
):
    mock_config.TRANSLATE_TRIGGER = "reaction"
    mock_config.REACTION_TRIGGER_EMOJI = "de"
    mock_config.CHANNEL_IDS_LIST = []
    mock_config.SLACK_BOT_TOKEN = "xoxb-fake"
    mock_http_post.return_value.status_code = 200
    mock_http_post.return_value.json.return_value = {
        "ok": True,
        "type": "message",
        "message": {"reactions": [{"name": "white_check_mark", "count": 1}]},
    }

    payload = _message_changed_payload(reactions=None)
    with TestClient(app) as client:
        res = client.post(
            "/slack/events",
            json=payload,
            headers={
                "x-slack-signature": "v0=fake",
                "x-slack-request-timestamp": "1700000000",
            },
        )

    assert res.status_code == 200
    mock_translate.assert_not_called()
    mock_post_reply.assert_not_called()
