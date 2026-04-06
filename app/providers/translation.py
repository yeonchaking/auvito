"""Subtitle translation provider using Claude API."""

import re
from typing import Optional

from app.utils.logger import get_logger
from app.utils.srt import SRTGenerator, SRTSubtitle

logger = get_logger(__name__)

# Max SRT blocks to send per API call (avoids hitting token limits)
_BATCH_SIZE = 30


class ClaudeSubtitleTranslator:
    """Translates SRT subtitle files using the Anthropic Claude API.

    Preserves all timecodes; only the text content is translated.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"):
        """Initialize translator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model string
        """
        import os

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model

        if not self.api_key:
            raise ValueError(
                "Anthropic API key is required for subtitle translation. "
                "Set ANTHROPIC_API_KEY environment variable or pass api_key."
            )

    async def translate_srt(
        self,
        subtitles: list[SRTSubtitle],
        source_lang: str = "Korean",
        target_lang: str = "English",
    ) -> list[SRTSubtitle]:
        """Translate a list of SRTSubtitle objects.

        Timecodes and indices are preserved exactly; only text is translated.

        Args:
            subtitles: Source subtitle list
            source_lang: Source language name (e.g. 'Korean')
            target_lang: Target language name (e.g. 'English')

        Returns:
            New list of SRTSubtitle with translated text, same timecodes.
        """
        if not subtitles:
            return []

        translated: list[SRTSubtitle] = []

        # Process in batches to stay within token limits
        for batch_start in range(0, len(subtitles), _BATCH_SIZE):
            batch = subtitles[batch_start : batch_start + _BATCH_SIZE]
            batch_translated = await self._translate_batch(batch, source_lang, target_lang)
            translated.extend(batch_translated)

        # Re-index sequentially (1-based)
        for i, sub in enumerate(translated, 1):
            sub.index = i

        logger.info(
            "Subtitle translation complete",
            total_blocks=len(translated),
            source_lang=source_lang,
            target_lang=target_lang,
        )
        return translated

    async def translate_srt_file(
        self,
        input_path: str,
        output_path: str,
        source_lang: str = "Korean",
        target_lang: str = "English",
    ) -> bool:
        """Read a .srt file, translate it, and write the result.

        Args:
            input_path: Path to source SRT file
            output_path: Path to write translated SRT file
            source_lang: Source language name
            target_lang: Target language name

        Returns:
            True on success, False on failure.
        """
        subtitles = SRTGenerator.read_srt_file(input_path)
        if not subtitles:
            logger.warning("No subtitles found in source file", path=input_path)
            return False

        translated = await self.translate_srt(subtitles, source_lang, target_lang)
        success = SRTGenerator.write_srt_file(translated, output_path)

        if success:
            logger.info(
                "Translated SRT written",
                input_path=input_path,
                output_path=output_path,
                block_count=len(translated),
            )
        else:
            logger.error("Failed to write translated SRT", output_path=output_path)

        return success

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _translate_batch(
        self,
        batch: list[SRTSubtitle],
        source_lang: str,
        target_lang: str,
    ) -> list[SRTSubtitle]:
        """Translate one batch of subtitles via Claude API.

        Sends the text lines to Claude and parses the returned translations.
        Each line is tagged <N>text</N> so Claude can return them in order.

        Args:
            batch: Subtitle objects to translate
            source_lang: Source language name
            target_lang: Target language name

        Returns:
            Translated SRTSubtitle list (same timecodes, new text).
        """
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Build numbered input block
        numbered_lines = "\n".join(
            f"<{sub.index}>{sub.text}</{sub.index}>" for sub in batch
        )

        prompt = (
            f"You are a professional subtitle translator. "
            f"Translate the following {source_lang} subtitle lines into natural {target_lang}. "
            f"Rules:\n"
            f"- Keep each translation concise (subtitle-length).\n"
            f"- Preserve the XML-like tags exactly: <N>...</N> where N is the index number.\n"
            f"- Do NOT add, remove, merge, or reorder tags.\n"
            f"- Do NOT translate proper nouns (names, places) unless they have a standard {target_lang} equivalent.\n"
            f"- Return ONLY the translated tagged lines, nothing else.\n\n"
            f"{numbered_lines}"
        )

        logger.debug(
            "Sending translation batch to Claude",
            batch_size=len(batch),
            model=self.model,
        )

        message = await client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text if message.content else ""
        return self._parse_translation_response(response_text, batch)

    def _parse_translation_response(
        self, response_text: str, original_batch: list[SRTSubtitle]
    ) -> list[SRTSubtitle]:
        """Parse Claude's tagged response back into SRTSubtitle objects.

        Falls back to the original text for any tag that couldn't be parsed.

        Args:
            response_text: Raw Claude response
            original_batch: Original subtitles (for fallback and timecodes)

        Returns:
            List of SRTSubtitle with translated text and original timecodes.
        """
        # Build a map: index → translated text
        translation_map: dict[int, str] = {}
        pattern = re.compile(r"<(\d+)>(.*?)</\1>", re.DOTALL)
        for match in pattern.finditer(response_text):
            idx = int(match.group(1))
            text = match.group(2).strip()
            translation_map[idx] = text

        result: list[SRTSubtitle] = []
        for sub in original_batch:
            translated_text = translation_map.get(sub.index, sub.text)
            if sub.index not in translation_map:
                logger.warning(
                    "Translation missing for subtitle index, using original",
                    index=sub.index,
                )
            result.append(
                SRTSubtitle(
                    index=sub.index,
                    start_sec=sub.start_sec,
                    end_sec=sub.end_sec,
                    text=translated_text,
                )
            )

        return result
