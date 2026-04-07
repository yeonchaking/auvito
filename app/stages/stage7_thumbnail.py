"""Stage 7: Thumbnail generation using Pillow."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.contracts import AssetManifestContract, ScriptContract
from app.stages.base import BaseStage
from app.storage.files import FileStorage
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Output spec
THUMB_W = 1280
THUMB_H = 720

# Text layout
TITLE_MARGIN_X = 60
TITLE_BOTTOM_Y = THUMB_H - 60   # baseline from bottom
MAX_TITLE_WIDTH = THUMB_W - TITLE_MARGIN_X * 2

# Gradient covers bottom N% of image
GRADIENT_HEIGHT_RATIO = 0.55

# Font candidates (tried in order; first found wins)
_KOREAN_FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/malgunbd.ttf",    # 맑은 고딕 Bold
    "C:/Windows/Fonts/malgun.ttf",      # 맑은 고딕
    "C:/Windows/Fonts/gulim.ttc",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    # Linux (nanum)
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    # Generic fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _find_font(size: int):
    """Return first available TrueType font at the requested size, or default."""
    from PIL import ImageFont

    for path in _KOREAN_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    # Ultimate fallback: PIL built-in bitmap font (no size control)
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def _draw_text_with_shadow(
    draw,
    xy: tuple[int, int],
    text: str,
    font,
    fill=(255, 255, 255),
    shadow_color=(0, 0, 0),
    shadow_offset: int = 3,
    shadow_blur: bool = False,
):
    """Draw text with a drop shadow."""
    sx, sy = xy[0] + shadow_offset, xy[1] + shadow_offset
    # Shadow
    draw.text((sx, sy), text, font=font, fill=shadow_color)
    # Main text
    draw.text(xy, text, font=font, fill=fill)


class ThumbnailStageInput:
    """Input data for thumbnail stage."""

    def __init__(
        self,
        script_contract: ScriptContract,
        asset_manifest_contract: AssetManifestContract,
        workspace_root: str,
        project_slug: str,
        title_override: Optional[str] = None,
        bg_asset_index: int = 0,
    ):
        """Initialize thumbnail stage input.

        Args:
            script_contract: ScriptContract (for title)
            asset_manifest_contract: AssetManifestContract (for background images)
            workspace_root: Workspace root directory
            project_slug: Project slug
            title_override: Custom title text (defaults to script title)
            bg_asset_index: Which asset image to use as background (0 = first)
        """
        self.script_contract = script_contract
        self.asset_manifest_contract = asset_manifest_contract
        self.workspace_root = workspace_root
        self.project_slug = project_slug
        self.title = title_override or script_contract.title
        self.bg_asset_index = bg_asset_index


class ThumbnailStage(BaseStage):
    """Stage 7: Thumbnail generation.

    Pipeline:
    1. Pick background image from asset manifest
    2. Resize / center-crop to 1280×720
    3. Apply dark gradient overlay at the bottom
    4. Render title text with shadow in the lower portion
    5. Save thumbnail.png

    Output:
    - thumbnail.png (1280×720 JPEG-quality PNG)
    """

    stage_name = "thumbnail"

    async def execute(self, input_data: ThumbnailStageInput) -> dict:
        """Generate thumbnail image.

        Returns:
            dict with thumbnail_path and metadata
        """
        from PIL import Image, ImageDraw, ImageFilter
        import numpy as np

        workspace = Path(input_data.workspace_root) / "projects" / input_data.project_slug
        thumb_dir = workspace / "07_thumbnail"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        output_path = thumb_dir / "thumbnail.png"

        logger.info(
            "Generating thumbnail",
            title=input_data.title,
            output=str(output_path),
        )

        # ── 1. Select background image ──────────────────────────────────────
        assets = input_data.asset_manifest_contract.selected_assets
        if not assets:
            raise ValueError("No assets available for thumbnail background")

        idx = min(input_data.bg_asset_index, len(assets) - 1)
        bg_asset = assets[idx]

        # Resolve path: stored URIs may be relative or use workspace prefix
        bg_path = Path(bg_asset.uri)
        if not bg_path.is_absolute():
            bg_path = Path(input_data.workspace_root) / bg_asset.uri

        # Fallback: scan images directory
        if not bg_path.exists():
            images_dir = workspace / "05_assets" / "images"
            pngs = sorted(images_dir.glob("*.png"))
            if not pngs:
                raise FileNotFoundError(f"Background image not found: {bg_path}")
            bg_path = pngs[idx % len(pngs)]

        logger.info("Using background image", path=str(bg_path))

        # ── 2. Resize / center-crop to 1280×720 ─────────────────────────────
        img = Image.open(bg_path).convert("RGB")
        img = _smart_crop(img, THUMB_W, THUMB_H)

        # ── 3. Dark gradient overlay ─────────────────────────────────────────
        img = _apply_gradient_overlay(img)

        # ── 4. Render title text ─────────────────────────────────────────────
        img = _render_title(img, input_data.title)

        # ── 5. Save ───────────────────────────────────────────────────────────
        img.save(str(output_path), "PNG", optimize=True)

        logger.info(
            "Thumbnail saved",
            path=str(output_path),
            size=f"{THUMB_W}x{THUMB_H}",
        )

        # Save metadata sidecar
        meta = {
            "generated_at": datetime.utcnow().isoformat(),
            "title": input_data.title,
            "background_asset": bg_asset.asset_id,
            "background_path": str(bg_path),
            "output_path": str(output_path),
            "width": THUMB_W,
            "height": THUMB_H,
        }
        await FileStorage.save_json(str(thumb_dir / "thumbnail_meta.json"), meta)

        return {
            "thumbnail_path": str(output_path),
            "title": input_data.title,
            "background_asset_id": bg_asset.asset_id,
            "width": THUMB_W,
            "height": THUMB_H,
        }


# ── Helper functions ──────────────────────────────────────────────────────────

def _smart_crop(img, target_w: int, target_h: int):
    """Scale + center-crop image to exactly target_w × target_h."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), resample=3)  # LANCZOS

    # Center crop
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    return img


