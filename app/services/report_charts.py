"""Fase 9.4 — Pure-Python SVG chart generators for the PDF report (D5).

Charts are emitted as inline SVG strings (no matplotlib — avoids ~50MB in the
container, D5). WeasyPrint renders inline SVG natively with high fidelity and it
scales cleanly to the A4 page.

Colours are hard-coded hex mirroring frontend/css/styles.css :root tokens, because
SVG presentation attributes inside WeasyPrint do not resolve CSS custom properties
(var(--x)) reliably — hex keeps the charts identical to the dashboard.

Every function returns a markupsafe.Markup so Jinja2 (autoescape=True) inlines the
SVG verbatim instead of HTML-escaping it. All caller-supplied text is escaped via
markupsafe.escape before interpolation (defence in depth — chart labels come from
talent/deal names).
"""
from __future__ import annotations

from markupsafe import Markup, escape

# ---- Palette (hex mirror of styles.css :root) ---------------------------------
ACCENT = "#e8520a"
AMBER = "#c97c14"
GREEN = "#1a9e6e"
PURPLE = "#6b54d6"
BLUE = "#2472c8"
RED = "#c43232"
TEXT = "#eeede6"
TEXT2 = "#8a8980"
TEXT3 = "#4e4e4a"
GREEN_T = "#3dcf96"
AMBER_T = "#f0a93a"
BLUE_T = "#6aabf0"
PURPLE_T = "#a594f0"
BG3 = "#18181c"
BG4 = "#1f1f24"
BG5 = "#26262c"

# Cycle used by the dashboard funnel bars (FUNNEL_COLORS).
FUNNEL_COLORS = [ACCENT, AMBER, GREEN, PURPLE, BLUE, TEXT3]
# Cycle used by the lost-opportunity donut (DONUT_COLORS).
DONUT_COLORS = [ACCENT, PURPLE, GREEN, AMBER, BLUE, TEXT2]


def _fmt_mxn(value: float) -> str:
    """Compact MXN formatting matching dashboard.js formatMXN ($, $K, $M)."""
    v = float(value or 0)
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def funnel_chart_svg(stages: list[dict], width: int = 300) -> Markup:
    """Horizontal bar funnel matching renderTalentFunnel() bars.

    `stages` is a list of {stage, count, amount} in canonical order. Bars are
    scaled to the max count (min 1). Bar width mirrors the dashboard: at least 4%
    when count>0 so a tiny stage is still visible.

    The SVG is emitted at width="100%" over a viewBox sized to `width` (the target
    column width in CSS px) so it scales to fit the widget without overflowing —
    text stays legible because the coordinate space ≈ the rendered size.
    """
    label_w = 108           # label column (scaled for the ~300px half-column)
    count_w = 22            # matches .f-n column
    gap = 8
    row_h = 22              # matches .f-track height
    row_gap = 9
    track_x = label_w + gap
    track_w = width - track_x - count_w - gap

    max_count = max((s["count"] for s in stages), default=0) or 1
    height = len(stages) * (row_h + row_gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet" '
        f'font-family="Inter, sans-serif">'
    ]
    for i, s in enumerate(stages):
        y = i * (row_h + row_gap)
        cy = y + row_h / 2
        color = FUNNEL_COLORS[i % len(FUNNEL_COLORS)]
        count = int(s["count"])
        pct = max((count / max_count), 0.04 if count > 0 else 0.0)
        fill_w = track_w * pct
        label = escape(str(s["stage"]))
        # label
        parts.append(
            f'<text x="0" y="{cy}" dominant-baseline="middle" font-size="12" '
            f'fill="{TEXT2}">{label}</text>'
        )
        # track
        parts.append(
            f'<rect x="{track_x}" y="{y}" width="{track_w}" height="{row_h}" '
            f'rx="5" fill="{BG5}"/>'
        )
        # fill
        if fill_w > 0:
            parts.append(
                f'<rect x="{track_x}" y="{y}" width="{fill_w:.1f}" height="{row_h}" '
                f'rx="5" fill="{color}"/>'
            )
        # count inside the fill (right-aligned) when it fits
        if count > 0 and fill_w > 24:
            parts.append(
                f'<text x="{track_x + fill_w - 8:.1f}" y="{cy}" text-anchor="end" '
                f'dominant-baseline="middle" font-size="11" font-weight="600" '
                f'fill="rgba(255,255,255,0.9)">{count}</text>'
            )
        # count column at the far right
        parts.append(
            f'<text x="{width}" y="{cy}" text-anchor="end" dominant-baseline="middle" '
            f'font-size="12" fill="{TEXT2}">{count}</text>'
        )
    parts.append("</svg>")
    return Markup("".join(parts))


