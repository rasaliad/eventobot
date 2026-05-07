"""Chart generation using HTML + Chrome headless."""

import logging
import math
import os
import tempfile

from html2image import Html2Image

logger = logging.getLogger(__name__)

_BROWSER = None
for path in [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]:
    if os.path.isfile(path):
        _BROWSER = path
        break


def _render_html(html: str, width: int, height: int) -> bytes:
    if not _BROWSER:
        raise RuntimeError("No Chrome/Edge found")
    with tempfile.TemporaryDirectory() as tmpdir:
        hti = Html2Image(
            output_path=tmpdir,
            size=(width, height),
            browser_executable=_BROWSER,
        )
        hti.screenshot(html_str=html, save_as="chart.png")
        with open(os.path.join(tmpdir, "chart.png"), "rb") as f:
            return f.read()


def _build_table(headers, rows, total_row=None):
    hdr = ""
    for i, h in enumerate(headers):
        align = "left" if i == 0 else "right"
        hdr += f'<th style="padding:8px 10px;text-align:{align}">{h}</th>'
    body = ""
    for idx, row in enumerate(rows):
        bg = "#f5f5f5" if idx % 2 == 0 else "white"
        cells = ""
        for i, val in enumerate(row):
            align = "left" if i == 0 else "right"
            color = "#c62828" if i == len(row) - 1 and i > 1 else "#333"
            cells += f'<td style="padding:6px 10px;text-align:{align};color:{color}">{val}</td>'
        body += f'<tr style="background:{bg}">{cells}</tr>'
    total_html = ""
    if total_row:
        cells = ""
        for i, val in enumerate(total_row):
            align = "left" if i == 0 else "right"
            cells += f'<td style="padding:8px 10px;text-align:{align}">{val}</td>'
        total_html = f'<tr style="background:#1a237e;color:white;font-weight:bold">{cells}</tr>'
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:15px">
        <thead><tr style="background:#1a237e;color:white">{hdr}</tr></thead>
        <tbody>{body}{total_html}</tbody>
    </table>"""


def _svg_pie(entered, remaining):
    """Pie chart: blue = entered, gray = remaining."""
    total = entered + remaining
    if total == 0:
        return ""

    pct_entered = entered / total
    pct_remain = remaining / total
    cx, cy, r = 110, 110, 95

    min_angle = 7
    angle_entered = pct_entered * 360
    angle_remain = pct_remain * 360
    if 0 < angle_entered < min_angle:
        angle_entered = min_angle
        angle_remain = 360 - min_angle
    elif 0 < angle_remain < min_angle:
        angle_remain = min_angle
        angle_entered = 360 - min_angle

    c_blue = "#4472C4"
    c_gray = "#c8c8d0"
    paths = ""

    if pct_remain == 0:
        paths += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c_blue}"/>'
    elif pct_entered == 0:
        paths += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c_gray}"/>'
    else:
        start = -90
        end = start + angle_entered
        large = 1 if angle_entered > 180 else 0
        x1 = cx + r * math.cos(math.radians(start))
        y1 = cy + r * math.sin(math.radians(start))
        x2 = cx + r * math.cos(math.radians(end))
        y2 = cy + r * math.sin(math.radians(end))
        paths += f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large},1 {x2:.1f},{y2:.1f} Z" fill="{c_blue}"/>'

        start2 = end
        end2 = start2 + angle_remain
        large2 = 1 if angle_remain > 180 else 0
        x3 = cx + r * math.cos(math.radians(start2))
        y3 = cy + r * math.sin(math.radians(start2))
        x4 = cx + r * math.cos(math.radians(end2))
        y4 = cy + r * math.sin(math.radians(end2))
        paths += f'<path d="M{cx},{cy} L{x3:.1f},{y3:.1f} A{r},{r} 0 {large2},1 {x4:.1f},{y4:.1f} Z" fill="{c_gray}"/>'

    if pct_entered >= 0.03:
        mid = -90 + angle_entered / 2
        lx = cx + r * 0.6 * math.cos(math.radians(mid))
        ly = cy + r * 0.6 * math.sin(math.radians(mid))
        paths += f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" dominant-baseline="middle" fill="white" font-size="14" font-weight="bold" font-family="Arial">{pct_entered * 100:.1f}%</text>'

    if pct_remain >= 0.03:
        mid2 = -90 + angle_entered + angle_remain / 2
        lx2 = cx + r * 0.6 * math.cos(math.radians(mid2))
        ly2 = cy + r * 0.6 * math.sin(math.radians(mid2))
        paths += f'<text x="{lx2:.0f}" y="{ly2:.0f}" text-anchor="middle" dominant-baseline="middle" fill="white" font-size="14" font-weight="bold" font-family="Arial">{pct_remain * 100:.1f}%</text>'

    return f'<svg viewBox="0 0 220 220" width="200" style="display:block;margin:0 auto">{paths}</svg>'


def generate_chart(funcion_name: str, detail_rows: list, total_entered: int,
                   total_remaining: int, lang: int = 1) -> bytes:
    """Combined image: detail table + totals pie chart."""
    # Parse detail areas
    areas = []
    total_row_data = None

    for row in detail_rows:
        area = str(row[1]).strip()
        try:
            disponibles = int(float(str(row[2]).strip().replace(",", "")))
        except (ValueError, TypeError):
            disponibles = 0
        try:
            entradas = int(float(str(row[3]).strip().replace(",", "")))
        except (ValueError, TypeError):
            entradas = 0
        no_entraron = disponibles - entradas

        if area.upper() == "TOTAL":
            total_row_data = (area, disponibles, entradas, no_entraron)
        elif disponibles > 0 or entradas > 0:
            areas.append((area, disponibles, entradas, no_entraron))

    if not areas:
        return _render_html('<div style="padding:40px;font-size:18px">No data</div>', 400, 100)

    # Detail table
    h_area = "AREA" if lang == 1 else "SECTION"
    h_read = "LEIDAS" if lang == 1 else "READ"
    h_remain = "FALTAN" if lang == 1 else "REMAIN"
    table_rows = [[a, f"{d:,}", f"{e:,}", f"{n:,}"] for a, d, e, n in areas]
    total_r = None
    if total_row_data:
        _, td, te, tn = total_row_data
        total_r = ["TOTAL", f"{td:,}", f"{te:,}", f"{tn:,}"]
    table = _build_table([h_area, "TOTAL", h_read, h_remain], table_rows, total_r)

    # Total summary line
    total_disp = total_entered + total_remaining
    pct = total_entered * 100 / total_disp if total_disp > 0 else 0
    lbl = "Asistencia" if lang == 1 else "Attendance"
    summary = f'<div style="text-align:center;font-size:15px;font-weight:bold;color:#1a237e;margin:10px 0">{lbl}: {total_entered:,} / {total_disp:,} ({pct:.1f}%)</div>'

    # Pie chart
    pie = _svg_pie(total_entered, total_remaining)

    lbl_entered = "Entradas" if lang == 1 else "Entered"
    lbl_remain = "Faltan" if lang == 1 else "Remaining"
    legend = f"""
    <div style="display:flex;justify-content:center;gap:20px;margin-top:8px;font-size:12px;color:#555">
        <div style="display:flex;align-items:center">
            <div style="width:14px;height:14px;background:#4472C4;border-radius:2px;margin-right:5px"></div>
            <b>{lbl_entered}</b>
        </div>
        <div style="display:flex;align-items:center">
            <div style="width:14px;height:14px;background:#c8c8d0;border-radius:2px;margin-right:5px"></div>
            <b>{lbl_remain}</b>
        </div>
    </div>"""

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;background:white;padding:20px;width:500px">
        <h2 style="text-align:center;color:#1a237e;margin:0 0 15px;font-size:18px;letter-spacing:1px">
            {funcion_name}
        </h2>
        {table}
        {summary}
        {pie}
        {legend}
    </div>"""

    height = 440 + len(areas) * 35
    return _render_html(html, 540, height)