def _apply_gradient_overlay(img):
    """Apply a dark-to-transparent gradient over the bottom portion."""
    from PIL import Image
    import numpy as np

    arr = np.array(img).astype(float)  # H×W×3
    h, w = arr.shape[:2]

    gradient_h = int(h * GRADIENT_HEIGHT_RATIO)
    start_y = h - gradient_h

    # alpha goes from 0 (transparent) at top of gradient → 0.85 at bottom
    alpha = np.linspace(0.0, 0.85, gradient_h)[:, None, None]  # gradient_h×1×1

    # Darken only the gradient region
    arr[start_y:, :, :] = arr[start_y:, :, :] * (1 - alpha)

    result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return result


def _render_title(img, title: str) -> "Image":
    """Render wrapped title text with shadow onto the image."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)

    # Try progressively smaller font sizes until the text fits in 3 lines
    for font_size in (72, 60, 52, 44, 36):
        font = _find_font(font_size)
        lines = _wrap_text(title, font, MAX_TITLE_WIDTH, draw)
        if len(lines) <= 3:
            break

    line_bbox = draw.textbbox((0, 0), "가나다Ag", font=font)
    line_h = line_bbox[3] - line_bbox[1]
    line_gap = int(line_h * 0.3)
    block_h = len(lines) * line_h + (len(lines) - 1) * line_gap

    # Bottom-align: place last line TITLE_BOTTOM_Y px from image bottom
    base_y = THUMB_H - TITLE_BOTTOM_Y - block_h

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (THUMB_W - line_w) // 2   # centered
        y = base_y + i * (line_h + line_gap)

        # Stroke / shadow
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))

        # Main text: bright yellow-white for contrast
        draw.text((x, y), line, font=font, fill=(255, 248, 180))

    return img
