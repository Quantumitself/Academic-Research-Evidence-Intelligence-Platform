"""Value objects for the document reading service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderedPage:
    """A single rendered page of a document.

    Attributes
    ----------
    page_number:
        1-based page number.
    width_points:
        Page width in PDF points (72 points per inch).
    height_points:
        Page height in PDF points.
    pixel_width:
        Rendered image width in pixels at the requested DPI.
    pixel_height:
        Rendered image height in pixels at the requested DPI.
    dpi:
        Dots-per-inch value used for the render.
    image_bytes:
        PNG-encoded image data. The presentation layer converts these
        into a Qt pixmap.
    """

    page_number: int
    width_points: float
    height_points: float
    pixel_width: int
    pixel_height: int
    dpi: int
    image_bytes: bytes

    @property
    def aspect_ratio(self) -> float:
        if self.height_points <= 0:
            return 1.0
        return self.width_points / self.height_points


@dataclass(frozen=True, slots=True)
class DocumentOutlineEntry:
    """A single entry of a document outline (table of contents)."""

    level: int
    title: str
    page_number: int

    @property
    def is_top_level(self) -> bool:
        return self.level <= 1