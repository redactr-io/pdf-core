from __future__ import annotations

import contextlib
import hashlib
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

import fitz

if TYPE_CHECKING:
    from pdf_service.core.types import RedactionStyleConfig

# Size thresholds for two-tier graceful degradation
LARGE_MIN_WIDTH = 80.0
LARGE_MIN_HEIGHT = 20.0
MEDIUM_MIN_WIDTH = 30.0
MEDIUM_MIN_HEIGHT = 10.0

# Icon sizing
ICON_PADDING = 2.0
ICON_MAX_SIZE = 20.0

# Rounded rectangle corner radius (clamped to half the smallest dimension)
BORDER_RADIUS = 3.0

# Padding between the branded frame and the redaction annotation
FRAME_PADDING = 3.0


def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Convert '#RRGGBB' hex color to PyMuPDF (0.0-1.0) RGB tuple."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_str!r}")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        raise ValueError(f"Invalid hex color: {hex_str!r}") from None
    return r / 255.0, g / 255.0, b / 255.0


def generate_redaction_id(page: int, x0: float, y0: float, x1: float, y1: float) -> str:
    """SHA-256 of packed coords, truncated to 12 hex chars."""
    data = struct.pack(">iffff", page, x0, y0, x1, y1)
    return hashlib.sha256(data).hexdigest()[:12]


@dataclass(frozen=True)
class BrandingStyle:
    fill_color: tuple[float, float, float]
    border_color: tuple[float, float, float]
    text_color: tuple[float, float, float]
    icon_png: bytes | None
    label_prefix: str

    @classmethod
    def from_config(cls, config: RedactionStyleConfig | None) -> BrandingStyle | None:
        """Build from config dict. Returns None if config is None."""
        if config is None:
            return None
        fill = hex_to_rgb(config.get("fill_color", "#000000"))
        return cls(
            fill_color=fill,
            border_color=(
                hex_to_rgb(config.get("border_color", ""))
                if config.get("border_color")
                else fill
            ),
            text_color=hex_to_rgb(config.get("text_color", "#FFFFFF")),
            icon_png=config.get("icon_png"),
            label_prefix=config.get("label_prefix", "ID:"),
        )


def _draw_rounded_rect(
    page: fitz.Page,
    rect: fitz.Rect,
    radius: float,
    border_color: tuple[float, float, float],
    fill_color: tuple[float, float, float],
) -> None:
    """Draw a filled rounded rectangle using a Shape with cubic bezier corners."""
    r = min(radius, rect.width / 2, rect.height / 2)
    # Quadratic-to-cubic conversion factor
    k = 2.0 / 3.0
    shape = page.new_shape()

    # Top edge
    shape.draw_line(
        fitz.Point(rect.x0 + r, rect.y0),
        fitz.Point(rect.x1 - r, rect.y0),
    )
    # Top-right corner (cubic bezier approximation of quarter arc)
    shape.draw_bezier(
        fitz.Point(rect.x1 - r, rect.y0),
        fitz.Point(rect.x1 - r + k * r, rect.y0),
        fitz.Point(rect.x1, rect.y0 + r - k * r),
        fitz.Point(rect.x1, rect.y0 + r),
    )
    # Right edge
    shape.draw_line(
        fitz.Point(rect.x1, rect.y0 + r),
        fitz.Point(rect.x1, rect.y1 - r),
    )
    # Bottom-right corner
    shape.draw_bezier(
        fitz.Point(rect.x1, rect.y1 - r),
        fitz.Point(rect.x1, rect.y1 - r + k * r),
        fitz.Point(rect.x1 - r + k * r, rect.y1),
        fitz.Point(rect.x1 - r, rect.y1),
    )
    # Bottom edge
    shape.draw_line(
        fitz.Point(rect.x1 - r, rect.y1),
        fitz.Point(rect.x0 + r, rect.y1),
    )
    # Bottom-left corner
    shape.draw_bezier(
        fitz.Point(rect.x0 + r, rect.y1),
        fitz.Point(rect.x0 + r - k * r, rect.y1),
        fitz.Point(rect.x0, rect.y1 - r + k * r),
        fitz.Point(rect.x0, rect.y1 - r),
    )
    # Left edge
    shape.draw_line(
        fitz.Point(rect.x0, rect.y1 - r),
        fitz.Point(rect.x0, rect.y0 + r),
    )
    # Top-left corner
    shape.draw_bezier(
        fitz.Point(rect.x0, rect.y0 + r),
        fitz.Point(rect.x0, rect.y0 + r - k * r),
        fitz.Point(rect.x0 + r - k * r, rect.y0),
        fitz.Point(rect.x0 + r, rect.y0),
    )
    shape.finish(color=border_color, fill=fill_color, width=0.5)
    shape.commit()