def projection_bar_chart_svg(projection: list[dict], width: int = 300) -> Markup:
    """Vertical stacked bars matching renderIncomeProjection().

    `projection` is a list of {month, cobrado, proyeccion, pendiente, is_current?}.
    Segments stack cobrado (green) → proyeccion/En campaña (blue) → pendiente (amber),
    scaled to the tallest column total. Emitted at width="100%" (see funnel note).
    """
    height = 210
    top_pad = 20            # room for the total label above each bar
    bottom_pad = 34         # room for the month / (Real|Estimado) labels
    plot_h = height - top_pad - bottom_pad
    n = max(len(projection), 1)
    gap = 8
    col_w = (width - gap * (n - 1)) / n

    def total(m: dict) -> float:
        return (m.get("cobrado") or 0) + (m.get("proyeccion") or 0) + (m.get("pendiente") or 0)

    max_val = max((total(m) for m in projection), default=0) or 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet" '
        f'font-family="Inter, sans-serif">'
    ]
    for i, m in enumerate(projection):
        x = i * (col_w + gap)
        cx = x + col_w / 2
        t = total(m)
        bar_h = plot_h * (t / max_val)
        base_y = top_pad + plot_h
        # stack from the bottom up
        segs = [
            (m.get("cobrado") or 0, GREEN),
            (m.get("proyeccion") or 0, BLUE),
            (m.get("pendiente") or 0, AMBER),
        ]
        y_cursor = base_y
        if t <= 0:
            # empty-column placeholder: thin dashed cap
            parts.append(
                f'<rect x="{x:.1f}" y="{base_y - 6:.1f}" width="{col_w:.1f}" height="6" '
                f'rx="3" fill="none" stroke="{TEXT3}" stroke-dasharray="3 2" opacity="0.4"/>'
            )
        else:
            for val, color in segs:
                if val <= 0:
                    continue
                seg_h = plot_h * (val / max_val)
                y_cursor -= seg_h
                parts.append(
                    f'<rect x="{x:.1f}" y="{y_cursor:.1f}" width="{col_w:.1f}" '
                    f'height="{seg_h:.1f}" fill="{color}"/>'
                )
                if seg_h > 16:
                    parts.append(
                        f'<text x="{cx:.1f}" y="{y_cursor + seg_h / 2:.1f}" '
                        f'text-anchor="middle" dominant-baseline="middle" font-size="10" '
                        f'font-weight="700" fill="#fff">{_fmt_mxn(val)}</text>'
                    )
            # total label above the bar
            parts.append(
                f'<text x="{cx:.1f}" y="{base_y - bar_h - 5:.1f}" text-anchor="middle" '
                f'font-size="10" fill="{TEXT2}">{_fmt_mxn(t)}</text>'
            )
        # month + sublabel
        month = escape(str(m.get("month", "")))
        sub = "(Real)" if m.get("is_current") else "(Estimado)"
        parts.append(
            f'<text x="{cx:.1f}" y="{base_y + 16:.1f}" text-anchor="middle" '
            f'font-size="10" font-weight="600" fill="{TEXT2}">{month}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{base_y + 28:.1f}" text-anchor="middle" '
            f'font-size="9" font-style="italic" fill="{TEXT3}">{sub}</text>'
        )
    parts.append("</svg>")
    return Markup("".join(parts))


