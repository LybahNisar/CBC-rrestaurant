"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — WEEKLY PDF REPORT GENERATOR                ║
║  Generates a polished 1-page PDF summary every Monday.          ║
║                                                                  ║
║  Standalone usage:                                              ║
║    python weekly_pdf_report.py                                  ║
║                                                                  ║
║  Or call from the dashboard:                                    ║
║    from weekly_pdf_report import generate_weekly_pdf            ║
║    pdf_bytes = generate_weekly_pdf(data, week_label)            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Colour palette (matches dashboard) ────────────────────────────
C_BG       = colors.HexColor("#0a0b0f")
C_SURFACE  = colors.HexColor("#12141a")
C_CARD     = colors.HexColor("#1a1d26")
C_ACCENT   = colors.HexColor("#f5a623")
C_ACCENT2  = colors.HexColor("#e8724a")
C_GREEN    = colors.HexColor("#3ecf8e")
C_RED      = colors.HexColor("#e05c5c")
C_TEXT     = colors.HexColor("#e8e9f0")
C_MUTED    = colors.HexColor("#6b7094")
C_BORDER   = colors.HexColor("#252836")
C_WHITE    = colors.white


# ── Style helpers ─────────────────────────────────────────────────

def _style(name, **kwargs):
    base = dict(
        fontName  = "Helvetica",
        fontSize  = 10,
        textColor = C_TEXT,
        leading   = 14,
    )
    base.update(kwargs)
    return ParagraphStyle(name, **base)


S_TITLE   = _style("title",   fontName="Helvetica-Bold", fontSize=22,
                   textColor=C_ACCENT,  leading=28, alignment=TA_LEFT)
S_SUBTITLE = _style("sub",    fontName="Helvetica",      fontSize=11,
                   textColor=C_MUTED,  leading=15)
S_H2      = _style("h2",      fontName="Helvetica-Bold", fontSize=13,
                   textColor=C_ACCENT, leading=18, spaceBefore=10)
S_H3      = _style("h3",      fontName="Helvetica-Bold", fontSize=10,
                   textColor=C_TEXT,   leading=14, spaceBefore=4)
S_BODY    = _style("body",    fontSize=9,  textColor=C_TEXT,   leading=13)
S_MUTED   = _style("muted",   fontSize=8,  textColor=C_MUTED,  leading=12)
S_GREEN   = _style("green",   fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_GREEN)
S_RED     = _style("red",     fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_RED)
S_NUM     = _style("num",     fontName="Helvetica-Bold", fontSize=18,
                   textColor=C_ACCENT, leading=22, alignment=TA_CENTER)
S_NUM_LBL = _style("numlbl",  fontSize=8,  textColor=C_MUTED,
                   leading=10, alignment=TA_CENTER)


# ── Table style builder ───────────────────────────────────────────

def _table_style(header_rows=1, zebra=True):
    cmds = [
        ("BACKGROUND",  (0, 0), (-1, header_rows - 1), C_CARD),
        ("TEXTCOLOR",   (0, 0), (-1, header_rows - 1), C_ACCENT),
        ("FONTNAME",    (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, header_rows - 1), 8),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND", (0, 0), (-1, -1), [C_SURFACE, C_BG]),
        ("TEXTCOLOR",   (0, header_rows), (-1, -1), C_TEXT),
        ("FONTNAME",    (0, header_rows), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, header_rows), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW",   (0, 0), (-1, header_rows - 1), 0.5, C_ACCENT),
        ("LINEBELOW",   (0, header_rows), (-1, -1), 0.3, C_BORDER),
        ("BOX",         (0, 0), (-1, -1), 0.5, C_BORDER),
    ]
    return TableStyle(cmds)


# ══════════════════════════════════════════════════════════════════
# Main generator
# ══════════════════════════════════════════════════════════════════

