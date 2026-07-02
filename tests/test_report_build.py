"""Fase 9.4 — Tests for the data-driven report build + HTML render (no Claude).

These exercise build_talent_report / build_report_context / render_report_html
against seeded data. They do NOT require WeasyPrint (they assert on the assembled
context and the rendered HTML string). The real-engine PDF smoke lives in
tests/test_report_render.py.
"""

import pytest
from markupsafe import Markup

from app.models import Talent
from app.services import periods as periods_service
from app.services import reports as reports_service


def _period():
    return periods_service.parse_period("month", "2026-06")


class TestSlugAndLabels:
    def test_slug_strips_accents_lowercases_hyphenates(self):
        assert reports_service.filename_slug("Emicánico Pérez") == "emicanico-perez"
        assert reports_service.filename_slug("Don Silverio y Don Wicho") == "don-silverio-y-don-wicho"

    def test_slug_falls_back_for_empty(self):
        assert reports_service.filename_slug("") == "talento"
        assert reports_service.filename_slug("   ") == "talento"

    def test_period_label_month_and_quarter(self):
        assert reports_service._period_label("2026-06") == "Junio 2026"
        assert reports_service._period_label("2026-Q2") == "Q2 2026"


class TestBuildTalentReport:
    def test_returns_all_widget_keys(self, db_session, seed_deals, seed_trello_cards):
        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        start, end = _period()
        data = reports_service.build_talent_report(db_session, talent, start, end)

        for key in (
            "talent_name", "slug", "headline_kpis", "detail_kpis", "funnel",
            "lost_summary", "projection", "calendar", "top_deals",
            "signed_deals", "signed_total", "funnel_svg", "projection_svg", "donut_svg",
        ):
            assert key in data

        # 3 headline tiles (firmadas/cobrado/pendiente), 3 snapshot tiles
        assert [t["label"] for t in data["headline_kpis"]] == [
            "Campañas firmadas", "Cobrado", "Pendiente por cobrar",
        ]
        # funnel has all 6 canonical stages
        assert len(data["funnel"]) == 6
        # charts are inlineable Markup SVGs
        assert isinstance(data["funnel_svg"], Markup)
        assert str(data["funnel_svg"]).lstrip().startswith("<svg")

    def test_funnel_includes_trello_stages_h0901(self, db_session, seed_deals, seed_trello_cards):
        """H-04 / H-09-01: the report funnel overlays the Trello-sourced stages
        (En ejecución / Cobranza) via funnel_service.talent_funnel.

        seed_trello_cards links card_ejecucion → deal_open (talent_a), so that
        talent's 'En ejecución' stage must be populated (was always 0 pre-9.2).
        """
        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        start, end = _period()
        data = reports_service.build_talent_report(db_session, talent, start, end)

        stages = {s["stage"]: s for s in data["funnel"]}
        assert stages["En ejecución"]["count"] >= 1


class TestBuildReportContext:
    def test_single_talent_context(self, db_session, seed_deals, seed_trello_cards):
        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        start, end = _period()
        ctx = reports_service.build_report_context(db_session, [talent], "2026-06", start, end)

        assert ctx["is_consolidated"] is False
        assert ctx["title"] == talent.name
        assert ctx["period_label"] == "Junio 2026"
        assert len(ctx["talents"]) == 1
        assert "UTC" in ctx["generated_stamp"]

    def test_consolidated_context_aggregates_kpis(self, db_session, seed_deals, seed_trello_cards):
        talents = db_session.query(Talent).filter(Talent.active.is_(True)).all()
        assert len(talents) >= 2  # sanity: seed provides multiple talents
        start, end = _period()
        ctx = reports_service.build_report_context(db_session, talents, "2026-06", start, end)

        assert ctx["is_consolidated"] is True
        assert ctx["title"] == "Reporte consolidado"
        assert len(ctx["talents"]) == len(talents)
        # aggregated headline value == sum of per-talent headline values
        agg_firmadas = ctx["cover_kpis"][0]["value"]
        per_talent_sum = sum(t["headline_kpis"][0]["value"] for t in ctx["talents"])
        assert agg_firmadas == pytest.approx(per_talent_sum)


class TestRenderHtml:
    def test_render_contains_widgets_and_no_unrendered_jinja(
        self, db_session, seed_deals, seed_trello_cards
    ):
        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        start, end = _period()
        ctx = reports_service.build_report_context(db_session, [talent], "2026-06", start, end)
        html = reports_service.render_report_html(ctx)

        assert talent.name in html
        assert "Junio 2026" in html
        # section titles from the widgets
        assert "Embudo del talento" in html
        assert "Deals firmados en el periodo" in html
        assert "Top campañas firmadas" in html
        # SVG charts inlined (not escaped)
        assert "<svg" in html
        # no unrendered Jinja tokens leaked into the output
        assert "{{" not in html and "{%" not in html
