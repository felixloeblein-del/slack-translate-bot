"""
Tests for EN->DE translation (DeepL mocked; no real API calls).
"""

from unittest.mock import MagicMock, patch

from slack_translate_bot.main import _translate_headline_and_body
from slack_translate_bot.translate import translate_en_to_de


def test_translate_empty_returns_none():
    """Empty or whitespace text returns None (no API call)."""
    assert translate_en_to_de("") is None
    assert translate_en_to_de("   ") is None


@patch("slack_translate_bot.translate.config")
def test_translate_returns_none_when_no_api_key(mock_config):
    """When DEEPL_API_KEY is not set, translation is skipped."""
    mock_config.DEEPL_API_KEY = ""
    assert translate_en_to_de("Hello") is None


@patch("deepl.Translator")
@patch("slack_translate_bot.translate.config")
def test_translate_mock_deepl_returns_german(mock_config, mock_deepl_translator):
    """When DeepL returns EN->DE, we return the translated text."""
    mock_config.DEEPL_API_KEY = "fake-key"
    # Use simple object so code treats as single result (not iterable list)
    class FakeResult:
        detected_source_lang = "EN"
        text = "Hallo, wie geht es dir?"
    mock_translator = MagicMock()
    mock_translator.translate_text.return_value = FakeResult()
    mock_deepl_translator.return_value = mock_translator

    got = translate_en_to_de("Hello, how are you?")
    assert got == "Hallo, wie geht es dir?"


@patch("deepl.Translator")
@patch("slack_translate_bot.translate.config")
def test_translate_mock_deepl_non_en_returns_none(mock_config, mock_deepl_translator):
    """When DeepL detects source is not English, we return None (no post to Slack)."""
    mock_config.DEEPL_API_KEY = "fake-key"
    class FakeResult:
        detected_source_lang = "DE"
        text = "Unverändert"
    mock_translator = MagicMock()
    mock_translator.translate_text.return_value = FakeResult()
    mock_deepl_translator.return_value = mock_translator

    got = translate_en_to_de("Some German text")
    assert got is None


# --- _translate_headline_and_body: headline and body translated separately, joined by newline ---


@patch("slack_translate_bot.main.translate_en_to_de")
def test_translate_headline_and_body_keeps_two_lines(mock_translate):
    """Headline and body are translated separately and joined with newline."""
    def side_effect(text):
        if "Crypto stocks jump" in text:
            return "Krypto-Aktien legen zu"
        if "Strategy +8%" in text or "Coinbase" in text:
            return "Strategy +8 %, Coinbase +14 %, da die verbesserte Risikostimmung den Sektor beflügelt."
        return None
    mock_translate.side_effect = side_effect

    text = ":loudspeaker: Crypto stocks jump\nStrategy +8%, Coinbase +14% as improving risk sentiment lifts the sector."
    got = _translate_headline_and_body(text)
    assert got is not None
    lines = got.split("\n")
    assert len(lines) == 2
    assert "Krypto-Aktien" in lines[0]
    assert "Strategy +8 %" in lines[1] or "Coinbase" in lines[1]
