import io
import logging
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

VERM  = colors.HexColor("#C8102E")
AMAR  = colors.HexColor("#F5C800")
PRET  = colors.HexColor("#1A1A1A")
CINZ  = colors.HexColor("#F5F5F5")
CINZ2 = colors.HexColor("#DDDDDD")
BRAN  = colors.white


def fmt_brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"


def gerar_pdf(pergunta: str, resposta: str, rows: list, columns: list, row_count: int, sql: str) -> bytes:
    """Gera PDF com a pergunta, resposta narrativa e tabela de dados do DuckDB."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.2 * cm,  bottomMargin=1.2 * cm,
    )

    s_titulo  = ParagraphStyle("titulo",  fontName="Helvetica-Bold",   fontSize=14, textColor=BRAN)
    s_sub     = ParagraphStyle("sub",     fontName="Helvetica",        fontSize=8,  textColor=colors.HexColor("#FFDDDD"))
    s_label   = ParagraphStyle("label",   fontName="Helvetica-Bold",   fontSize=7,  textColor=colors.HexColor("#888888"), spaceAfter=2)
    s_body    = ParagraphStyle("body",    fontName="Helvetica",        fontSize=9,  textColor=PRET, leading=14, spaceAfter=6)
    s_rodape  = ParagraphStyle("rodape",  fontName="Helvetica",        fontSize=7,  textColor=colors.HexColor("#AAAAAA"), alignment=TA_CENTER)
    s_sql     = ParagraphStyle("sql",     fontName="Courier",          fontSize=7,  textColor=colors.HexColor("#666666"), leading=10)

    hoje_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story = []

    # ── Cabeçalho ──────────────────────────────────────────
    cab_data = [[
        Paragraph("IAF VDDB · RELATÓRIO DE ANÁLISE", s_titulo),
        Paragraph(f"Frinense Alimentos · {hoje_str}", s_sub),
    ]]
    cab_table = Table(cab_data, colWidths=["70%", "30%"])
    cab_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), VERM),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (1, 0), (1, 0),   "RIGHT"),
    ]))
    story.append(cab_table)
    story.append(Spacer(1, 10))

    # ── Pergunta ───────────────────────────────────────────
    story.append(Paragraph("PERGUNTA", s_label))
    story.append(Paragraph(pergunta, s_body))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1, 6))

    # ── Resposta narrativa ─────────────────────────────────
    story.append(Paragraph("ANÁLISE", s_label))
    # quebra por linhas para manter parágrafos
    for linha in resposta.split("\n"):
        linha = linha.strip()
        if linha:
            story.append(Paragraph(linha, s_body))
    story.append(Spacer(1, 8))

    # ── Tabela de dados ────────────────────────────────────
    if rows and columns:
        story.append(Paragraph(f"DADOS ({row_count} registros)", s_label))
        story.append(Spacer(1, 4))

        # cabeçalho da tabela
        header_row = [Paragraph(str(c).upper(), ParagraphStyle(
            "th", fontName="Helvetica-Bold", fontSize=7, textColor=BRAN, alignment=TA_CENTER
        )) for c in columns]

        table_data = [header_row]

        # linhas de dados (máx 100 no PDF)
        for row in rows[:100]:
            line = []
            for col in columns:
                val = row.get(col, "")
                # tenta formatar números
                try:
                    f = float(val)
                    if f == int(f):
                        val = f"{int(f):,}".replace(",", ".")
                    else:
                        val = f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except (TypeError, ValueError):
                    val = str(val) if val is not None else ""
                line.append(Paragraph(str(val)[:60], ParagraphStyle(
                    "td", fontName="Helvetica", fontSize=7, textColor=PRET
                )))
            table_data.append(line)

        # distribui colunas igualmente
        page_w = landscape(A4)[0] - 2.4 * cm
        col_w  = page_w / len(columns)
        tbl = Table(table_data, colWidths=[col_w] * len(columns), repeatRows=1)

        tbl_style = [
            ("BACKGROUND",    (0, 0), (-1,  0),  VERM),
            ("TEXTCOLOR",     (0, 0), (-1,  0),  BRAN),
            ("FONTNAME",      (0, 0), (-1,  0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1),  7),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),  [BRAN, CINZ]),
            ("GRID",          (0, 0), (-1, -1),  0.3, CINZ2),
            ("TOPPADDING",    (0, 0), (-1, -1),  3),
            ("BOTTOMPADDING", (0, 0), (-1, -1),  3),
            ("LEFTPADDING",   (0, 0), (-1, -1),  4),
            ("RIGHTPADDING",  (0, 0), (-1, -1),  4),
        ]
        tbl.setStyle(TableStyle(tbl_style))
        story.append(tbl)

        if row_count > 100:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"* Exibindo 100 de {row_count} registros.",
                ParagraphStyle("nota", fontName="Helvetica-Oblique", fontSize=7, textColor=colors.HexColor("#999999"))
            ))

    story.append(Spacer(1, 12))

    # ── SQL gerado ─────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1, 4))
    story.append(Paragraph("SQL GERADO", s_label))
    story.append(Paragraph(sql.replace("<", "&lt;").replace(">", "&gt;"), s_sql))
    story.append(Spacer(1, 10))

    # ── Rodapé ─────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"IAF VDDB · Analista Comercial · Frinense Alimentos · Gerado em {hoje_str}",
        s_rodape
    ))

    doc.build(story)
    return buf.getvalue()
