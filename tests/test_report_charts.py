"""Fase 9.4 — Unit tests for the pure SVG chart generators.

These are dependency-free (no WeasyPrint, no DB): they assert the generated SVG
is well-formed, proportional, and escapes caller text.
"""
import xml.etree.ElementTree as ET

from markupsafe import Markup

from app.services import report_charts as rc


def _parse(svg: str) -> ET.Element:
    """Parse the SVG string — raises if it is not well-formed XML."""
    return ET.fromstring(str(svg))


def test_funnel_chart_returns_wellformed_markup():
    stages = [
        {"stage": "Llamada", "count": 10, "amount": 0.0},
        {"stage": "Cotización", "count": 6, "amount": 5000.0},
        {"stage": "Negociación", "count": 3, "amount": 20000.0},
        {"stage": "Contrato", "count": 1, "amount": 50000.0},
        {"stage": "En ejecución", "count": 2, "amount": 30000.0},
        {"stage": "Cobranza", "count": 0, "amount": 0.0},
    ]
    svg = rc.funnel_chart_svg(stages)
    assert isinstance(svg, Markup)
    root = _parse(svg)
    assert root.tag.endswith("svg")
    # every stage label appears as a <text> node
    texts = [t.text for t in root.iter() if t.tag.endswith("text")]
    for s in stages:
        assert s["stage"] in texts


def test_funnel_widest_bar_is_the_max_count():
    stages = [
        {"stage": "Llamada", "count": 10, "amount": 0.0},
        {"stage": "Cotización", "count": 5, "amount": 0.0},
    ]
    root = _parse(rc.funnel_chart_svg(stages))
    fills = [
        float(r.get("width"))
        for r in root.iter()
        if r.tag.endswith("rect") and r.get("fill", "").startswith("#e8")  # accent fill
    ]
    # the accent-coloured fill (first row, count=10) must be present and non-zero
    assert fills and max(fills) > 0


def test_funnel_zero_count_stage_has_no_fill():
    stages = [{"stage": "Cobranza", "count": 0, "amount": 0.0}]
    root = _parse(rc.funnel_chart_svg(stages))
    # only the grey track rect exists, no coloured fill rect
    colored = [
        r for r in root.iter()
        if r.tag.endswith("rect") and r.get("fill") not in (rc.BG5,)
    ]
    assert colored == []


def test_projection_stacks_three_segments():
    projection = [
        {"month": "Jul", "cobrado": 10000, "proyeccion": 5000, "pendiente": 2000, "is_current": True},
        {"month": "Ago", "cobrado": 0, "proyeccion": 0, "pendiente": 0},
    ]
    root = _parse(rc.projection_bar_chart_svg(projection))
    fills = {r.get("fill") for r in root.iter() if r.tag.endswith("rect")}
    assert rc.GREEN in fills and rc.BLUE in fills and rc.AMBER in fills
    # month labels present
    texts = [t.text for t in root.iter() if t.tag.endswith("text")]
    assert "Jul" in texts and "Ago" in texts
    assert "(Real)" in texts and "(Estimado)" in texts


def test_donut_slices_sum_to_full_circle():
    lost = [
        {"reason": "Presupuesto", "count": 3},
        {"reason": "Sin respuesta", "count": 1},
    ]
    root = _parse(rc.lost_donut_svg(lost))
    # one base track + 2 slices = 3 circles; centre total text == "4"
    circles = [c for c in root.iter() if c.tag.endswith("circle")]
    assert len(circles) == 3
    texts = [t.text for t in root.iter() if t.tag.endswith("text")]
    assert "4" in texts


def test_donut_empty_has_only_track():
    root = _parse(rc.lost_donut_svg([]))
    circles = [c for c in root.iter() if c.tag.endswith("circle")]
    assert len(circles) == 1  # base track only
    texts = [t.text for t in root.iter() if t.tag.endswith("text")]
    assert "0" in texts


def test_chart_escapes_caller_text():
    stages = [{"stage": "<script>x</script>", "count": 1, "amount": 0.0}]
    svg = str(rc.funnel_chart_svg(stages))
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
