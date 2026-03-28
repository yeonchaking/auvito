"""Pillow service for image processing."""

from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.utils.logger import get_logger

logger = get_logger(__name__)


class PillowService:
    """Pillow wrapper for image operations."""

    async def resize_image(
        self,
        input_path: str,
        output_path: str,
        width: int,
        height: int,
        maintain_aspect: bool = True,
    ) -> bool:
        """Resize image.

        Args:
            input_path: Path to input image
            output_path: Path to save resized image
            width: Target width
            height: Target height
            maintain_aspect: If True, maintain aspect ratio and letterbox with black bars

        Returns:
            True if successful, False otherwise
        """
        try:
            img = Image.open(input_path)

            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                # Center the image with letterbox
                new_img = Image.new("RGB", (width, height), color=(0, 0, 0))
                offset = (
                    (width - img.width) // 2,
                    (height - img.height) // 2,
                )
                new_img.paste(img, offset)
                img = new_img
            else:
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            img.save(output_path)
            return True
        except Exception as e:
            logger.error(
                "Image resize failed",
                input=input_path,
                target_size=f"{width}x{height}",
                error=str(e),
            )
            return False

    async def resize_to_canvas(
        self,
        input_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> bool:
        """Resize image to exact canvas size, handling aspect ratio with letterbox/pillarbox.

        Args:
            input_path: Path to input image
            output_path: Path to save resized image
            width: Canvas width
            height: Canvas height

        Returns:
            True if successful, False otherwise
        """
        try:
            img = Image.open(input_path).convert("RGB")

            img.thumbnail((width, height), Image.Resampling.LANCZOS)

            canvas = Image.new("RGB", (width, height), color=(0, 0, 0))
            offset = (
                (width - img.width) // 2,
                (height - img.height) // 2,
            )
            canvas.paste(img, offset)
            canvas.save(output_path)

            logger.info(
                "Image resized to canvas",
                input=input_path,
                canvas_size=f"{width}x{height}",
            )
            return True
        except Exception as e:
            logger.error(
                "Canvas resize failed",
                input=input_path,
                canvas_size=f"{width}x{height}",
                error=str(e),
            )
            return False

    async def add_letterbox(
        self,
        input_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> bool:
        """Add black letterbox/pillarbox to image to fit exact dimensions.

        Args:
            input_path: Path to input image
            output_path: Path to save letterboxed image
            width: Target width
            height: Target height

        Returns:
            True if successful, False otherwise
        """
        return await self.resize_to_canvas(input_path, output_path, width, height)

    async def add_text_overlay(
        self,
        input_path: str,
        output_path: str,
        text: str,
        font_path: Optional[str] = None,
        font_size: int = 40,
        text_color: tuple = (255, 255, 255),
        stroke_color: tuple = (0, 0, 0),
        stroke_width: int = 3,
        position: tuple = (50, 50),
    ) -> bool:
        """Add text overlay to image with stroke outline.

        Args:
            input_path: Path to input image
            output_path: Path to save image with text
            text: Text to overlay
            font_path: Path to TTF font file (optional)
            font_size: Font size in pixels
            text_color: RGB tuple for text color
            stroke_color: RGB tuple for stroke/outline color
            stroke_width: Width of stroke outline
            position: (x, y) tuple for text position

        Returns:
            True if successful, False otherwise
        """
        try:
            img = Image.open(input_path).convert("RGBA")
            draw = ImageDraw.Draw(img)

            try:
                if font_path:
                    font = ImageFont.truetype(font_path, font_size)
                else:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            # Draw text with stroke
            for adj_x in range(-stroke_width, stroke_width + 1):
                for adj_y in range(-stroke_width, stroke_width + 1):
                    draw.text(
                        (position[0] + adj_x, position[1] + adj_y),
                        text,
                        font=font,
                        fill=stroke_color,
                    )

            # Draw main text
            draw.text(position, text, font=font, fill=text_color)

            img = img.convert("RGB")
            img.save(output_path)

            logger.info(
                "Text overlay added",
                input=input_path,
                text_length=len(text),
            )
            return True
        except Exception as e:
            logger.error(
                "Text overlay failed",
                input=input_path,
                error=str(e),
            )
            return False

    async def composite_images(
        self,
        background_path: str,
        foreground_path: str,
        output_path: str,
        position: tuple = (0, 0),
    ) -> bool:
        """Composite foreground image onto background.

        Args:
            background_path: Path to background image
            foreground_path: Path to foreground image (will use alpha channel if present)
            output_path: Path to save composited image
            position: (x, y) tuple for foreground position

        Returns:
            True if successful, False otherwise
        """
        try:
            bg = Image.open(background_path).convert("RGB")
            fg = Image.open(foreground_path).convert("RGBA")

            bg.paste(fg, position, fg)
            bg.save(output_path)

            logger.info(
                "Images composited",
                background=background_path,
                foreground=foreground_path,
            )
            return True
        except Exception as e:
            logger.error(
                "Image composite failed",
                background=background_path,
                error=str(e),
            )
            return False

    async def get_image_info(self, image_path: str) -> Optional[dict]:
        """Get image metadata.

        Args:
            image_path: Path to image file

        Returns:
            Dict with width, height, format; or None if unable to read
        """
        try:
            img = Image.open(image_path)
            info = {
                "width": img.width,
                "height": img.height,
                "format": img.format,
            }
            logger.debug(
                "Image info retrieved",
                path=image_path,
                width=img.width,
                height=img.height,
            )
            return info
        except Exception as e:
            logger.error(
                "Image info retrieval failed",
                path=image_path,
                error=str(e),
            )
            return None
