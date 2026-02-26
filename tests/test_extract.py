"""
Tests for content extraction: request line is skipped, only headline + body are translated.
Matches the l10n format in .cursor/rules/l10n-translation-format.mdc
"""

import pytest

from slack_translate_bot import config
from slack_translate_bot.main import _extract_content_to_translate, _split_headline_body

# Phrases that trigger "only translate after this" (same as config default)
EXTRACT_PHRASES = [
    "Can you please assist us with a translation of the following:",
    "Can you please assist with translating the following:",
    "Can you translate the following:",
    "Please translate the below:",
    "translation of the following:",
    "the following:",
]


@pytest.fixture(autouse=True)
def set_extract_phrases(monkeypatch):
    """Use a fixed phrase list so tests don't depend on env."""
    phrases = sorted(EXTRACT_PHRASES, key=len, reverse=True)
    monkeypatch.setattr(config, "EXTRACT_PHRASES_LIST", phrases)


def test_extract_skips_request_line_single_block():
    """When message has @here request + headline + body, only headline and body are extracted."""
    msg = (
        "@here Can you please assist us with a translation of the following:\n"
        ":loudspeaker: Precious metals rally\n"
        "Gold +2.4%, Silver +6% rebound from one-week lows on safe-haven demand."
    )
    got = _extract_content_to_translate(msg)
    assert "@here" not in got
    assert "Can you please assist" not in got
    assert got.strip().startswith(":loudspeaker:")
    assert "Precious metals rally" in got
    assert "Gold +2.4%" in got


def test_extract_skips_request_line_alternate_phrase():
    """Alternate request phrase still strips preamble."""
    msg = (
        "@here Can you please assist with translating the following:\n"
        ":chart_with_downwards_trend: DBX tumbles\n"
        "Dropbox drops 4.2% as soft outlook overshadows modest earnings beat."
    )
    got = _extract_content_to_translate(msg)
    assert got.strip().startswith(":chart_with_downwards_trend:")
    assert "DBX tumbles" in got
    assert "Dropbox drops" in got


def test_extract_two_headline_body_pairs():
    """Multiple headline+body pairs in one message: all after the phrase are kept."""
    msg = (
        "@here Can you please assist with translating the following:\n"
        ":newspaper: Precious metals rush\n"
        "Silver +3%, Gold +1% as intensifying US-Iran tensions drive safe-haven demand.\n"
        ":rocket: OPEN reignited\n"
        "Opendoor Technologies jumps 19% after massive revenue beat and upbeat guidance."
    )
    got = _extract_content_to_translate(msg)
    assert "@here" not in got
    assert ":newspaper: Precious metals rush" in got
    assert "Silver +3%" in got
    assert ":rocket: OPEN reignited" in got
    assert "Opendoor Technologies" in got


def test_extract_no_phrase_returns_full_text():
    """If no preamble phrase is found, full text is returned (no stripping)."""
    msg = (
        ":loudspeaker: Precious metals rally\n"
        "Gold +2.4%, Silver +6% rebound."
    )
    got = _extract_content_to_translate(msg)
    assert got == msg


def test_extract_empty_after_phrase():
    """If the phrase appears but nothing after, implementation returns full text (no empty)."""
    msg = "@here Can you please assist us with a translation of the following:"
    got = _extract_content_to_translate(msg)
    assert got is not None
    assert "following" in got or "translation" in got


def test_extract_case_insensitive():
    """Matching is case-insensitive."""
    msg = (
        "CAN YOU PLEASE ASSIST US WITH A TRANSLATION OF THE FOLLOWING:\n"
        ":chocolate_bar: NESN advances\n"
        "Nestle jumps 3.6%."
    )
    got = _extract_content_to_translate(msg)
    assert ":chocolate_bar:" in got
    assert "NESN advances" in got


# --- _split_headline_body: headline and body stay on separate lines after translation ---


def test_split_headline_body_two_lines():
    """Headline is first line, body is the rest (so we can translate them separately)."""
    text = ":loudspeaker: Crypto stocks jump\nStrategy +8%, Coinbase +14% as improving risk sentiment lifts the sector."
    headline, body = _split_headline_body(text)
    assert headline == ":loudspeaker: Crypto stocks jump"
    assert body == "Strategy +8%, Coinbase +14% as improving risk sentiment lifts the sector."


def test_split_headline_body_one_line():
    """Single line is treated as headline, body empty."""
    text = ":loudspeaker: Crypto stocks jump"
    headline, body = _split_headline_body(text)
    assert headline == ":loudspeaker: Crypto stocks jump"
    assert body == ""


def test_split_headline_body_multiline_body():
    """Body can be multiple lines (e.g. two headline+body blocks)."""
    text = ":newspaper: Precious metals rush\nSilver +3%, Gold +1%.\n:rocket: OPEN reignited\nOpendoor jumps 19%."
    headline, body = _split_headline_body(text)
    assert headline == ":newspaper: Precious metals rush"
    assert "Silver +3%" in body
    assert ":rocket: OPEN reignited" in body
