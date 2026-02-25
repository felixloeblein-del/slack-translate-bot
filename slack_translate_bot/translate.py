"""Translate text using DeepL; only treat as success when source is English."""

import logging
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

# Only post translation to Slack when detected source is English
SOURCE_LANG_FILTER = "EN"


def translate_en_to_de(text: str) -> Optional[str]:
    """
    Translate text to German. Uses DeepL auto-detect; only returns translation
    when the detected source language is English (SOURCE_LANG_FILTER).
    Returns None if not English or on error.
    """
    if not text or not text.strip():
        return None
    if not config.DEEPL_API_KEY:
        logger.warning("DEEPL_API_KEY not set; skipping translation")
        return None
    try:
        import deepl
    except ImportError:
        logger.warning("deepl package not installed; pip install deepl")
        return None
    try:
        translator = deepl.Translator(config.DEEPL_API_KEY)
        result = translator.translate_text(text.strip(), target_lang="DE")
        # Single string returns one result; list returns list of results
        if hasattr(result, "__iter__") and not isinstance(result, str):
            results = list(result)
            if not results:
                return None
            first = results[0]
        else:
            first = result
        detected = getattr(first, "detected_source_lang", None)
        if detected is not None and str(detected).upper() != SOURCE_LANG_FILTER:
            logger.debug("Skipping translation: detected source %s is not EN", detected)
            return None
        return getattr(first, "text", None) or str(first)
    except Exception as e:
        logger.exception("DeepL translation failed: %s", e)
        return None
