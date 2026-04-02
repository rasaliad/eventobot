"""Chart generation using Plotly for attendance data."""

import logging

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# Theme — light background for Telegram
C_BG = "#f5f6fa"
C_PAPER = "#ffffff"
C_GREEN = "#27ae60"
C_RED = "#c0392b"
C_BLUE = "#2980b9"
C_TEXT = "#2c3e50"
C_TEXT_DIM = "#7f8c8d"
C_GRID = "#dcdde1"


def generate_totals_chart(funcion_name: str, rows: list, lang: int = 1) -> bytes:
    """Horizontal bar chart for total attendance."""
    labels = []
    values = []
    pcts = []
    colors = [C_BLUE, C_GREEN, C_RED]

    for i, row in enumerate(rows):
        desc = str(row[0]).strip()
        val_str = str(row[1]).strip().replace(",", "")
        pct_str = str(row[2]).strip() if row[2] else ""
        try:
            val = int(float(val_str))
        except (ValueError, TypeError):
            val = 0
        labels.append(desc)
        values.append(val)
        pcts.append(pct_str)

    # Reverse for top-to-bottom display
    labels.reverse()
    values.reverse()
    pcts.reverse()
    bar_colors = list(reversed(colors[:len(labels)]))

    text_items = []
    for v, p in zip(values, pcts):
        text_items.append(f"  <b>{v:,}</b>  ({p})" if p else f"  <b>{v:,}</b>")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=values, orientation="h",
        marker=dict(color=bar_colors, cornerradius=5),
        text=text_items, textposition="outside",
        textfont=dict(size=15, color=C_TEXT, family="Arial"),
        width=0.55,
    ))

    subtitle = "Asistencia Total" if lang == 1 else "Total Attendance"
    fig.update_layout(
        title=dict(
            text=f"<b>{funcion_name}</b><br><span style='font-size:12px;color:{C_TEXT_DIM}'>{subtitle}</span>",
            font=dict(size=18, color=C_TEXT, family="Arial"), x=0.02, xanchor="left",
        ),
        plot_bgcolor=C_BG, paper_bgcolor=C_PAPER,
        font=dict(color=C_TEXT, family="Arial", size=14),
        xaxis=dict(visible=False, range=[0, max(values) * 1.4]),
        yaxis=dict(tickfont=dict(size=14, family="Arial Black", color=C_TEXT), gridcolor="rgba(0,0,0,0)"),
        margin=dict(l=130, r=30, t=75, b=15),
        width=620, height=max(200, 75 + len(labels) * 80),
        showlegend=False,
    )
    return _fig_to_png(fig)


def generate_detail_chart(funcion_name: str, rows: list, lang: int = 1) -> bytes:
    """Bar chart showing entered vs available per area, with clear green/red."""
    areas = []
    total_row = None

    for row in rows:
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
            total_row = (area, disponibles, entradas, no_entraron)
        elif disponibles > 0 or entradas > 0:
            areas.append((area, disponibles, entradas, no_entraron))

    if not areas:
        return _empty_chart()

    # Reverse for top-to-bottom
    areas.reverse()

    area_names = [a[0] for a in areas]
    entered = [a[2] for a in areas]
    remaining = [a[3] for a in areas]
    disponibles = [a[1] for a in areas]

    # Labels
    entered_text = []
    for e, d in zip(entered, disponibles):
        pct = f"{e * 100 // d}%" if d > 0 else "0%"
        entered_text.append(f" {e:,} ({pct})")

    remaining_text = [f" {r:,}" for r in remaining]

    fig = go.Figure()

    lbl_entered = "Entradas" if lang == 1 else "Entered"
    fig.add_trace(go.Bar(
        y=area_names, x=entered, orientation="h", name=lbl_entered,
        marker=dict(color=C_GREEN, cornerradius=3),
        text=entered_text, textposition="inside", textangle=0,
        textfont=dict(size=11, color="white", family="Arial Black"),
        insidetextanchor="start",
        width=0.6,
    ))

    lbl_remain = "Restan" if lang == 1 else "Remaining"
    fig.add_trace(go.Bar(
        y=area_names, x=remaining, orientation="h", name=lbl_remain,
        marker=dict(color=C_RED, opacity=0.7, cornerradius=3),
        text=remaining_text, textposition="inside", textangle=0,
        textfont=dict(size=11, color="white", family="Arial"),
        insidetextanchor="start",
        width=0.6,
    ))

    # Title with total
    subtitle = "Asistencia por Area" if lang == 1 else "Attendance by Section"
    total_text = ""
    if total_row:
        _, t_disp, t_entr, _ = total_row
        t_pct = f"{t_entr * 100 // t_disp}%" if t_disp > 0 else "0%"
        total_text = f"<br><b>TOTAL: {t_entr:,} / {t_disp:,} ({t_pct})</b>"

    fig.update_layout(
        barmode="stack",
        title=dict(
            text=f"<b>{funcion_name}</b><br><span style='font-size:12px;color:{C_TEXT_DIM}'>{subtitle}</span>{total_text}",
            font=dict(size=16, color=C_TEXT, family="Arial"), x=0.02, xanchor="left",
        ),
        plot_bgcolor=C_BG, paper_bgcolor=C_PAPER,
        font=dict(color=C_TEXT, family="Arial", size=12),
        xaxis=dict(visible=False),
        yaxis=dict(
            tickfont=dict(size=11, family="Arial", color=C_TEXT),
            gridcolor="rgba(0,0,0,0)",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=12, color=C_TEXT), bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=140, r=20, t=100 + (20 if total_row else 0), b=15),
        width=700,
        height=max(280, 120 + len(areas) * 42),
        showlegend=True,
    )
    return _fig_to_png(fig)


def _fig_to_png(fig: go.Figure) -> bytes:
    return fig.to_image(format="png", scale=2, engine="kaleido")


def _empty_chart() -> bytes:
    fig = go.Figure()
    fig.add_annotation(text="No data", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=24, color=C_TEXT))
    fig.update_layout(
        plot_bgcolor=C_BG, paper_bgcolor=C_PAPER,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        width=400, height=150,
    )
    return _fig_to_png(fig)