def generate_weekly_pdf(data: dict, week_label: str = "") -> bytes:
    """
    data: same dict returned by app_dashboard.load_data()
    Returns raw PDF bytes — save to file or serve via st.download_button.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize   = A4,
        leftMargin = 18 * mm,
        rightMargin= 18 * mm,
        topMargin  = 14 * mm,
        bottomMargin= 14 * mm,
    )

    # ── Background canvas callback ─────────────────────────────
    def draw_bg(canvas, doc):
        canvas.setFillColor(C_BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        # Header bar
        canvas.setFillColor(C_SURFACE)
        canvas.rect(0, A4[1] - 30 * mm, A4[0], 30 * mm, fill=1, stroke=0)
        # Footer
        canvas.setFillColor(C_SURFACE)
        canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 3.5 * mm,
            f"Chocoberry Intelligence  ·  Generated {datetime.now().strftime('%d %b %Y %H:%M')}  ·  Confidential")
        canvas.drawRightString(A4[0] - 18 * mm, 3.5 * mm,
            f"Page {doc.page}")

    # ── Assemble story ─────────────────────────────────────────
    story = []

    df          = data.get("daily")
    channels    = data.get("channels", {})
    dispatch    = data.get("dispatch_truth", {})
    personnel   = data.get("personnel", {})

    # Calculate weekly figures from last 7 days of data
    if df is not None and not df.empty:
        import pandas as pd
        last7 = df.sort_values("date").tail(7)
        week_net    = last7["Net sales"].sum()
        week_orders = int(last7["Orders"].sum())
        week_tax    = last7["Tax on net sales"].sum()
        week_aov    = week_net / week_orders if week_orders > 0 else 0
        prev7       = df.sort_values("date").iloc[-14:-7]
        prev_net    = prev7["Net sales"].sum() if len(prev7) == 7 else 0
        wow_pct     = ((week_net - prev_net) / prev_net * 100) if prev_net > 0 else 0
        daily_avg   = week_net / 7
        best_day    = last7.loc[last7["Net sales"].idxmax()]
        slow_day    = last7.loc[last7["Net sales"].idxmin()]
    else:
        week_net = week_orders = week_tax = week_aov = 0
        wow_pct = daily_avg = 0
        best_day = slow_day = None

    if not week_label:
        week_label = datetime.now().strftime("Week of %d %b %Y")

    # ── Header block ──────────────────────────────────────────
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Chocoberry Intelligence", S_TITLE))
    story.append(Paragraph(f"Weekly Performance Report  ·  {week_label}", S_SUBTITLE))
    story.append(Spacer(1, 6 * mm))

    # ── KPI cards (as a table row) ─────────────────────────────
    kpi_labels = ["Net Sales", "Orders", "Avg Order Value", "Daily Average", "WoW Change", "Tax Collected"]
    kpi_values = [
        f"£{week_net:,.0f}",
        f"{week_orders:,}",
        f"£{week_aov:.2f}",
        f"£{daily_avg:,.0f}",
        f"{wow_pct:+.1f}%",
        f"£{week_tax:,.0f}",
    ]
    kpi_colors = [C_ACCENT, C_TEXT, C_TEXT, C_TEXT,
                  C_GREEN if wow_pct >= 0 else C_RED, C_MUTED]

    kpi_val_cells = []
    kpi_lbl_cells = []
    for i, (val, lbl, col) in enumerate(zip(kpi_values, kpi_labels, kpi_colors)):
        s = ParagraphStyle(f"kv{i}", fontName="Helvetica-Bold",
                           fontSize=16, textColor=col, leading=20, alignment=TA_CENTER)
        kpi_val_cells.append(Paragraph(val, s))
        kpi_lbl_cells.append(Paragraph(lbl, S_NUM_LBL))

    kpi_table = Table(
        [kpi_val_cells, kpi_lbl_cells],
        colWidths=[28 * mm] * 6,
    )
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_CARD),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.3, C_BORDER),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, C_BORDER),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 5 * mm))

    # ── Day-by-day table ──────────────────────────────────────
    story.append(Paragraph("Day-by-Day Performance", S_H2))
    story.append(Spacer(1, 1 * mm))

    if df is not None and not df.empty:
        import pandas as pd
        day_rows = [["Date", "Day", "Net Sales", "Orders", "AOV", "WoW %"]]
        last7_sorted = last7.sort_values("date")
        for _, row in last7_sorted.iterrows():
            aov = row["Net sales"] / row["Orders"] if row["Orders"] > 0 else 0
            day_rows.append([
                row["date"].strftime("%d %b"),
                row["day"][:3],
                f"£{row['Net sales']:,.0f}",
                f"{int(row['Orders']):,}",
                f"£{aov:.2f}",
                "—",
            ])

        day_table = Table(day_rows, colWidths=[22*mm, 20*mm, 30*mm, 22*mm, 22*mm, 22*mm])
        day_table.setStyle(_table_style())

        # Highlight best / worst
        best_idx = last7_sorted["Net sales"].idxmax()
        slow_idx = last7_sorted["Net sales"].idxmin()
        rows_list = list(last7_sorted.index)
        if best_idx in rows_list:
            r = rows_list.index(best_idx) + 1
            day_table.setStyle(TableStyle([("BACKGROUND", (0, r), (-1, r), colors.HexColor("#102a18"))]))
        if slow_idx in rows_list:
            r = rows_list.index(slow_idx) + 1
            day_table.setStyle(TableStyle([("BACKGROUND", (0, r), (-1, r), colors.HexColor("#1f1410"))]))

        story.append(day_table)
    story.append(Spacer(1, 4 * mm))

    # ── Two-column section: Dispatch + Channels ────────────────
    story.append(Paragraph("Revenue Split", S_H2))
    story.append(Spacer(1, 1 * mm))

    disp_total = sum(v["revenue"] for v in dispatch.values()) or 1
    disp_rows  = [["Type", "Revenue", "% Share"]]
    for dtype, vals in dispatch.items():
        rev = vals.get("revenue", 0)
        disp_rows.append([dtype, f"£{rev:,.0f}", f"{rev/disp_total*100:.1f}%"])

    ch_total = sum(channels.values()) or 1
    ch_rows  = [["Platform", "Net Sales", "% Share"]]
    for platform, rev in sorted(channels.items(), key=lambda x: -x[1]):
        ch_rows.append([platform[:18], f"£{rev:,.0f}", f"{rev/ch_total*100:.1f}%"])

    disp_tbl = Table(disp_rows, colWidths=[32*mm, 26*mm, 22*mm])
    ch_tbl   = Table(ch_rows,   colWidths=[38*mm, 24*mm, 22*mm])
    disp_tbl.setStyle(_table_style())
    ch_tbl.setStyle(_table_style())

    split_table = Table(
        [[disp_tbl, Spacer(6*mm, 1), ch_tbl]],
        colWidths=[82*mm, 8*mm, 87*mm],
    )
    split_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(split_table)
    story.append(Spacer(1, 4 * mm))

    # ── Peak / slow day callout ────────────────────────────────
    if best_day is not None and slow_day is not None:
        callout_data = [[
            Paragraph(
                f"<b><font color='#3ecf8e'>Best day:</font></b> "
                f"{best_day['date'].strftime('%A %d %b')} — "
                f"£{best_day['Net sales']:,.0f} ({int(best_day['Orders'])} orders)",
                S_BODY
            ),
            Paragraph(
                f"<b><font color='#e05c5c'>Slowest day:</font></b> "
                f"{slow_day['date'].strftime('%A %d %b')} — "
                f"£{slow_day['Net sales']:,.0f} ({int(slow_day['Orders'])} orders)",
                S_BODY
            ),
        ]]
        callout_tbl = Table(callout_data, colWidths=[87*mm, 87*mm])
        callout_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_CARD),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
            ("LINEAFTER",     (0, 0), (0, -1),  0.3, C_BORDER),
        ]))
        story.append(callout_tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Labour summary (if available) ─────────────────────────
    if personnel:
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=C_BORDER, spaceAfter=4*mm))
        story.append(Paragraph("Labour Summary", S_H2))
        story.append(Spacer(1, 1 * mm))

        staff_count = len(personnel)
        total_wages = sum(
            float(p.get("Fixed Wage") or 0) or
            float(p.get("Hourly Rate", 0)) * 30
            for p in personnel.values()
        )
        labour_pct = total_wages / week_net * 100 if week_net > 0 else 0
        flag_color = "#e05c5c" if labour_pct > 30 else "#3ecf8e"
        flag_text  = "OVER 30% THRESHOLD" if labour_pct > 30 else "Within 30% target"

        lab_rows = [
            [Paragraph("Staff on rota", S_MUTED), Paragraph(f"{staff_count}", S_H3)],
            [Paragraph("Est. wages", S_MUTED),     Paragraph(f"£{total_wages:,.2f}", S_H3)],
            [Paragraph("Labour % of revenue", S_MUTED),
             Paragraph(f'<font color="{flag_color}">{labour_pct:.1f}% — {flag_text}</font>', S_H3)],
        ]
        lab_tbl = Table(lab_rows, colWidths=[50*mm, 120*mm])
        lab_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_CARD),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
            ("LINEBELOW",     (0, 0), (-1, -2), 0.3, C_BORDER),
        ]))
        story.append(lab_tbl)

    # ── Insights box ──────────────────────────────────────────
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=C_BORDER, spaceAfter=4*mm))
    story.append(Paragraph("Key Insights This Week", S_H2))
    story.append(Spacer(1, 1 * mm))

    insights = _generate_insights(
        week_net, prev_net, week_aov, week_orders, wow_pct, channels
    )
    insight_rows = [[Paragraph(f"{'•'} {ins}", S_BODY)] for ins in insights]
    ins_tbl = Table(insight_rows, colWidths=[174*mm])
    ins_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_CARD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_ACCENT),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, C_BORDER),
    ]))
    story.append(ins_tbl)

    # ── Build ──────────────────────────────────────────────────
    doc.build(story, onFirstPage=draw_bg, onLaterPages=draw_bg)
    return buf.getvalue()


# ── Insight text generator ────────────────────────────────────────

def _generate_insights(week_net, prev_net, aov, orders, wow_pct, channels):
    insights = []

    if wow_pct > 10:
        insights.append(f"Strong week — revenue up {wow_pct:.1f}% vs the same week prior. "
                        "Investigate what drove the uplift and replicate.")
    elif wow_pct < -10:
        insights.append(f"Revenue down {abs(wow_pct):.1f}% week-on-week. "
                        "Review any operational or external factors that may have affected trade.")
    else:
        insights.append(f"Revenue in line with prior week ({wow_pct:+.1f}%). Stable trading pattern.")

    if aov > 15:
        insights.append(f"Average order value at £{aov:.2f} — strong upselling. "
                        "Continue promoting add-ons and meal deals.")
    elif aov < 12:
        insights.append(f"AOV at £{aov:.2f} is below target. Consider upsell prompts "
                        "at checkout — waffles + drink combos are high margin.")

    ch_total = sum(channels.values()) or 1
    top_ch   = max(channels, key=channels.get, default="POS")
    top_pct  = channels.get(top_ch, 0) / ch_total * 100
    insights.append(f"{top_ch} is the top revenue channel at {top_pct:.1f}% of sales. "
                    "Ensure this channel is fully optimised and stock is prioritised for peak hours.")

    web_rev = channels.get("Web (Flipdish)", 0)
    if web_rev < 1000:
        insights.append("Direct web orders remain low (£" + f"{web_rev:,.0f}). "
                        "Promoting the website link avoids third-party commission fees — "
                        "even a 5% shift from Uber Eats would save ~£300/week.")

    if orders > 1000:
        insights.append(f"{orders:,} orders this week — high volume. "
                        "Ensure kitchen throughput and packaging stock are adequate.")

    return insights[:4]  # max 4 bullets


# ── Streamlit integration helper ──────────────────────────────────

def render_pdf_download_button(data: dict, week_label: str = "",
                                button_label: str = "Download Weekly PDF Report"):
    """
    Call this inside any Streamlit tab to add a PDF download button.
    Requires: import streamlit as st
    """
    import streamlit as st
    if st.button(button_label, key="pdf_dl_btn"):
        with st.spinner("Generating PDF..."):
            pdf_bytes = generate_weekly_pdf(data, week_label)
        fname = f"chocoberry_weekly_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(
            label     = "⬇️ Download PDF",
            data      = pdf_bytes,
            file_name = fname,
            mime      = "application/pdf",
        )


# ── Standalone test ───────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from datetime import date, timedelta

    # Build minimal mock data to test the PDF
    dates = [date(2026, 3, 30) + timedelta(days=i) for i in range(7)]
    df = pd.DataFrame({
        "date":            pd.to_datetime(dates),
        "day":             [d.strftime("%A") for d in dates],
        "Net sales":       [2142, 2590, 2160, 3508, 2750, 2291, 1630],
        "Revenue":         [2252, 2693, 2278, 3622, 2873, 2413, 1694],
        "Orders":          [139,  162,  145,  220,  198,  166,  111],
        "Tax on net sales":[109,  99,   103,  114,  102,  111,  60],
        "refunds":         [0,0,7.5,0,0,0,0],
    })

    mock_data = {
        "daily":   df,
        "channels": {
            "POS (In-Store)": 148085,
            "Uber Eats":       61052,
            "Deliveroo":       28783,
            "Just Eat":         2187,
            "Web (Flipdish)":    630,
        },
        "dispatch_truth": {
            "Delivery":   {"revenue": 89702, "orders": 6147},
            "Dine In":    {"revenue": 77570, "orders": 5312},
            "Take Away":  {"revenue": 64373, "orders": 4409},
            "Collection": {"revenue":  9093, "orders":  623},
        },
        "personnel": {
            "Dhiraj": {"Hourly Rate": 9.0},
            "Chintan": {"Hourly Rate": 8.5},
            "Damini": {"Fixed Wage": 300},
        },
    }

    pdf_bytes = generate_weekly_pdf(mock_data, "30 Mar – 05 Apr 2026")
    out_path  = "chocoberry_weekly_report_sample.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"\n✅  PDF generated: {out_path}  ({len(pdf_bytes):,} bytes)\n")
