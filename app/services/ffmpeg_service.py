"""FFmpeg service for video rendering."""

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


class FFmpegService:
    """FFmpeg wrapper for video operations."""

    async def create_video_from_image(
        self,
        image_path: str,
        duration_sec: float,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        motion_preset: str = "static",
    ) -> bool:
        """Create video clip from image with optional motion effect.

        Args:
            image_path: Path to input image
            duration_sec: Duration of output video in seconds
            output_path: Path to save output video
            width: Output video width
            height: Output video height
            fps: Frames per second
            motion_preset: Motion effect ("static", "ken_burns_slow", "slow_zoom_in",
                          "slow_zoom_out", "pan_left", "pan_right")

        Returns:
            True if successful, False otherwise
        """
        try:
            total_frames = int(duration_sec * fps)

            if motion_preset == "static":
                filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            elif motion_preset == "ken_burns_slow":
                filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.0005,1.15)':d={total_frames}:s={width}x{height}"
            elif motion_preset == "slow_zoom_in":
                filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.001,1.25)':d={total_frames}:s={width}x{height}"
            elif motion_preset == "slow_zoom_out":
                filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,zoompan=z='max(zoom-0.001,1.0)':d={total_frames}:s={width}x{height}"
            elif motion_preset == "pan_left":
                filter_chain = f"scale={width * 2}:{height}:force_original_aspect_ratio=decrease,pad={width * 2}:{height}:(ow-iw)/2:(oh-ih)/2,crop={width}:{height}:x='min(t*{width}/{duration_sec},{width})':y=0"
            elif motion_preset == "pan_right":
                filter_chain = f"scale={width * 2}:{height}:force_original_aspect_ratio=decrease,pad={width * 2}:{height}:(ow-iw)/2:(oh-ih)/2,crop={width}:{height}:x='max({width}-t*{width}/{duration_sec},0)':y=0"
            else:
                filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"

            cmd = [
                "ffmpeg",
                "-loop",
                "1",
                "-i",
                image_path,
                "-vf",
                filter_chain,
                "-r",
                str(fps),
                "-t",
                str(duration_sec),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-y",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "FFmpeg image-to-video failed",
                    image_path=image_path,
                    motion_preset=motion_preset,
                    stderr=stderr.decode()[:500],
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "FFmpeg image-to-video exception",
                image_path=image_path,
                error=str(e),
            )
            return False

    async def concat_clips(
        self,
        video_files: list[str],
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        video_codec: str = "h264",
        audio_codec: str = "aac",
        transition: str = "crossfade",
        transition_duration_sec: float = 0.5,
    ) -> bool:
        """Concatenate video clips with optional crossfade transitions.

        Args:
            video_files: List of video file paths
            output_path: Path to save concatenated video
            width: Output video width
            height: Output video height
            fps: Frames per second
            video_codec: Video codec (h264, h265, etc.)
            audio_codec: Audio codec (aac, mp3, etc.)
            transition: Transition type ("cut", "crossfade")
            transition_duration_sec: Duration of crossfade transition in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            if not video_files:
                logger.error("No video files provided for concatenation")
                return False

            if transition == "cut" or len(video_files) == 1:
                return await self._concat_clips_cut(
                    video_files, output_path, width, height, fps, video_codec, audio_codec
                )
            else:
                return await self._concat_clips_crossfade(
                    video_files,
                    output_path,
                    width,
                    height,
                    fps,
                    video_codec,
                    audio_codec,
                    transition_duration_sec,
                )
        except Exception as e:
            logger.error("FFmpeg concatenation exception", error=str(e))
            return False

    async def _concat_clips_cut(
        self,
        video_files: list[str],
        output_path: str,
        width: int,
        height: int,
        fps: int,
        video_codec: str,
        audio_codec: str,
    ) -> bool:
        """Concatenate clips without transitions using concat demuxer."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                concat_file = f.name
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

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            Path(concat_file).unlink(missing_ok=True)

            if proc.returncode != 0:
                logger.error(
                    "FFmpeg concat (cut) failed",
                    clip_count=len(video_files),
                    stderr=stderr.decode()[:500],
                )
                return False

            return True
        except Exception as e:
            logger.error("FFmpeg concat (cut) exception", error=str(e))
            return False

    async def _concat_clips_crossfade(
        self,
        video_files: list[str],
        output_path: str,
        width: int,
        height: int,
        fps: int,
        video_codec: str,
        audio_codec: str,
        transition_duration_sec: float,
    ) -> bool:
        """Concatenate clips with crossfade transitions using filter_complex."""
        try:
            if len(video_files) < 2:
                return await self._concat_clips_cut(
                    video_files, output_path, width, height, fps, video_codec, audio_codec
                )

            cmd = ["ffmpeg"]

            # Add all input files
            for video in video_files:
                cmd.extend(["-i", video])

            # Build filter complex for crossfade
            filter_parts = []
            for i, _ in enumerate(video_files):
                filter_parts.append(f"[{i}:v]scale={width}:{height}[v{i}]")

            # Create crossfade chain
            concat_filter = "[v0]"
            for i in range(1, len(video_files)):
                concat_filter += f"[v{i}]xfade=transition=fade:duration={transition_duration_sec}:offset={sum([(10 - transition_duration_sec) for j in range(i)])}[xf{i}]"
                if i < len(video_files) - 1:
                    concat_filter = f"[xf{i}]"

            filter_str = ";".join(filter_parts) + ";" + concat_filter

            cmd.extend(
                [
                    "-filter_complex",
                    filter_str,
                    "-c:v",
                    video_codec,
                    "-c:a",
                    audio_codec,
                    "-r",
                    str(fps),
                    "-y",
                    output_path,
                ]
            )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    "FFmpeg crossfade failed, falling back to cut",
                    clip_count=len(video_files),
                    stderr=stderr.decode()[:200],
                )
                return await self._concat_clips_cut(
                    video_files, output_path, width, height, fps, video_codec, audio_codec
                )

            return True
        except Exception as e:
            logger.warning(
                "FFmpeg concat (crossfade) exception, falling back to cut",
                error=str(e),
            )
            return await self._concat_clips_cut(
                video_files, output_path, width, height, fps, video_codec, audio_codec
            )

    async def overlay_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        video_codec: str = "h264",
        audio_codec: str = "aac",
    ) -> bool:
        """Overlay audio onto video (replace/mix audio track).

        Args:
            video_path: Path to input video
            audio_path: Path to input audio
            output_path: Path to save output
            video_codec: Video codec
            audio_codec: Audio codec

        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-i",
                audio_path,
                "-c:v",
                video_codec,
                "-c:a",
                audio_codec,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-y",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "FFmpeg audio overlay failed",
                    video=video_path,
                    audio=audio_path,
                    stderr=stderr.decode()[:500],
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "FFmpeg audio overlay exception",
                video=video_path,
                error=str(e),
            )
            return False

    @staticmethod
    def _ascii_temp_copy(src_path: str) -> tuple[str, str]:
        """Copy a file to a guaranteed-ASCII temp path for FFmpeg compatibility.

        FFmpeg's ``subtitles=`` filter fails on Windows when the path contains
        non-ASCII characters (Korean, spaces with special chars, etc.).
        Returns (safe_path, tmp_dir) — caller must clean up tmp_dir.

        Args:
            src_path: Original (possibly non-ASCII) file path

        Returns:
            Tuple of (safe ASCII path string, temp dir string to remove after use)
        """
        import shutil as _shutil
        import uuid as _uuid

        tmp_dir = Path(tempfile.gettempdir()) / f"ffmpeg_{_uuid.uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        # Keep the extension, use generic ASCII filename
        ext = Path(src_path).suffix
        safe_path = tmp_dir / f"input{ext}"
        _shutil.copy2(src_path, str(safe_path))
        return str(safe_path), str(tmp_dir)

    async def burn_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        font_path: Optional[str] = None,
        font_size: int = 32,
    ) -> bool:
        """Burn subtitles into video with styling.

        Args:
            video_path: Path to input video
            subtitle_path: Path to SRT subtitle file
            output_path: Path to save output
            font_path: Path to font file (optional)
            font_size: Font size

        Returns:
            True if successful, False otherwise
        """
        import shutil as _shutil

        # FFmpeg subtitles= 필터는 경로에 한글/특수문자가 있으면 실패함.
        # 자막 파일을 ASCII 임시 경로로 복사해서 처리.
        safe_sub_path, _tmp_dir = self._ascii_temp_copy(subtitle_path)

        try:
            subtitle_path_escaped = safe_sub_path.replace("\\", "/").replace(":", "\\:")

            if font_path:
                font_path_escaped = font_path.replace("\\", "/").replace(":", "\\:")
                subtitle_filter = f"subtitles={subtitle_path_escaped}:fontfile={font_path_escaped}:fontsize={font_size}"
            else:
                subtitle_filter = f"subtitles={subtitle_path_escaped}:fontsize={font_size}"

            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                subtitle_filter,
                "-c:a",
                "copy",
                "-y",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "FFmpeg subtitle burn failed",
                    video=video_path,
                    subtitles=subtitle_path,
                    stderr=stderr.decode()[:500],
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "FFmpeg subtitle burn exception",
                video=video_path,
                error=str(e),
            )
            return False
        finally:
            # 임시 자막 파일 정리
            _shutil.rmtree(_tmp_dir, ignore_errors=True)

    async def embed_subtitles_soft(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
    ) -> bool:
        """Embed subtitles as a soft (toggle-able) track using mov_text codec.

        Unlike burn_subtitles(), this does NOT render text into the video pixels.
        The subtitle track is embedded inside the MP4 container and can be toggled
        by the player. Works on any path — no ASCII temp copy needed.

        Args:
            video_path: Path to input video
            subtitle_path: Path to SRT subtitle file
            output_path: Path to save output

        Returns:
            True if successful, False otherwise
        """
        import shutil as _shutil

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", subtitle_path,
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=kor",
            "-y",
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    "Soft subtitle embed failed",
                    video=video_path,
                    stderr=stderr.decode()[:300],
                )
                return False

            logger.info("Soft subtitle embed succeeded", output=output_path)
            return True
        except Exception as e:
            logger.warning("Soft subtitle embed exception", error=str(e))
            return False

    async def get_duration(self, file_path: str) -> Optional[float]:
        """Get video duration in seconds using ffprobe.

        Args:
            file_path: Path to media file

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
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

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    "FFprobe duration check failed",
                    file=file_path,
                    stderr=stderr.decode()[:200],
                )
                return None

            duration_str = stdout.decode().strip()
            return float(duration_str) if duration_str else None
        except Exception as e:
            logger.error("FFprobe exception", file=file_path, error=str(e))
            return None

    async def create_draft(
        self,
        image_paths: list[str],
        durations: list[float],
        motion_presets: list[str],
        narration_audio_path: str,
        subtitles_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        font_path: Optional[str] = None,
    ) -> bool:
        """High-level orchestration: images → clips → concat → audio → subtitles → draft.mp4.

        Args:
            image_paths: List of image file paths
            durations: List of durations for each image
            motion_presets: List of motion presets for each image
            narration_audio_path: Path to narration audio file
            subtitles_path: Path to subtitle file
            output_path: Path to save final draft video
            width: Output width
            height: Output height
            fps: Frames per second
            font_path: Font path for subtitles

        Returns:
            True if successful, False otherwise
        """
        try:
            if not image_paths:
                logger.error("No image paths provided for draft creation")
                return False

            if len(image_paths) != len(durations) or len(image_paths) != len(motion_presets):
                logger.error(
                    "Mismatched image/duration/preset counts",
                    images=len(image_paths),
                    durations=len(durations),
                    presets=len(motion_presets),
                )
                return False

            temp_clips = []

            try:
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
                    temp_dir_path = Path(temp_dir)

                    logger.info(
                        "Creating video clips from images",
                        image_count=len(image_paths),
                    )

                    for i, (img_path, duration, preset) in enumerate(
                        zip(image_paths, durations, motion_presets)
                    ):
                        clip_path = str(temp_dir_path / f"clip_{i:03d}.mp4")
                        success = await self.create_video_from_image(
                            img_path,
                            duration,
                            clip_path,
                            width=width,
                            height=height,
                            fps=fps,
                            motion_preset=preset,
                        )

                        if not success:
                            logger.error(
                                "Failed to create video clip",
                                index=i,
                                image=img_path,
                                preset=preset,
                            )
                            return False

                        temp_clips.append(clip_path)

                    logger.info("Concatenating clips", clip_count=len(temp_clips))

                    concat_path = str(temp_dir_path / "concatenated.mp4")
                    success = await self.concat_clips(
                        temp_clips,
                        concat_path,
                        width=width,
                        height=height,
                        fps=fps,
                        video_codec="h264",
                        audio_codec="aac",
                        transition="cut",
                    )

                    if not success:
                        logger.error("Failed to concatenate clips")
                        return False

                    logger.info("Overlaying audio")

                    audio_path = str(temp_dir_path / "with_audio.mp4")
                    success = await self.overlay_audio(
                        concat_path,
                        narration_audio_path,
                        audio_path,
                        video_codec="h264",
                        audio_codec="aac",
                    )

                    if not success:
                        logger.error("Failed to overlay audio")
                        return False

                    # ── 자막 처리 3단계 fallback chain ──────────────────────
                    # 1. hardcoded burn  (subtitles= 필터로 픽셀에 직접 렌더링)
                    # 2. soft embed      (mov_text 트랙으로 MP4 안에 삽입, 플레이어에서 토글 가능)
                    # 3. no subtitles    (SRT 파일은 result 폴더에 별도 보관됨)
                    # ────────────────────────────────────────────────────────
                    import shutil as _shutil

                    subs_file = Path(subtitles_path) if subtitles_path else None
                    has_subtitles = (
                        subs_file is not None
                        and subs_file.exists()
                        and subs_file.stat().st_size > 0
                    )

                    if has_subtitles:
                        # Step 1: hardcoded burn
                        logger.info("Burning subtitles (hardcoded)")
                        burn_ok = await self.burn_subtitles(
                            audio_path,
                            subtitles_path,
                            output_path,
                            font_path=font_path,
                        )

                        if burn_ok:
                            logger.info("Subtitle burn succeeded")
                        else:
                            # Step 2: soft embed fallback
                            logger.warning(
                                "Subtitle burn failed — trying soft embed (mov_text)"
                            )
                            soft_ok = await self.embed_subtitles_soft(
                                audio_path,
                                subtitles_path,
                                output_path,
                            )

                            if not soft_ok:
                                # Step 3: no subtitles
                                logger.warning(
                                    "Soft embed also failed — producing video without subtitles"
                                )
                                _shutil.copy2(audio_path, output_path)
                    else:
                        logger.warning("Subtitles file empty or missing, skipping burn")
                        _shutil.copy2(audio_path, output_path)

                    logger.info("Draft video creation completed", output=output_path)
                    return True

            except Exception as e:
                logger.error("Exception during draft creation", error=str(e))
                return False

        except Exception as e:
            logger.error("Outer exception during draft creation", error=str(e))
            return False
