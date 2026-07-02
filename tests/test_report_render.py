"""Fase 9.3 — Real WeasyPrint render smoke tests.

Unlike tests/test_reports.py (which mocks WeasyPrint via the mock_weasyprint
fixture), these tests exercise the REAL engine to verify the base setup:
the Inter Variable font embeds and the @page/A4 CSS renders.

They are skipped automatically when WeasyPrint's system libraries (Pango,
Cairo, GDK-Pixbuf) are unavailable — e.g. a bare CI runner. Locally run with:

    DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/test_report_render.py
"""
import io
from pathlib import Path

import pytest

# Skip the whole module if the real WeasyPrint stack can't be imported
# (missing Pango/Cairo). Everything below needs the real renderer.
weasyprint = pytest.importorskip(
    "weasyprint",
    reason="WeasyPrint system libs (Pango/Cairo/GDK-Pixbuf) not available",
)
pdfplumber = pytest.importorskip("pdfplumber")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_CSS = PROJECT_ROOT / "app" / "templates" / "reports" / "report.css"
INTER_FONT = PROJECT_ROOT / "app" / "static" / "fonts" / "Inter.woff2"


def _render(html_body: str) -> bytes:
    """Render an HTML fragment with the base report.css to PDF bytes.

    base_url is the project root (absolute) so the @font-face url()
    'app/static/fonts/Inter.woff2' resolves regardless of the pytest CWD.
    """
    css_text = REPORT_CSS.read_text(encoding="utf-8")
    html_doc = (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        f"<style>{css_text}</style></head><body>{html_body}</body></html>"
    )
    return weasyprint.HTML(
        string=html_doc, base_url=str(PROJECT_ROOT)
    ).write_pdf()


def test_inter_font_file_present():
    """The embedded font asset must exist and be a real WOFF2 file."""
    assert INTER_FONT.exists(), f"Missing Inter font at {INTER_FONT}"
    # WOFF2 magic number is 'wOF2'
    assert INTER_FONT.read_bytes()[:4] == b"wOF2"


def test_smoke_pdf_renders_and_extracts_text():
    """A trivial 'Hello Talent Agency' page renders and text is extractable."""
    pdf_bytes = _render(
        "<h1 style=\"font-family:'Inter'\">Hello Talent Agency</h1>"
    )
    assert pdf_bytes[:5] == b"%PDF-"

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Hello Talent Agency" in text


def test_smoke_pdf_embeds_inter_font():
    """WeasyPrint must embed Inter (not fall back to a system serif) — R1 defense.

    WeasyPrint 66+ compresses PDF object streams, so the font name is not in the
    plaintext bytes. We instead read each glyph's fontname via pdfplumber: when
    Inter is embedded the subset name looks like 'ABCDEF+Inter-Regular/-Bold';
    the fallback would report a serif (e.g. 'PT-Serif').
    """
    pdf_bytes = _render(
        "<p style=\"font-family:'Inter'\">Talent Agency 2026</p>"
    )
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        fontnames = {c.get("fontname", "") for c in pdf.pages[0].chars}

    assert fontnames, "no glyphs rendered"
    assert all("Inter" in fn for fn in fontnames), (
        f"Inter not embedded — got fallback fonts: {fontnames}"
    )
