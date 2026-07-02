"""Fase 9.5c — golden-file cover snapshot + D10 PDF sanity checks.

The cover golden is deterministic: a fixed talent (seed_deals), a fixed period,
and an injected generation timestamp (build_report_context(now=...)). The real
WeasyPrint PDF checks are skipped when the engine's system libs are unavailable.
"""
import io
from datetime import datetime
from pathlib import Path

import pytest

from app.models import Talent
from app.services import periods as periods_service
from app.services import reports as reports_service

FIXED_NOW = datetime(2026, 7, 1, 12, 0, 0)
GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_COVER = GOLDEN_DIR / "cover_seed.html"


def _seed_cover_html(db_session, seed_deals) -> str:
    """Render the cover fragment for the seeded talent with a fixed timestamp."""
    talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
    start, end = periods_service.parse_period("month", "2026-06")
    ctx = reports_service.build_report_context(
        db_session, [talent], "2026-06", start, end, now=FIXED_NOW
    )
    return reports_service._jinja_env.get_template("reports/cover.html").render(ctx=ctx)


def test_cover_golden(db_session, seed_deals):
    """The cover HTML must match the committed golden snapshot exactly (D10).

    First run (no golden yet) writes the snapshot and fails, prompting a commit;
    subsequent runs assert byte-for-byte equality.
    """
    cover_html = _seed_cover_html(db_session, seed_deals)

    if not GOLDEN_COVER.exists():
        GOLDEN_DIR.mkdir(exist_ok=True)
        GOLDEN_COVER.write_text(cover_html, encoding="utf-8")
        pytest.fail("golden cover snapshot created — review and re-run to lock it in")

    assert cover_html == GOLDEN_COVER.read_text(encoding="utf-8"), (
        "cover HTML drifted from the golden snapshot; if the change is intended, "
        "delete tests/golden/cover_seed.html and re-run to regenerate it"
    )


# --- D10 real-engine PDF sanity ------------------------------------------------
weasyprint = pytest.importorskip(
    "weasyprint",
    reason="WeasyPrint system libs (Pango/Cairo/GDK-Pixbuf) not available",
)
pdfplumber = pytest.importorskip("pdfplumber")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _render_seed_pdf(db_session, seed_deals) -> bytes:
    talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
    start, end = periods_service.parse_period("month", "2026-06")
    ctx = reports_service.build_report_context(
        db_session, [talent], "2026-06", start, end, now=FIXED_NOW
    )
    html = reports_service.render_report_html(ctx)
    return weasyprint.HTML(string=html, base_url=str(PROJECT_ROOT)).write_pdf()


def test_pdf_sanity_size_and_content(db_session, seed_deals):
    """D10: PDF > 20 KB and carries the talent name, period, and generation date."""
    talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
    pdf_bytes = _render_seed_pdf(db_session, seed_deals)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 20_000  # embedded Inter subset + layout (D10 sanity)

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert talent.name in text
    assert "Junio 2026" in text  # period in the cover title
    assert "2026-07-01 12:00 UTC" in text  # injected generation stamp (footer/cover)
