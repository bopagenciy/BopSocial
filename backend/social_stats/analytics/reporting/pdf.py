"""
Server-side deterministic PDF renderer for Bop Social Executive Reporting (BS-4G).
Converts structured report_data into print-ready A4 PDF using WeasyPrint and inline SVG.
"""
import hashlib
import os
from typing import Any, Dict, Tuple
from django.utils.html import escape

from .templates import BRANDING, get_report_strings


def _generate_sparkline_svg(series: list, metric_key: str, width: int = 160, height: int = 36, color: str = "#00D7FF") -> str:
    """Generates an inline SVG sparkline for a trend series."""
    values = [float(item[metric_key]) for item in series if metric_key in item and item[metric_key] is not None]
    if len(values) < 2:
        return ""
    min_v = min(values)
    max_v = max(values)
    diff = max_v - min_v if max_v != min_v else 1.0

    points = []
    n = len(values)
    for i, v in enumerate(values):
        x = (i / (n - 1)) * (width - 10) + 5
        y = height - 5 - ((v - min_v) / diff) * (height - 10)
        points.append(f"{x:.1f},{y:.1f}")

    pts_str = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="vertical-align: middle;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{pts_str}" />'
        f'</svg>'
    )


def render_report_html(report_data: Dict[str, Any], language: str = "es") -> str:
    """
    Renders structured report payload into pristine, print-styled HTML+CSS.
    Supports complete Spanish typography, UTF-8 charset, and page counters.
    """
    strings = get_report_strings(language)
    c = report_data.get("cover", {})
    metadata = report_data.get("metadata", {})
    kpis = report_data.get("kpi_overview", {}).get("kpis", [])
    exec_summary = report_data.get("executive_summary", {})
    trends = report_data.get("performance_trends", {}).get("series", [])
    content = report_data.get("content_performance", {}).get("top_posts", [])
    signals = report_data.get("business_intelligence_signals", {}).get("signals", [])
    platforms = report_data.get("platform_breakdown", {}).get("platforms", [])
    formats = report_data.get("winning_formats", {})
    post_time = report_data.get("posting_time_insights", {})
    health = report_data.get("data_health", {})
    methodology = report_data.get("methodology", {}).get("points", [])

    colors = BRANDING["colors"]

    # Generate sparkline if trend data exists
    trend_svg = ""
    if len(trends) >= 2:
        trend_svg = _generate_sparkline_svg(trends, "REACTIONS", width=340, height=45, color=colors["accent_cyan"])

    html = f"""<!DOCTYPE html>
<html lang="{escape(language)}">
<head>
<meta charset="utf-8">
<title>{escape(c.get('title', 'Informe Ejecutivo'))}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 14mm 14mm 16mm 14mm;
    @bottom-center {{
      content: "{escape(BRANDING['company_name'])} · " counter(page) " / " counter(pages);
      font-size: 8pt;
      color: {colors['text_tertiary']};
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}
  }}

  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: {colors['text_primary']};
    margin: 0;
    padding: 0;
  }}

  .page-break {{
    page-break-after: always;
  }}

  /* ── Cover Page ── */
  .cover-container {{
    min-height: 250mm;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding-top: 30mm;
  }}

  .cover-badge {{
    display: inline-block;
    background: {colors['primary_dark']};
    color: #FFFFFF;
    font-weight: 800;
    font-size: 10pt;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 6px;
  }}

  .cover-title {{
    font-size: 26pt;
    font-weight: 800;
    color: {colors['primary_dark']};
    line-height: 1.15;
    margin: 20px 0 10px 0;
  }}

  .cover-gold-strip {{
    width: 60px;
    height: 4px;
    background: {colors['accent_gold']};
    margin-bottom: 24px;
  }}

  .cover-subtitle {{
    font-size: 12pt;
    color: {colors['text_secondary']};
    line-height: 1.5;
    max-width: 140mm;
  }}

  .cover-meta-grid {{
    background: {colors['surface_bg']};
    border: 1px solid {colors['border']};
    border-radius: 12px;
    padding: 20px 24px;
    margin-top: 40mm;
    display: table;
    width: 100%;
    box-sizing: border-box;
  }}

  .meta-row {{
    display: table-row;
  }}

  .meta-cell-label {{
    display: table-cell;
    padding: 8px 12px;
    font-size: 8.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: {colors['text_tertiary']};
    width: 35%;
  }}

  .meta-cell-val {{
    display: table-cell;
    padding: 8px 12px;
    font-size: 10.5pt;
    font-weight: 700;
    color: {colors['text_primary']};
  }}

  /* ── Content Sections ── */
  .section-header {{
    border-bottom: 2px solid {colors['primary_dark']};
    padding-bottom: 6px;
    margin: 24px 0 14px 0;
  }}

  .section-title {{
    font-size: 13pt;
    font-weight: 800;
    color: {colors['primary_dark']};
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 0;
  }}

  .bullet-box {{
    background: {colors['surface_bg']};
    border-left: 4px solid {colors['accent_gold']};
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 14px;
  }}

  .bullet-box ul {{
    margin: 0;
    padding-left: 18px;
  }}

  .bullet-box li {{
    margin-bottom: 6px;
    color: {colors['text_primary']};
    font-size: 9.5pt;
    line-height: 1.4;
  }}

  /* ── KPI Grid ── */
  .kpi-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 18px;
  }}

  .kpi-table th {{
    background: {colors['primary_dark']};
    color: #FFFFFF;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    text-align: left;
    padding: 8px 10px;
  }}

  .kpi-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid {colors['border']};
    font-size: 9pt;
  }}

  .kpi-table tr:nth-child(even) td {{
    background: {colors['surface_bg']};
  }}

  .val-strong {{
    font-weight: 800;
    color: {colors['text_primary']};
  }}

  .badge {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 7.5pt;
    font-weight: 800;
    text-transform: uppercase;
  }}

  .badge-info {{ background: #E0F2FE; color: #0369A1; }}
  .badge-warn {{ background: #FEF3C7; color: #B45309; }}
  .badge-pos  {{ background: #D1FAE5; color: #047857; }}
  .badge-high {{ background: #DBEAFE; color: #1D4ED8; }}
  .badge-none {{ background: #F1F5F9; color: #64748B; }}

  /* ── Signals List ── */
  .signal-card {{
    background: #FFFFFF;
    border: 1px solid {colors['border']};
    border-left: 4px solid {colors['accent_cyan']};
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 10px;
  }}

  .signal-top {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }}

  .signal-name {{
    font-size: 9.5pt;
    font-weight: 800;
    color: {colors['primary_dark']};
  }}

  .signal-explanation {{
    font-size: 8.5pt;
    color: {colors['text_secondary']};
    line-height: 1.35;
  }}

  .note-box {{
    padding: 10px 14px;
    background: {colors['surface_bg']};
    border: 1px dashed {colors['border']};
    border-radius: 6px;
    font-size: 8.5pt;
    color: {colors['text_secondary']};
    margin: 8px 0;
  }}
</style>
</head>
<body>

<!-- ════════════ COVER PAGE ════════════ -->
<div class="cover-container page-break">
  <div>
    <div class="cover-badge">{escape(BRANDING['company_name'])}</div>
    <h1 class="cover-title">{escape(c.get('title', 'Informe Ejecutivo'))}</h1>
    <div class="cover-gold-strip"></div>
    <div class="cover-subtitle">{escape(c.get('subtitle', ''))}</div>
  </div>

  <div class="cover-meta-grid">
    <div class="meta-row">
      <div class="meta-cell-label">{escape(strings['cover_client'])}</div>
      <div class="meta-cell-val">{escape(c.get('client_name', ''))}</div>
    </div>
    <div class="meta-row">
      <div class="meta-cell-label">{escape(strings['cover_period'])}</div>
      <div class="meta-cell-val">{escape(c.get('period_label', ''))}</div>
    </div>
    <div class="meta-row">
      <div class="meta-cell-label">{escape(strings['cover_platform'])}</div>
      <div class="meta-cell-val">{escape(c.get('platform_filter', ''))}</div>
    </div>
    <div class="meta-row">
      <div class="meta-cell-label">{escape(strings['cover_generated'])}</div>
      <div class="meta-cell-val">{escape(c.get('generation_date', ''))}</div>
    </div>
  </div>

  <div style="font-size: 8pt; color: {colors['text_tertiary']};">
    {escape(BRANDING['footer_attribution_es'] if language == 'es' else BRANDING['footer_attribution_en'])} · v{escape(metadata.get('template_version', 'bs4g-v1'))}
  </div>
</div>

<!-- ════════════ EXECUTIVE SUMMARY & KPIS ════════════ -->
<div>
  <div class="section-header">
    <h2 class="section-title">{escape(exec_summary.get('title', strings['section_exec_summary']))}</h2>
  </div>

  <div class="bullet-box">
    <ul>
      {''.join(f'<li>{escape(b)}</li>' for b in exec_summary.get('bullets', []))}
    </ul>
  </div>

  <div class="section-header" style="margin-top: 20px;">
    <h2 class="section-title">{escape(strings['section_kpis'])}</h2>
  </div>

  <table class="kpi-table">
    <thead>
      <tr>
        <th style="width: 32%;">{escape(strings['table_metric'])}</th>
        <th style="width: 22%;">{escape(strings['table_current'])}</th>
        <th style="width: 22%;">{escape(strings['table_previous'])}</th>
        <th style="width: 24%;">{escape(strings['table_delta'])}</th>
      </tr>
    </thead>
    <tbody>
"""

    for k in kpis:
        m_label = escape(k.get("label", k.get("metric_key", "")))
        if not k.get("is_available"):
            curr_str = f'<span class="badge badge-warn">{escape(strings["unavailable"])}</span>'
            prev_str = "—"
            delta_str = f'<span style="font-size:7.5pt; color:#B45309;">{escape(k.get("unavailable_reason") or strings["unavailable"])}</span>'
        else:
            curr_val = k.get("current_value")
            prev_val = k.get("baseline_value")
            curr_str = f'<span class="val-strong">{int(curr_val):,}</span>' if curr_val is not None else "—"
            prev_str = f"{int(prev_val):,}" if prev_val is not None else "—"
            delta_str = escape(k.get("delta_display", "—"))

            if k.get("is_gauge"):
                curr_str += f' <span style="font-size:7pt; color:{colors["text_tertiary"]};">({escape(strings["gauge_note"])})</span>'
            elif k.get("is_non_aggregatable"):
                curr_str += f' <span style="font-size:7pt; color:{colors["text_tertiary"]};">({escape(strings["reach_note"])})</span>'

        html += f"""      <tr>
        <td><strong>{m_label}</strong></td>
        <td>{curr_str}</td>
        <td>{prev_str}</td>
        <td>{delta_str}</td>
      </tr>\n"""

    html += f"""    </tbody>
  </table>
</div>

<div class="page-break"></div>

<!-- ════════════ PLATFORM BREAKDOWN & CONTENT ════════════ -->
<div>
  <div class="section-header">
    <h2 class="section-title">{escape(strings['section_platforms'])}</h2>
  </div>

  <table class="kpi-table">
    <thead>
      <tr>
        <th>{escape(strings['table_platform'])}</th>
        <th>{escape(strings['table_status'])}</th>
        <th>Métricas Disponibles</th>
        <th>Reacciones</th>
        <th>Comentarios</th>
      </tr>
    </thead>
    <tbody>
"""
    for p in platforms:
        p_name = escape(p.get("platform", "").capitalize())
        m_label = escape(p.get("mode_label", ""))
        b_class = "badge-pos" if p.get("status_mode") == "FULL" else "badge-warn"
        avail = ", ".join(p.get("available_metrics", []))
        html += f"""      <tr>
        <td><strong>{p_name}</strong></td>
        <td><span class="badge {b_class}">{m_label}</span></td>
        <td style="font-size:8pt; color:{colors['text_secondary']};">{escape(avail)}</td>
        <td class="val-strong">{p.get('reactions_total', 0):,}</td>
        <td class="val-strong">{p.get('comments_total', 0):,}</td>
      </tr>\n"""

    html += f"""    </tbody>
  </table>

  <div class="section-header" style="margin-top: 24px;">
    <h2 class="section-title">{escape(strings['section_content'])}</h2>
  </div>
"""

    if not content:
        html += f"""  <div class="note-box">No se registraron publicaciones en el período analizado.</div>\n"""
    else:
        html += f"""  <table class="kpi-table">
    <thead>
      <tr>
        <th style="width: 25%;">{escape(strings['table_platform'])} / {escape(strings['table_format'])}</th>
        <th style="width: 30%;">{escape(strings['table_author'])}</th>
        <th style="width: 15%;">{escape(strings['kpi_reactions'])}</th>
        <th style="width: 15%;">{escape(strings['kpi_comments'])}</th>
        <th style="width: 15%;">{escape(strings['kpi_shares'])}</th>
      </tr>
    </thead>
    <tbody>\n"""
        for post in content[:8]:
            p_name = escape(post.get("platform", "").capitalize())
            fmt_str = escape(post.get("media_type", "").upper())
            auth_str = escape(post.get("source_label", ""))
            reac = f"{post.get('reactions', 0):,}"
            comm = f"{post.get('comments', 0):,}"
            sh = f"{post.get('shares', 0):,}" if post.get("shares") is not None else '<span class="badge badge-none">—</span>'

            html += f"""      <tr>
        <td><strong>{p_name}</strong> · {fmt_str}</td>
        <td style="font-size:8pt;">{auth_str}</td>
        <td class="val-strong">{reac}</td>
        <td class="val-strong">{comm}</td>
        <td>{sh}</td>
      </tr>\n"""
        html += f"""    </tbody>
  </table>\n"""

    html += f"""</div>

<div class="page-break"></div>

<!-- ════════════ BUSINESS SIGNALS & METHODOLOGY ════════════ -->
<div>
  <div class="section-header">
    <h2 class="section-title">{escape(strings['section_signals'])} ({len(signals)})</h2>
  </div>
"""

    if not signals:
        html += f"""  <div class="note-box">No se identificaron señales para los filtros seleccionados.</div>\n"""
    else:
        for s in signals:
            sig_name = escape(s.get("signal_type", "").replace("_", " "))
            p_name = escape(s.get("platform", "").capitalize())
            conf_str = escape(s.get("confidence_label", s.get("confidence_level", "")))
            sev_str = escape(s.get("severity_label", s.get("severity", "")))
            expl = escape(s.get("explanation", ""))

            html += f"""  <div class="signal-card">
    <div class="signal-top">
      <div>
        <span class="signal-name">[{p_name}] {sig_name}</span>
      </div>
      <div>
        <span class="badge badge-high">{conf_str}</span>
        <span class="badge badge-info">{sev_str}</span>
      </div>
    </div>
    <div class="signal-explanation">{expl}</div>
  </div>\n"""

    html += f"""
  <div class="section-header" style="margin-top: 24px;">
    <h2 class="section-title">{escape(strings['section_methodology'])}</h2>
  </div>

  <div class="note-box" style="line-height: 1.5;">
    <ul style="margin: 0; padding-left: 18px;">
      {''.join(f'<li>{escape(pt)}</li>' for pt in methodology)}
    </ul>
  </div>
</div>

</body>
</html>
"""
    return html


def generate_report_pdf(report_data: Dict[str, Any], language: str = "es") -> Tuple[bytes, str]:
    """
    Renders HTML report and compiles into binary PDF using WeasyPrint.
    Returns (pdf_bytes, sha256_checksum).
    """
    import weasyprint

    # Ensure fontconfig cache writable
    os.environ["XDG_CACHE_HOME"] = "/tmp"

    html_content = render_report_html(report_data, language=language)
    html_doc = weasyprint.HTML(string=html_content)
    pdf_bytes = html_doc.write_pdf()

    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    return pdf_bytes, checksum
