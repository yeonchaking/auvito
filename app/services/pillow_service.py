"""Pillow service for image processing."""

from typing import Optional

from PIL import Image, ImageDraw, ImageFont


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
        """Resize image."""
        try:
            img = Image.open(input_path)

            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                # Center the image
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
        except Exception:
            return False

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
        """Add text overlay to image."""
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
            return True
        except Exception:
            return False

    async def composite_images(
        self,
        background_path: str,
        foreground_path: str,
        output_path: str,
        position: tuple = (0, 0),
    ) -> bool:
        """Composite foreground image onto background."""
        try:
            bg = Image.open(background_path).convert("RGB")
            fg = Image.open(foreground_path).convert("RGBA")

            bg.paste(fg, position, fg)
            bg.save(output_path)
            return True
        except Exception:
            return False

    async def get_image_info(self, image_path: str) -> Optional[dict]:
        """Get image metadata."""
        try:
            img = Image.open(image_path)
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format,
            }
        except Exception:
            return None