def draw_branding(
    page: fitz.Page,
    rect: fitz.Rect,
    redaction_id: str,
    style: BrandingStyle,
) -> None:
    """Draw branded redaction overlay with two-tier degradation.

    The branded frame expands outward from the redaction rect by FRAME_PADDING,
    creating a visible coloured border around the viewer's black redaction box.

    Small  (< MEDIUM_MIN_WIDTH x MEDIUM_MIN_HEIGHT): rounded rect + border + logo.
    Medium+ (>= 30x10): rounded rect + border + logo + ID text (bottom-right).
    """
    width = rect.width
    height = rect.height

    # Expand outward so the branded frame is visible around the black redaction box.
    is_medium = width >= MEDIUM_MIN_WIDTH and height >= MEDIUM_MIN_HEIGHT
    frame = fitz.Rect(
        rect.x0 - FRAME_PADDING,
        rect.y0 - FRAME_PADDING,
        rect.x1 + FRAME_PADDING,
        rect.y1 + FRAME_PADDING,
    )

    # Always: filled rounded rectangle with border
    _draw_rounded_rect(page, frame, BORDER_RADIUS, style.border_color, style.fill_color)

    is_large = width >= LARGE_MIN_WIDTH and height >= LARGE_MIN_HEIGHT

    # Compute icon rect up front (needed for text left-margin and image insertion).
    icon_rect = None
    if style.icon_png:
        icon_size = min(height - 2 * ICON_PADDING, ICON_MAX_SIZE)
        if icon_size > 4:
            icon_rect = fitz.Rect(
                frame.x0,
                frame.y0,
                frame.x0 + icon_size,
                frame.y0 + icon_size,
            )

    # Medium+: ID text at bottom-right inside the redaction area — added as
    # a FreeText annotation so it is not extractable page-content text.
    if is_medium:
        label = f"{style.label_prefix} {redaction_id}"
        fontsize = min(7.0 if is_large else 5.5, height - 4.0)
        # Push text left edge past the icon so the annotation doesn't cover it
        text_x0 = icon_rect.x1 if icon_rect else frame.x0
        if fontsize >= 4.0:
            text_rect = fitz.Rect(
                text_x0,
                frame.y1 - fontsize - 2.0,
                frame.x1 - 2.5,
                frame.y1,
            )
            annot = page.add_freetext_annot(
                text_rect,
                label,
                fontsize=fontsize,
                fontname="helv",
                text_color=style.text_color,
                fill_color=style.fill_color,  # match frame background
                align=2,  # right-aligned
            )
            annot.set_flags(
                fitz.PDF_ANNOT_IS_READ_ONLY
                | fitz.PDF_ANNOT_IS_LOCKED
                | fitz.PDF_ANNOT_IS_LOCKED_CONTENTS
            )
            annot.update()

    # Icon at top-left of frame (all sizes, when icon_png provided and fits).
    if icon_rect is not None:
        with contextlib.suppress(Exception):
            page.insert_image(icon_rect, stream=style.icon_png)