def talent_projection_svg(projection70: list[dict], width: int = 680) -> Markup:
    """Fase 9.7 — single-value monthly bars for the talent's 'Estimado a cobrar'.

    `projection70` is a list of {month, estimado70, is_current, has_data}. Each
    month is one green bar (the talent's 70% still to be collected). Months with
    no data render a dashed baseline + 'Sin cobros programados'. No internal
    breakdown by list_state is exposed (talent audience).
    """
    height = 200
    top_pad = 22
    bottom_pad = 30
    plot_h = height - top_pad - bottom_pad
    n = max(len(projection70), 1)
    gap = 14
    col_w = (width - gap * (n - 1)) / n
    max_val = max((m.get("estimado70") or 0 for m in projection70), default=0) or 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet" '
        f'font-family="Inter, sans-serif">'
    ]
    base_y = top_pad + plot_h
    for i, m in enumerate(projection70):
        x = i * (col_w + gap)
        cx = x + col_w / 2
        val = m.get("estimado70") or 0
        month = escape(str(m.get("month", "")))
        if val <= 0:
            parts.append(
                f'<rect x="{x:.1f}" y="{base_y - 5:.1f}" width="{col_w:.1f}" height="5" '
                f'rx="2" fill="none" stroke="{TEXT3}" stroke-dasharray="3 2" opacity="0.5"/>'
            )
            parts.append(
                f'<text x="{cx:.1f}" y="{base_y - 12:.1f}" text-anchor="middle" '
                f'font-size="9" fill="{TEXT3}">Sin cobros</text>'
            )
        else:
            bar_h = plot_h * (val / max_val)
            parts.append(
                f'<rect x="{x:.1f}" y="{base_y - bar_h:.1f}" width="{col_w:.1f}" '
                f'height="{bar_h:.1f}" rx="4" fill="{GREEN}"/>'
            )
            parts.append(
                f'<text x="{cx:.1f}" y="{base_y - bar_h - 6:.1f}" text-anchor="middle" '
                f'font-size="11" font-weight="700" fill="{GREEN_T}">{_fmt_mxn(val)}</text>'
            )
        parts.append(
            f'<text x="{cx:.1f}" y="{base_y + 16:.1f}" text-anchor="middle" '
            f'font-size="10" font-weight="600" fill="{TEXT2}">{month}</text>'
        )
    parts.append("</svg>")
    return Markup("".join(parts))


def lost_donut_svg(lost_summary: list[dict], size: int = 92) -> Markup:
    """Donut (ring) of lost opportunities by reason, matching renderLostOpportunities().

    `lost_summary` is a list of {reason, count}. Slices use DONUT_COLORS. The ring
    is drawn as stroked circle arcs via stroke-dasharray so no conic-gradient (which
    WeasyPrint does not support) is needed. The legend is rendered by the template.
    """
    total = sum(int(r["count"]) for r in lost_summary) or 0
    cx = cy = size / 2
    stroke = 16
    r = (size - stroke) / 2
    circ = 2 * 3.141592653589793 * r

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">'
    ]
    # base track
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BG5}" '
        f'stroke-width="{stroke}"/>'
    )
    if total > 0:
        offset = 0.0
        # rotate -90deg so the first slice starts at 12 o'clock
        for i, row in enumerate(lost_summary):
            frac = int(row["count"]) / total
            seg = circ * frac
            color = DONUT_COLORS[i % len(DONUT_COLORS)]
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke}" '
                f'stroke-dasharray="{seg:.2f} {circ - seg:.2f}" '
                f'stroke-dashoffset="{-offset:.2f}" '
                f'transform="rotate(-90 {cx} {cy})"/>'
            )
            offset += seg
    # centre total
    parts.append(
        f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Inter, sans-serif" font-size="18" font-weight="700" '
        f'fill="{TEXT}">{total}</text>'
    )
    parts.append("</svg>")
    return Markup("".join(parts))
