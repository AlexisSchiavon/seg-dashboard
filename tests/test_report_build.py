"""Fase 9.4 — Tests for the data-driven report build + HTML render (no Claude).

These exercise build_talent_report / build_report_context / render_report_html
against seeded data. They do NOT require WeasyPrint (they assert on the assembled
context and the rendered HTML string). The real-engine PDF smoke lives in
tests/test_report_render.py.
"""

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
    def test_returns_talent_facing_keys(self, db_session, seed_deals, seed_trello_cards):
        """Fase 9.7: the talent dataset carries only talent-appropriate keys."""
        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        start, end = _period()
        data = reports_service.build_talent_report(db_session, talent, start, end)

        for key in (
            "talent_name", "slug", "talent_kpis", "account_status",
            "signed_deals", "signed_count", "signed_total_70",
            "projection70", "projection70_svg",
        ):
            assert key in data

        # TA-internal fields must NOT leak into the talent dataset (D-9.7). Note
        # headline_kpis is gone too (P1): the cover no longer shows KPIs.
        for gone in ("headline_kpis", "detail_kpis", "funnel", "lost_summary",
                     "top_deals", "funnel_svg", "donut_svg", "projection_svg"):
            assert gone not in data

        # Talent KPIs are the 70% headline numbers
        assert set(data["talent_kpis"]) == {
            "firmadas_count", "firmadas_70", "cobrado_70", "por_cobrar_70",
        }
        # Account-status buckets present
        assert set(data["account_status"]) == {"proximos_meses", "retraso", "cobrado_ano"}
        # Projection chart is inlineable Markup SVG
        assert isinstance(data["projection70_svg"], Markup)
        assert str(data["projection70_svg"]).lstrip().startswith("<svg")


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
        # P1: the cover carries no KPI data
        assert "cover_kpis" not in ctx

    def test_consolidated_context_is_branding_only(self, db_session, seed_deals, seed_trello_cards):
        talents = db_session.query(Talent).filter(Talent.active.is_(True)).all()
        assert len(talents) >= 2  # sanity: seed provides multiple talents
        start, end = _period()
        ctx = reports_service.build_report_context(db_session, talents, "2026-06", start, end)

        assert ctx["is_consolidated"] is True
        assert ctx["title"] == "Reporte consolidado"
        assert ctx["talent_count"] == len(talents)
        assert len(ctx["talents"]) == len(talents)
        # P1: no aggregated sensitive KPIs on the cover
        assert "cover_kpis" not in ctx


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
        # talent-facing section titles
        assert "Estado de tus cuentas" in html
        assert "Detalle de campañas firmadas del mes" in html
        assert "Proyección de tus próximos ingresos" in html
        assert "Talent Agency gestiona el proceso de cobro" in html  # disclaimer
        # TA-internal widgets removed (D-9.7)
        assert "Embudo del talento" not in html
        assert "Pipeline" not in html
        assert "Comisión" not in html
        assert "Oportunidades perdidas" not in html
        # SVG charts inlined (not escaped)
        assert "<svg" in html
        # no unrendered Jinja tokens leaked into the output
        assert "{{" not in html and "{%" not in html
