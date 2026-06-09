"""Newspaper-style PDF of the 'Jornal do Dia'.

Layout (A4 portrait):
    1. Masthead: serif title + edition strip
    2. Hero photo (Palacio da Educacao) with caption
    3. KPI strip (Suplementado / Reduzido / Saldo / Expedientes)
    4. Manchete: chapeu + big headline + lead + meta
    5. Two columns: 'Curtas do Orcamento' + 'Radar de Deficits'
    6. Footer

Built with ReportLab using only built-in fonts (Times/Helvetica) so no
external font installation is required.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                KeepInFrame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from . import queries
from . import exportutils as eu

# ----------------------------- Brand tokens ------------------------------- #
# Paleta sóbria (branco/preto/cinza/vermelho) — coerente com identity.css e
# com a paleta dos demais PDFs (exportutils).
RED       = eu.PDF_RED                       # acento / déficit
RED_DARK  = colors.HexColor("#A10009")
INK       = eu.PDF_INK
INK_SOFT  = colors.HexColor("#2E3440")
MUTE      = eu.PDF_MUTE
LINE      = eu.PDF_LINE
LINE_SOFT = colors.HexColor("#E9ECF2")
PAPER     = colors.HexColor("#FFFFFF")
CHIP_BG   = colors.HexColor("#F4F5F7")
DEF_BG    = eu.PDF_DEF_BG
DEF_TXT   = eu.PDF_DEF_TXT


BASE_DIR = Path(__file__).resolve().parent.parent
# Versao otimizada (JPEG ~250KB) para embeddar no PDF, com fallback para o PNG
# de alta resolucao caso ela ainda nao tenha sido gerada.
_HERO_JPG = BASE_DIR / "static" / "img" / "headline-pdf.jpg"
_HERO_PNG = BASE_DIR / "static" / "img" / "headline.png"
HERO_IMAGE = _HERO_JPG if _HERO_JPG.exists() else _HERO_PNG


# ----------------------------- Formatting --------------------------------- #
# Helper único de moeda pt-BR compartilhado com app.py (exportutils).
_moeda = eu.brl
_moeda_compacta = eu.brl_compacta


def _data_pt(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return s


def _smartcap(text: str | None, n: int = 80) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _shorten_uo(uo: str | None) -> str:
    if not uo:
        return "uma Unidade Orçamentária"
    return _smartcap(uo, 64)


def _escape(text: str | None) -> str:
    if text is None:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# ----------------------------- Styles ------------------------------------- #
def _styles():
    return {
        "edicao": ParagraphStyle(
            "Edicao", fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=MUTE, alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "masthead": ParagraphStyle(
            "Masthead", fontName="Times-Bold", fontSize=46,
            leading=48, textColor=INK, alignment=TA_CENTER, spaceAfter=2,
        ),
        "subhead": ParagraphStyle(
            "Subhead", fontName="Times-Italic", fontSize=11,
            leading=14, textColor=INK_SOFT, alignment=TA_CENTER, spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "Caption", fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=MUTE, alignment=TA_LEFT, spaceAfter=2,
        ),
        "chapeu": ParagraphStyle(
            "Chapeu", fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=colors.white, alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "headline": ParagraphStyle(
            "Headline", fontName="Times-Bold", fontSize=22,
            leading=25, textColor=INK, alignment=TA_LEFT, spaceAfter=6,
        ),
        "lead": ParagraphStyle(
            "Lead", fontName="Times-Roman", fontSize=11,
            leading=15, textColor=INK_SOFT, alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "Meta", fontName="Helvetica", fontSize=8.5,
            leading=12, textColor=MUTE, alignment=TA_LEFT,
        ),
        "col_title": ParagraphStyle(
            "ColTitle", fontName="Helvetica-Bold", fontSize=10,
            leading=12, textColor=INK, alignment=TA_LEFT,
            spaceAfter=4, letterSpacing=1.4,
        ),
        "curta_data": ParagraphStyle(
            "CurtaData", fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=RED, alignment=TA_LEFT,
            spaceAfter=1, letterSpacing=0.8,
        ),
        "curta_corpo": ParagraphStyle(
            "CurtaCorpo", fontName="Times-Roman", fontSize=10,
            leading=12.5, textColor=INK_SOFT, alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "kpi_label": ParagraphStyle(
            "KpiLabel", fontName="Helvetica-Bold", fontSize=7,
            leading=8, textColor=MUTE, alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "kpi_value": ParagraphStyle(
            "KpiValue", fontName="Helvetica-Bold", fontSize=14,
            leading=16, textColor=INK, alignment=TA_CENTER, spaceAfter=2,
        ),
        "kpi_sub": ParagraphStyle(
            "KpiSub", fontName="Helvetica", fontSize=7,
            leading=8, textColor=MUTE, alignment=TA_CENTER,
        ),
    }


# ----------------------------- Builders ----------------------------------- #
def _build_masthead(story: list, st: dict, edicao: str) -> None:
    story.append(Paragraph(
        f"SEDUC &middot; EDIÇÃO DE {edicao.upper()}", st["edicao"]
    ))
    story.append(HRFlowable(width="100%", thickness=0.8, color=INK))
    story.append(Spacer(1, 4))
    story.append(Paragraph("O Diário do Orçamento", st["masthead"]))
    story.append(Paragraph(
        "Boletim editorial da Secretaria da Educação do Estado de São Paulo",
        st["subhead"]
    ))
    story.append(Spacer(1, 2))
    story.append(HRFlowable(width="100%", thickness=1.2, color=INK))
    story.append(HRFlowable(width="100%", thickness=0.5, color=INK,
                            spaceBefore=1.5))
    story.append(Spacer(1, 10))


def _build_hero(story: list, st: dict, available_width: float) -> None:
    if not HERO_IMAGE.exists():
        return
    img = Image(str(HERO_IMAGE))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = available_width
    img.drawHeight = min(available_width * ratio, 7.5 * cm)
    img.hAlign = "CENTER"
    story.append(img)
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "PALÁCIO DA EDUCAÇÃO &middot; Sede histórica da Secretaria da "
        "Educação na Praça da República, São Paulo.",
        st["caption"]
    ))
    story.append(Spacer(1, 12))


def _build_kpis(story: list, st: dict, m: dict, available_width: float) -> None:
    s = m["status"]
    cards = [
        ("SUPLEMENTADO",      _moeda_compacta(m["total_suplementacao"]),
         _moeda(m["total_suplementacao"])),
        ("REDUZIDO",          _moeda_compacta(m["total_reducao"]),
         _moeda(m["total_reducao"])),
        ("SALDO LÍQUIDO",     _moeda_compacta(m["saldo_liquido"]),
         "Suplementações – Reduções"),
        ("EXPEDIENTES",       f"{m['total_expedientes']:,}".replace(",", "."),
         f"{s['realizadas']} realizadas"),
    ]
    cell_w = (available_width - 6) / 4
    data = [[]]
    for label, value, sub in cards:
        cell = [
            Paragraph(_escape(label), st["kpi_label"]),
            Spacer(1, 2),
            Paragraph(_escape(value), st["kpi_value"]),
            Paragraph(_escape(sub), st["kpi_sub"]),
        ]
        data[0].append(cell)
    table = Table(data, colWidths=[cell_w] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CHIP_BG),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEABOVE", (1, 0), (1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    # Red top bar per cell
    bar_style = TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 2.4, RED),
    ])
    table.setStyle(bar_style)
    story.append(table)
    story.append(Spacer(1, 12))


def _build_manchete(story: list, st: dict, m: dict, available_width: float) -> None:
    if not m:
        story.append(Paragraph(
            "<i>Nenhuma manchete disponível para o período carregado.</i>",
            st["lead"]
        ))
        return

    # Chapeu (red box)
    chapeu = Table(
        [[Paragraph("MANCHETE &middot; MAIOR SUPLEMENTAÇÃO", st["chapeu"])]],
        colWidths=[5.6 * cm],
    )
    chapeu.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    chapeu.hAlign = "LEFT"
    story.append(chapeu)
    story.append(Spacer(1, 6))

    uo = _shorten_uo(m.get("uo_nome") or m.get("uo_codigo"))
    assunto = (m.get("assunto") or "execução orçamentária").lower()
    valor = _moeda_compacta(m.get("suplementacao") or 0)
    headline = f"{uo} recebe {valor} para {assunto}"
    story.append(Paragraph(_escape(headline), st["headline"]))

    lead = (
        f"Expediente <b>{_escape(m.get('expediente') or '—')}</b> "
        f"({_escape(m.get('tipo') or '—')}) destinou "
        f"<b>{_escape(_moeda(m.get('suplementacao') or 0))}</b> à ação "
        f"<i>{_escape(_smartcap(m.get('acao'), 70))}</i>, dentro do "
        f"programa <b>{_escape(m.get('programa') or '—')}</b>, financiado "
        f"pela fonte <b>{_escape(m.get('fonte') or '—')}</b>."
    )
    story.append(Paragraph(lead, st["lead"]))

    meta_data = [[
        Paragraph(f"<b>UO</b><br/>{_escape(m.get('uo_codigo') or '—')}", st["meta"]),
        Paragraph(f"<b>Grupo</b><br/>{_escape(m.get('grupo') or '—')}", st["meta"]),
        Paragraph(f"<b>Fonte</b><br/>{_escape(m.get('fonte') or '—')}", st["meta"]),
        Paragraph(f"<b>Envio</b><br/>{_escape(_data_pt(m.get('data_envio')))}", st["meta"]),
        Paragraph(f"<b>Conclusão</b><br/>{_escape(_data_pt(m.get('data_conclusao')))}", st["meta"]),
        Paragraph(f"<b>Status</b><br/>{_escape(m.get('status') or '—')}", st["meta"]),
    ]]
    meta_table = Table(meta_data, colWidths=[available_width / 6.0] * 6)
    meta_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.4, LINE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 4))
    story.append(meta_table)
    story.append(Spacer(1, 14))


def _build_two_columns(story: list, st: dict, timeline: list, alertas: list,
                       available_width: float) -> None:
    col_w = (available_width - 14) / 2

    # Left column: Curtas
    left_flowables = [
        Paragraph("CURTAS DO ORÇAMENTO", st["col_title"]),
        HRFlowable(width="100%", thickness=2, color=RED, spaceAfter=6),
    ]
    if not timeline:
        left_flowables.append(Paragraph("Sem registros.", st["curta_corpo"]))
    for r in timeline[:8]:
        data = _data_pt(r.get("data_conclusao") or r.get("data_envio"))
        uo = _shorten_uo(r.get("uo_nome") or r.get("uo_codigo"))
        assunto = (r.get("assunto") or "—").lower()
        valor = _moeda(r.get("suplementacao") or 0)
        left_flowables.append(Paragraph(data.upper(), st["curta_data"]))
        left_flowables.append(Paragraph(
            f"<b>{_escape(uo)}</b> recebeu suplementação para "
            f"<i>{_escape(_smartcap(assunto, 100))}</i> &mdash; "
            f"<b>{_escape(valor)}</b>.",
            st["curta_corpo"]
        ))

    # Right column: Radar de Deficits
    right_flowables = [
        Paragraph("RADAR DE DÉFICITS", st["col_title"]),
        HRFlowable(width="100%", thickness=2, color=RED, spaceAfter=6),
    ]
    if not alertas:
        right_flowables.append(Paragraph(
            "Nenhuma linha de execução em déficit no momento. "
            "Suplementações em curso preservam o saldo orçamentário.",
            st["curta_corpo"]
        ))
    for a in alertas[:6]:
        uo = _shorten_uo(a.get("uo_nome") or a.get("uo_codigo"))
        assunto = (a.get("assunto") or "—").lower()
        valor = _moeda(a.get("a_empenhar") or 0)
        right_flowables.append(Paragraph("ALERTA · DÉFICIT", st["curta_data"]))
        right_flowables.append(Paragraph(
            f"<b>{_escape(uo)}</b> &mdash; <i>{_escape(assunto)}</i>. "
            f"Valor a empenhar: <b>{_escape(valor)}</b>.",
            st["curta_corpo"]
        ))

    table = Table(
        [[left_flowables, "", right_flowables]],
        colWidths=[col_w, 14, col_w],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (2, 0), (2, 0), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(table)


def _build_resumo_deficit(story: list, st: dict, resumo: dict,
                          available_width: float) -> None:
    """Resumo executivo de déficits — grupos 33 (Custeio) e 44 (Capital),
    excluindo a folha de pessoal (31). Espelha o bloco da tela."""
    story.append(Paragraph("RESUMO DE DÉFICITS &middot; CUSTEIO E CAPITAL", st["col_title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=RED, spaceAfter=4))
    story.append(Paragraph(
        "Principais temas em déficit (A Empenhar &lt; 0) nos grupos 33 e 44. "
        "<b>Folha de pessoal (grupo 31) excluída.</b>", st["caption"]))
    story.append(Spacer(1, 8))

    por_grupo = resumo.get("deficit_por_grupo") or {}
    cards = [
        ("DÉFICIT TOTAL 33+44", _moeda_compacta(resumo.get("deficit_total_33_44") or 0),
         _moeda(resumo.get("deficit_total_33_44") or 0)),
        ("DÉFICIT CUSTEIO (33)", _moeda_compacta(por_grupo.get("33") or 0),
         "Grupo 33 · Custeio"),
        ("DÉFICIT CAPITAL (44)", _moeda_compacta(por_grupo.get("44") or 0),
         "Grupo 44 · Capital"),
        ("TEMAS EM DÉFICIT", f"{resumo.get('n_linhas') or 0}",
         "linhas 33/44 negativas"),
    ]
    cell_w = (available_width - 6) / 4
    krow = []
    for label, value, sub in cards:
        krow.append([
            Paragraph(_escape(label), st["kpi_label"]),
            Spacer(1, 2),
            Paragraph(_escape(value), st["kpi_value"]),
            Paragraph(_escape(sub), st["kpi_sub"]),
        ])
    ktable = Table([krow], colWidths=[cell_w] * 4)
    ktable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CHIP_BG),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 2.4, RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(ktable)
    story.append(Spacer(1, 10))

    linhas = resumo.get("linhas") or []
    if not linhas:
        story.append(Paragraph(
            "Nenhuma linha em déficit nos grupos 33/44 no momento.", st["curta_corpo"]))
        story.append(Spacer(1, 6))
        return

    cell = ParagraphStyle("rcell", fontName="Helvetica", fontSize=7.5,
                          leading=9.5, textColor=INK_SOFT)
    cell_b = ParagraphStyle("rcellb", parent=cell, fontName="Helvetica-Bold",
                            textColor=INK)
    cell_r = ParagraphStyle("rcellr", parent=cell, fontName="Helvetica-Bold",
                            textColor=DEF_TXT, alignment=TA_CENTER)
    head = ParagraphStyle("rhead", fontName="Helvetica-Bold", fontSize=7.5,
                          leading=9.5, textColor=colors.white)

    data = [[
        Paragraph("UGE", head), Paragraph("ASSUNTO / DESPESA", head),
        Paragraph("GRUPO", head), Paragraph("DÉFICIT (R$)", head),
    ]]
    for r in linhas:
        uge = r.get("uge_nome") or r.get("uge_codigo") or r.get("uo_nome") or "—"
        data.append([
            Paragraph(_escape(_smartcap(uge, 34)), cell_b),
            Paragraph(_escape(_smartcap(r.get("assunto") or "—", 60)), cell),
            Paragraph(_escape(r.get("grupo") or "—"), cell),
            Paragraph(_escape(_moeda(r.get("a_empenhar") or 0)), cell_r),
        ])
    col_w = [available_width * x for x in (0.26, 0.46, 0.10, 0.18)]
    table = Table(data, colWidths=col_w, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("GRID", (0, 0), (-1, -1), 0.25, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CHIP_BG]),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 14))


# ----------------------------- Page chrome -------------------------------- #
def _draw_page(canvas: Canvas, doc) -> None:
    canvas.saveState()
    page_w, page_h = A4
    # Top hairline + brand mark
    canvas.setStrokeColor(INK)
    canvas.setLineWidth(0.4)
    canvas.line(1.5 * cm, page_h - 0.9 * cm, page_w - 1.5 * cm, page_h - 0.9 * cm)

    canvas.setFillColor(RED)
    canvas.rect(1.5 * cm, page_h - 0.92 * cm, 1.2 * cm, 0.08 * cm,
                stroke=0, fill=1)

    canvas.setFillColor(MUTE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(2.9 * cm, page_h - 0.85 * cm,
                      "SEDUC · GOVERNO DO ESTADO DE SÃO PAULO")
    canvas.drawRightString(page_w - 1.5 * cm, page_h - 0.85 * cm,
                           "O DIÁRIO DO ORÇAMENTO")

    # Footer
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(1.5 * cm, 1.6 * cm, page_w - 1.5 * cm, 1.6 * cm)
    canvas.setFillColor(MUTE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(1.5 * cm, 1.1 * cm,
                      "SEDUC · Monitoramento Orçamentário · "
                      "Identidade visual conforme manual GESP v1.12.")
    canvas.drawRightString(
        page_w - 1.5 * cm, 1.1 * cm,
        f"Página {doc.page}"
    )
    canvas.restoreState()


# ----------------------------- Public API --------------------------------- #
def build_pdf() -> bytes:
    dados = queries.manchete_e_timeline(limite=8)
    metricas = queries.metricas_consolidadas({})
    alertas = queries.alertas_deficit({}, top_n=6)
    resumo_def = queries.resumo_deficit_jornal(top_n=8)

    buf = io.BytesIO()
    page_w, page_h = A4
    margin_x, margin_top, margin_bottom = 1.6 * cm, 1.4 * cm, 1.9 * cm
    frame = Frame(
        margin_x, margin_bottom,
        page_w - 2 * margin_x,
        page_h - margin_top - margin_bottom,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        showBoundary=0,
    )
    template = PageTemplate(id="diario", frames=[frame], onPage=_draw_page)
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin_x, rightMargin=margin_x,
        topMargin=margin_top, bottomMargin=margin_bottom,
        title="O Diário do Orçamento",
        author="SEDUC - Governo do Estado de São Paulo",
    )
    doc.addPageTemplates([template])

    st = _styles()
    edicao = datetime.now().strftime("%d/%m/%Y")
    available_width = page_w - 2 * margin_x

    story: list = []
    _build_masthead(story, st, edicao)
    _build_hero(story, st, available_width)
    _build_kpis(story, st, metricas, available_width)
    _build_manchete(story, st, dados.get("manchete"), available_width)
    _build_resumo_deficit(story, st, resumo_def, available_width)
    _build_two_columns(
        story, st, dados.get("timeline") or [], alertas or [], available_width
    )

    doc.build(story)
    return buf.getvalue()
