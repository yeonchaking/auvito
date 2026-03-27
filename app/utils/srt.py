"""SRT (SubRip) subtitle file utilities."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SRTSubtitle:
    """Single subtitle entry in SRT format."""

    index: int
    start_sec: float
    end_sec: float
    text: str

    def to_srt_block(self) -> str:
        """Convert to SRT format block.

        Returns:
            SRT formatted block (index, timecode, text)
        """
        start_timecode = self._seconds_to_timecode(self.start_sec)
        end_timecode = self._seconds_to_timecode(self.end_sec)
        return f"{self.index}\n{start_timecode} --> {end_timecode}\n{self.text}\n"

    @staticmethod
    def _seconds_to_timecode(seconds: float) -> str:
        """Convert seconds to SRT timecode format (HH:MM:SS,mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Timecode string in SRT format
        """
        total_seconds = int(seconds)
        milliseconds = int((seconds - total_seconds) * 1000)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


class SRTGenerator:
    """Utility for generating SRT subtitle files."""

    MAX_CHARS_PER_LINE = 42
    MAX_LINES = 3

    @staticmethod
    def generate_from_words(
        words: list[dict],
        max_chars_per_line: int = MAX_CHARS_PER_LINE,
        max_lines: int = MAX_LINES,
    ) -> list[SRTSubtitle]:
        """Generate SRT subtitles from word-level timestamps.

        Args:
            words: List of dicts with 'word', 'start_sec', 'end_sec'
            max_chars_per_line: Maximum characters per line
            max_lines: Maximum lines per subtitle

        Returns:
            List of SRTSubtitle objects
        """
        if not words:
            return []

        subtitles = []
        current_line = ""
        current_index = 1
        start_time = words[0]["start_sec"]
        line_count = 0

        for i, word_data in enumerate(words):
            word = word_data["word"]
            end_time = word_data["end_sec"]

            # Check if adding this word would exceed limits
            test_line = current_line + (" " if current_line else "") + word
            if (
                len(test_line) > max_chars_per_line
                or line_count >= max_lines - 1
                or (i == len(words) - 1)
            ):
                # Finish current subtitle
                if i == len(words) - 1 and len(test_line) <= max_chars_per_line:
                    # Last word fits on current line
                    current_line = test_line
                    end_time = word_data["end_sec"]
                else:
                    # Create subtitle with current content
                    if current_line:
                        subtitles.append(
                            SRTSubtitle(
                                index=current_index,
                                start_sec=start_time,
                                end_sec=words[i - 1]["end_sec"],
                                text=current_line,
                            )
                        )
                        current_index += 1

                    # Check if we need to add the last word as new line
                    if i == len(words) - 1 and len(test_line) > max_chars_per_line:
                        subtitles.append(
                            SRTSubtitle(
                                index=current_index,
                                start_sec=word_data["start_sec"],
                                end_sec=end_time,
                                text=word,
                            )
                        )

                    # Reset for next subtitle
                    current_line = word if i < len(words) - 1 else ""
                    start_time = word_data["start_sec"]
                    line_count = 0 if current_line else -1
            else:
                current_line = test_line
                line_count += current_line.count("\n") if "\n" in test_line else 0

        # Add final subtitle if not empty
        if current_line:
            subtitles.append(
                SRTSubtitle(
                    index=current_index,
                    start_sec=start_time,
                    end_sec=words[-1]["end_sec"],
                    text=current_line,
                )
            )

        return subtitles

    @staticmethod
    def generate_from_text_chunks(
        chunks: list[dict],
    ) -> list[SRTSubtitle]:
        """Generate SRT subtitles from text chunks with timestamps.

        Args:
            chunks: List of dicts with 'text', 'start_sec', 'end_sec'

        Returns:
            List of SRTSubtitle objects
        """
        subtitles = []

        for i, chunk in enumerate(chunks, 1):
            subtitles.append(
                SRTSubtitle(
                    index=i,
                    start_sec=chunk["start_sec"],
                    end_sec=chunk["end_sec"],
                    text=chunk["text"],
                )
            )

        return subtitles

    @staticmethod
    def write_srt_file(subtitles: list[SRTSubtitle], output_path: str) -> bool:
        """Write SRT subtitles to file.

        Args:
            subtitles: List of SRTSubtitle objects
            output_path: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for subtitle in subtitles:
                    f.write(subtitle.to_srt_block())
                    f.write("\n")
            return True
        except Exception:
            return False

    @staticmethod
    def read_srt_file(input_path: str) -> list[SRTSubtitle]:
        """Read SRT subtitles from file.

        Args:
            input_path: Input file path

        Returns:
            List of SRTSubtitle objects
        """
        subtitles = []

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split by double newlines
            blocks = content.strip().split("\n\n")

            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) < 3:
                    continue

                try:
                    index = int(lines[0])
                    timecode = lines[1]
                    text = "\n".join(lines[2:])

                    # Parse timecode
                    parts = timecode.split(" --> ")
                    if len(parts) != 2:
                        continue

                    start_sec = SRTSubtitle._timecode_to_seconds(parts[0])
                    end_sec = SRTSubtitle._timecode_to_seconds(parts[1])

                    subtitles.append(
                        SRTSubtitle(
                            index=index,
                            start_sec=start_sec,
                            end_sec=end_sec,
                            text=text,
                        )
                    )
                except (ValueError, IndexError):
                    continue

        except Exception:
            pass

        return subtitles

    @staticmethod
    def _timecode_to_seconds(timecode: str) -> float:
        """Convert SRT timecode to seconds.

        Args:
            timecode: Timecode string (HH:MM:SS,mmm)

        Returns:
            Time in seconds
        """
        timecode = timecode.strip()
        # Replace comma with period for milliseconds
        timecode = timecode.replace(",", ".")

        parts = timecode.split(":")
        if len(parts) != 3:
            return 0.0

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            return 0.0
