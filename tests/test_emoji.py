"""
Tests for Slack emoji preservation: shortcodes are replaced before DeepL and restored after.
"""

from slack_translate_bot.main import (
    _replace_slack_emojis_for_translation,
    _restore_slack_emojis,
)


def test_emoji_replaced_with_placeholders():
    """Slack :shortcode: are replaced so DeepL doesn't translate them."""
    text = ":loudspeaker: Precious metals rally"
    out, shortcodes = _replace_slack_emojis_for_translation(text)
    assert ":loudspeaker:" not in out
    assert "EMOJISLACK" in out
    assert shortcodes == [":loudspeaker:"]


def test_emoji_restore_roundtrip():
    """After translation, placeholders are restored to original shortcodes."""
    text = ":loudspeaker: Edelmetalle erholen sich"
    replaced, shortcodes = _replace_slack_emojis_for_translation(text)
    restored = _restore_slack_emojis(replaced, shortcodes)
    assert restored == text


def test_multiple_emojis_preserved():
    """Multiple emojis in one message are all replaced and restored in order."""
    text = ":chart_with_downwards_trend: DBX stürzt ab. :newspaper: Mehr dazu."
    replaced, shortcodes = _replace_slack_emojis_for_translation(text)
    assert len(shortcodes) == 2
    assert ":chart_with_downwards_trend:" in shortcodes
    assert ":newspaper:" in shortcodes
    restored = _restore_slack_emojis(replaced, shortcodes)
    assert restored == text


def test_no_emoji_unchanged():
    """Text without emoji shortcodes is unchanged."""
    text = "Gold +2.4%, Silver +6% rebound."
    out, shortcodes = _replace_slack_emojis_for_translation(text)
    assert out == text
    assert shortcodes == []
