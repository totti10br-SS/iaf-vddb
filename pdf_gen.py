import io
import re
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

# Paleta
VERM   = colors.HexColor("#CC0000")
VERM2  = colors.HexColor("#A00000")
AMAR   = colors.HexColor("#F5C800")
PRET   = colors.HexColor("#1A1A1A")
CINZ   = colors.HexColor("#F7F7F7")
CINZ2  = colors.HexColor("#E0E0E0")
CINZ3  = colors.HexColor("#666666")
BRAN   = colors.white
AZUL   = colors.HexColor("#1A3A5C")


def fmt_brl(v):
    try:
        f = float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
        return f"R$ {f:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except:
        return str(v)

def fmt_num(v):
    try:
        f = float(str(v).replace(".","").replace(",",".").strip())
        if f == int(f):
            return f"{int(f):,}".replace(",",".")
        return f"{f:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except:
        return str(v)

def is_valor(s):
    s = str(s).strip().replace("R$","").replace(".","").replace(",",".").replace("%","").strip()
    try: float(s); return True
    except: return False

def is_total_row(row):
    return str(row.get(list(row.keys())[0], "")).upper().startswith("TOTAL")


def gerar_pdf(pergunta: str, resposta: str, rows: list, columns: list, row_count: int, sql: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm,  bottomMargin=1.2*cm,
    )

    hoje_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    W = landscape(A4)[0] - 3*cm

    # ── Estilos ────────────────────────────────────────────
    def st(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=9, textColor=PRET, leading=13)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_h1    = st("h1",  fontName="Helvetica-Bold", fontSize=16, textColor=BRAN,  leading=20)
    s_h1sub = st("sub", fontName="Helvetica",      fontSize=9,  textColor=colors.HexColor("#FFCCCC"), leading=12)
    s_h2    = st("h2",  fontName="Helvetica-Bold", fontSize=11, textColor=VERM,  leading=14, spaceAfter=4)
    s_body  = st("bd",  fontName="Helvetica",      fontSize=9,  textColor=PRET,  leading=13, spaceAfter=4)
    s_bold  = st("bo",  fontName="Helvetica-Bold", fontSize=9,  textColor=PRET,  leading=13)
    s_muted = st("mu",  fontName="Helvetica",      fontSize=7,  textColor=CINZ3, leading=10)
    s_th    = st("th",  fontName="Helvetica-Bold", fontSize=8,  textColor=BRAN,  alignment=TA_CENTER, leading=10)
    s_td    = st("td",  fontName="Helvetica",      fontSize=8,  textColor=PRET,  leading=10)
    s_td_r  = st("tdr", fontName="Helvetica",      fontSize=8,  textColor=PRET,  alignment=TA_RIGHT, leading=10)
    s_td_tot= st("tdt", fontName="Helvetica-Bold", fontSize=8,  textColor=PRET,  alignment=TA_RIGHT, leading=10)
    s_td_tot0=st("tdt0",fontName="Helvetica-Bold", fontSize=8,  textColor=PRET,  leading=10)
    s_alerta= st("al",  fontName="Helvetica-Bold", fontSize=9,  textColor=VERM,  leading=13)
    s_sql   = st("sq",  fontName="Courier",        fontSize=6.5,textColor=CINZ3, leading=9)

    story = []

    # ── Cabeçalho ──────────────────────────────────────────
    cab = Table([[
        Paragraph("IAF VDDB · RELATÓRIO EXECUTIVO", s_h1),
        Table([[
            Paragraph("Frinense Alimentos", st("fi", fontName="Helvetica-Bold", fontSize=9, textColor=AMAR, leading=11)),
            Paragraph(hoje_str, st("dt", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#FFCCCC"), leading=11, alignment=TA_RIGHT)),
        ]], colWidths=["50%","50%"], style=TableStyle([
            ("ALIGN",(1,0),(1,0),"RIGHT"),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ]))
    ]], colWidths=["60%","40%"])
    cab.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),VERM),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(0,-1),14),("RIGHTPADDING",(-1,0),(-1,-1),14),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LINEBELOW",(0,0),(-1,-1),3,AMAR),
    ]))
    story.append(cab)
    story.append(Spacer(1,10))

    # ── Pergunta ───────────────────────────────────────────
    story.append(Table([[
        Paragraph("CONSULTA", st("ql", fontName="Helvetica-Bold", fontSize=7, textColor=CINZ3, leading=9)),
        Paragraph(pergunta.upper(), st("qv", fontName="Helvetica-Bold", fontSize=9, textColor=PRET, leading=12)),
    ]], colWidths=[2*cm, W-2*cm]))
    story.append(Spacer(1,8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1,8))

    # ── Tabela de dados ────────────────────────────────────
    if rows and columns:
        story.append(Paragraph("DADOS", st("dl", fontName="Helvetica-Bold", fontSize=7, textColor=CINZ3, leading=9)))
        story.append(Spacer(1,4))

        header = [Paragraph(c.upper().replace("_"," "), s_th) for c in columns]
        tdata  = [header]

        for row in rows[:150]:
            is_tot = is_total_row(row)
            line = []
            for i, col in enumerate(columns):
                val = row.get(col, "")
                txt = str(val) if val is not None else ""
                if i == 0:
                    sty = s_td_tot0 if is_tot else s_td
                else:
                    sty = s_td_tot if is_tot else (s_td_r if is_valor(txt) else s_td)
                    # formata números
                    if is_valor(txt) and txt.strip():
                        col_l = col.lower()
                        if any(x in col_l for x in ["fat","valor","liquido","receita"]):
                            txt = fmt_brl(txt)
                        elif any(x in col_l for x in ["rs_","preco","unitario","perc","desc","comis"]):
                            txt = fmt_num(txt)
                        else:
                            txt = fmt_num(txt)
                line.append(Paragraph(txt[:50], sty))
            tdata.append(line)

        col_w = W / len(columns)
        tbl = Table(tdata, colWidths=[col_w]*len(columns), repeatRows=1)
        tbl.setStyle(TableStyle([
            # cabeçalho
            ("BACKGROUND",(0,0),(-1,0), VERM),
            ("LINEBELOW",(0,0),(-1,0),1.5,AMAR),
            # zebra
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[BRAN,CINZ]),
            # grid
            ("GRID",(0,0),(-1,-1),0.3,CINZ2),
            # padding
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ]))

        # linha TOTAL em destaque
        for i, row in enumerate(rows[:150], start=1):
            if is_total_row(row):
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",(0,i),(-1,i),colors.HexColor("#FFF8DC")),
                    ("LINEABOVE",(0,i),(-1,i),1,AMAR),
                    ("LINEBELOW",(0,i),(-1,i),0.5,AMAR),
                ]))

        story.append(tbl)
        if row_count > 150:
            story.append(Spacer(1,3))
            story.append(Paragraph(f"* Exibindo 150 de {row_count} registros.", s_muted))

    story.append(Spacer(1,12))

    # ── Análise narrativa ──────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1,8))

    # Processa markdown da resposta
    for line in resposta.split("\n"):
        line = line.strip()
        if not line or line == "---": continue

        if line.startswith("# "):
            story.append(Paragraph(line[2:].upper(), st("rh1", fontName="Helvetica-Bold", fontSize=13, textColor=VERM, leading=16, spaceAfter=4)))
        elif line.startswith("## "):
            story.append(Spacer(1,6))
            story.append(Paragraph(line[3:], s_h2))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], st("rh3", fontName="Helvetica-Bold", fontSize=9, textColor=AZUL, leading=12, spaceAfter=2)))
        elif line.startswith("- ") or line.startswith("* "):
            txt = line[2:]
            txt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', txt)
            story.append(Paragraph("• " + txt, st("li", fontName="Helvetica", fontSize=9, textColor=PRET, leading=13, leftIndent=10, spaceAfter=2)))
        elif line.startswith("|"):
            pass  # tabelas markdown ignoradas aqui — já renderizamos os dados acima
        elif "⚠" in line or "ALERTA" in line.upper():
            txt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(txt, s_alerta))
        else:
            txt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
            txt = re.sub(r'\*(.+?)\*', r'<i>\1</i>', txt)
            story.append(Paragraph(txt, s_body))

    story.append(Spacer(1,12))

    # ── Rodapé ─────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZ2))
    story.append(Spacer(1,3))
    story.append(Paragraph(
        f"IAF VDDB · Analista Comercial Sênior · Frinense Alimentos · {hoje_str} · Documento confidencial",
        st("foot", fontName="Helvetica", fontSize=7, textColor=CINZ3, alignment=TA_CENTER, leading=9)
    ))

    doc.build(story)
    return buf.getvalue()
