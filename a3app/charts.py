"""Server-side SVG chart for KPI measurements (no JavaScript / external libraries)."""
from markupsafe import Markup, escape

W, H, PAD_L, PAD_R, PAD_T, PAD_B = 640, 260, 55, 110, 15, 40


def kpi_chart(measurements, baseline, target):
    pts = [(m["m_date"], m["value"]) for m in measurements if m["value"] is not None]
    if not pts:
        return Markup('<p class="muted">No measurements yet.</p>')
    values = [v for _, v in pts] + [x for x in (baseline, target) if x is not None]
    lo, hi = min(values), max(values)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    span = hi - lo
    lo, hi = lo - span * 0.08, hi + span * 0.08
    pw, ph = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    def x(i):
        return PAD_L + (pw * i / (len(pts) - 1) if len(pts) > 1 else pw / 2)

    def y(v):
        return PAD_T + ph * (1 - (v - lo) / (hi - lo))

    parts = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="KPI trend">',
             f'<rect x="{PAD_L}" y="{PAD_T}" width="{pw}" height="{ph}" fill="#fafafa" stroke="#ccc"/>']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        parts.append(f'<text x="{PAD_L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="11">{v:.4g}</text>')
    for label, val, color in (("Baseline", baseline, "#888"), ("Target", target, "#2e7d32")):
        if val is not None:
            parts.append(f'<line x1="{PAD_L}" x2="{PAD_L + pw}" y1="{y(val):.1f}" y2="{y(val):.1f}" '
                         f'stroke="{color}" stroke-dasharray="6 4"/>')
            parts.append(f'<text x="{PAD_L + pw + 6}" y="{y(val) + 4:.1f}" font-size="11" fill="{color}">'
                         f'{label} {val:.4g}</text>')
    poly = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(pts))
    parts.append(f'<polyline points="{poly}" fill="none" stroke="#ff5f00" stroke-width="2"/>')
    step = max(1, len(pts) // 8)
    for i, (d, v) in enumerate(pts):
        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="#ff5f00">'
                     f'<title>{escape(d)}: {v:.4g}</title></circle>')
        if i % step == 0 or i == len(pts) - 1:
            parts.append(f'<text x="{x(i):.1f}" y="{H - PAD_B + 16}" text-anchor="middle" font-size="10">'
                         f'{escape(d)}</text>')
    parts.append("</svg>")
    return Markup("".join(parts))
