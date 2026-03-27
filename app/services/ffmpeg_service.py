"""FFmpeg service for video rendering."""

import asyncio
import subprocess
from typing import Optional


class FFmpegService:
    """FFmpeg wrapper for video operations."""

    async def concat_videos(
        self,
        video_files: list[str],
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        video_codec: str = "h264",
        audio_codec: str = "aac",
    ) -> bool:
        """Concatenate videos."""
        # Create concat demuxer file
        concat_file = "/tmp/concat.txt"
        with open(concat_file, "w") as f:
            for video in video_files:
                f.write(f"file '{video}'\n")

        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c:v",
            video_codec,
            "-c:a",
            audio_codec,
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-y",
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def add_audio_track(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> bool:
        """Add audio track to video."""
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-y",
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def burn_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
    ) -> bool:
        """Burn subtitles into video."""
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            f"subtitles={subtitle_path}",
            "-c:a",
            "copy",
            "-y",
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def get_duration(self, file_path: str) -> Optional[float]:
        """Get video duration in seconds."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
            file_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            duration_str = stdout.decode().strip()
            return float(duration_str) if duration_str else None
        except Exception:
            return None
