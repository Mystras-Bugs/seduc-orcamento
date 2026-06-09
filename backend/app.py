"""FastAPI entry-point for the SEDUC Budget Monitor (Jornal + BI)."""
from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import queries
from . import exportutils as eu
from .database import init_db
from .etl import import_xlsx, import_execucao_xlsx, import_necessidade_xlsx
from .pdf_jornal import build_pdf as build_jornal_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SEDUC - Monitoramento Orcamentario", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def page_jornal(request: Request):
    return templates.TemplateResponse(request, "jornal.html", {"page": "jornal"})


@app.get("/painel", response_class=HTMLResponse)
def page_painel(request: Request):
    return templates.TemplateResponse(request, "painel.html", {"page": "painel"})


@app.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request):
    return templates.TemplateResponse(request, "admin.html", {"page": "admin"})


@app.get("/execucao", response_class=HTMLResponse)
def page_execucao(request: Request):
    return templates.TemplateResponse(request, "execucao.html", {"page": "execucao"})


@app.get("/inteligencia", response_class=HTMLResponse)
def page_inteligencia(request: Request):
    return templates.TemplateResponse(request, "inteligencia.html", {"page": "inteligencia"})


@app.get("/pressao", response_class=HTMLResponse)
def page_pressao(request: Request):
    return templates.TemplateResponse(request, "pressao.html", {"page": "pressao"})


# --------------------------------------------------------------------------- #
# Filter helper
# --------------------------------------------------------------------------- #
def _collect_filtros(
    uo: Optional[str] = None,
    programa: Optional[str] = None,
    acao: Optional[str] = None,
    grupo: Optional[str] = None,
    elemento: Optional[str] = None,
    fonte: Optional[str] = None,
    assunto: Optional[str] = None,
    status: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
) -> dict:
    return {
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte, "assunto": assunto,
        "status": status, "data_inicio": data_inicio, "data_fim": data_fim,
    }


# --------------------------------------------------------------------------- #
# REST API
# --------------------------------------------------------------------------- #
@app.get("/api/filtros")
def api_filtros():
    return queries.filtros_disponiveis()


@app.get("/api/metricas")
def api_metricas(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    assunto: Optional[str] = None, status: Optional[str] = None,
    data_inicio: Optional[str] = None, data_fim: Optional[str] = None,
):
    return queries.metricas_consolidadas(
        _collect_filtros(uo, programa, acao, grupo, elemento, fonte,
                         assunto, status, data_inicio, data_fim)
    )


@app.get("/api/jornal")
def api_jornal():
    return queries.manchete_e_timeline()


@app.get("/api/distribuicao-uo")
def api_dist_uo(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    assunto: Optional[str] = None, status: Optional[str] = None,
    data_inicio: Optional[str] = None, data_fim: Optional[str] = None,
):
    return queries.distribuicao_por_uo(
        _collect_filtros(uo, programa, acao, grupo, elemento, fonte,
                         assunto, status, data_inicio, data_fim)
    )


@app.get("/api/distribuicao-grupo")
def api_dist_grupo(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    assunto: Optional[str] = None, status: Optional[str] = None,
    data_inicio: Optional[str] = None, data_fim: Optional[str] = None,
):
    return queries.distribuicao_por_grupo(
        _collect_filtros(uo, programa, acao, grupo, elemento, fonte,
                         assunto, status, data_inicio, data_fim)
    )


@app.get("/api/serie-mensal")
def api_serie_mensal(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    assunto: Optional[str] = None, status: Optional[str] = None,
    data_inicio: Optional[str] = None, data_fim: Optional[str] = None,
):
    return queries.serie_mensal(
        _collect_filtros(uo, programa, acao, grupo, elemento, fonte,
                         assunto, status, data_inicio, data_fim)
    )


@app.get("/api/status-funil")
def api_status_funil(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    assunto: Optional[str] = None, status: Optional[str] = None,
    data_inicio: Optional[str] = None, data_fim: Optional[str] = None,
):
    return queries.status_funil(
        _collect_filtros(uo, programa, acao, grupo, elemento, fonte,
                         assunto, status, data_inicio, data_fim)
    )


@app.get("/api/execucao")
def api_execucao(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    # Tabela pivotada de execução (mesma fonte da aba Execução Orçamentária).
    return queries.execucao_tabela({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    })


@app.get("/api/alertas")
def api_alertas():
    return queries.alertas_deficit(_collect_filtros(), top_n=6)


@app.get("/api/jornal/resumo-deficit")
def api_jornal_resumo_deficit():
    """Resumo executivo de déficits para o Jornal — grupos 33/44 (sem folha 31)."""
    return queries.resumo_deficit_jornal(top_n=8)


# --------------------------------------------------------------------------- #
# Execução Orçamentária endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/execucao/filtros")
def api_exec_filtros():
    return queries.execucao_filtros_disponiveis()


@app.get("/api/execucao/kpis")
def api_exec_kpis(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.execucao_kpis({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    })


@app.get("/api/execucao/por-uo")
def api_exec_por_uo(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.execucao_por_uo({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    })


@app.get("/api/execucao/mensal")
def api_exec_mensal(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.execucao_mensal({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    })


@app.get("/api/execucao/top-assuntos")
def api_exec_top_assuntos(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.execucao_top_assuntos({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    })


@app.get("/api/execucao/tabela")
def api_exec_tabela(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    agrupamento: Optional[str] = "assunto",
):
    return queries.execucao_tabela({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
        "agrupamento": agrupamento,
    })


@app.get("/api/export/jornal.pdf")
def export_jornal_pdf():
    pdf_bytes = build_jornal_pdf()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                'attachment; filename="diario-do-orcamento.pdf"'
        },
    )


# --------------------------------------------------------------------------- #
# Export endpoints (legado) — redirecionam para o pivot correto de execução,
# usando os helpers únicos de exportação (mesma saída de /api/execucao/export.*)
# --------------------------------------------------------------------------- #
def _exec_export_rows(uo, programa, acao, grupo, elemento, fonte,
                      classificacao, assunto, agrupamento="assunto"):
    return queries.execucao_tabela({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
        "agrupamento": agrupamento,
    })


@app.get("/api/export/execucao.csv")
def export_execucao_csv(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    agrupamento: Optional[str] = "assunto",
):
    rows = _exec_export_rows(uo, programa, acao, grupo, elemento, fonte,
                             classificacao, assunto, agrupamento)
    header = [
        "UO Codigo", "UO Nome", "Assunto", "Grupo", "Programa", "Ação",
        "Dotação", "Empenhado", "A Empenhar", "Liquidado", "A Liquidar", "Déficit",
    ]
    data = [[
        r["uo_codigo"], r["uo_nome"], r["assunto"], r["grupo"],
        r["programa"], r["acao"],
        eu.csv_num(r["dotacao"]), eu.csv_num(r["empenhado"]),
        eu.csv_num(r["a_empenhar"]), eu.csv_num(r["liquidado"]),
        eu.csv_num(r["a_liquidar"]), "SIM" if r["deficit"] else "NAO",
    ] for r in rows]
    return eu.csv_response("execucao_orcamentaria.csv", header, data)


@app.get("/api/export/execucao.pdf")
def export_execucao_pdf(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    agrupamento: Optional[str] = "assunto",
):
    return _build_execucao_pdf(_exec_export_rows(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto, agrupamento))


# --------------------------------------------------------------------------- #
# Import endpoints
# --------------------------------------------------------------------------- #
@app.post("/api/importar")
async def api_importar(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Envie um arquivo .xlsx ou .xlsm")
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        summary = import_xlsx(tmp_path, replace=True)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    return JSONResponse(summary)


@app.post("/api/importar-execucao")
async def api_importar_execucao(file: UploadFile = File(...)):
    """Import the PLANEJADO_CONSOLIDADO execution spreadsheet."""
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Envie um arquivo .xlsx ou .xlsm")
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        summary = import_execucao_xlsx(tmp_path, replace=True)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    return JSONResponse(summary)


@app.post("/api/importar-necessidade")
async def api_importar_necessidade(file: UploadFile = File(...)):
    """Import the NECESSIDADE spreadsheet (necessidade atualizada por UGE)."""
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Envie um arquivo .xlsx ou .xlsm")
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        summary = import_necessidade_xlsx(tmp_path, replace=True)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    return JSONResponse(summary)


# --------------------------------------------------------------------------- #
# Export endpoints – Execução
# --------------------------------------------------------------------------- #
@app.get("/api/execucao/export.csv")
def export_exec_csv(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    agrupamento: Optional[str] = "assunto",
):
    rows = queries.execucao_tabela({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
        "agrupamento": agrupamento,
    })
    header = [
        "UO Codigo", "UO Nome", "Assunto", "Grupo", "Programa", "Ação",
        "Dotação", "Empenhado", "A Empenhar", "Liquidado", "A Liquidar", "Déficit",
    ]
    data = [[
        r["uo_codigo"], r["uo_nome"], r["assunto"], r["grupo"],
        r["programa"], r["acao"],
        eu.csv_num(r["dotacao"]), eu.csv_num(r["empenhado"]),
        eu.csv_num(r["a_empenhar"]), eu.csv_num(r["liquidado"]),
        eu.csv_num(r["a_liquidar"]), "SIM" if r["deficit"] else "NAO",
    ] for r in rows]
    return eu.csv_response("execucao_orcamentaria.csv", header, data)


def _build_execucao_pdf(rows: list) -> StreamingResponse:
    """PDF da Execução (landscape A4) — paleta e formatação únicas (exportutils).
    Usado por /api/execucao/export.pdf e pelo legado /api/export/execucao.pdf."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    n_def = sum(1 for r in rows if r["deficit"])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=20, rightMargin=20, topMargin=24, bottomMargin=20)
    styles = getSampleStyleSheet()
    title    = Paragraph("<b>SEDUC - Relatório de Execução Orçamentária</b>", styles["Title"])
    subtitle = Paragraph(
        f"Total de linhas: {len(rows)} · Linhas em déficit (A Empenhar &lt; 0): {n_def}",
        styles["Normal"])

    data = [["UO", "Assunto", "Grp", "Dotação", "Empenhado", "A Empenhar", "Liquidado", "A Liquidar"]]
    deficit_rows = []
    for i, r in enumerate(rows[:300], start=1):
        if r["deficit"]:
            deficit_rows.append(i)
        data.append([
            (r["uo_codigo"] or "")[:10],
            (r["assunto"] or "")[:40],
            (r["grupo"] or "")[:4],
            eu.brl(r["dotacao"]),
            eu.brl(r["empenhado"]),
            eu.brl(r["a_empenhar"]),
            eu.brl(r["liquidado"]),
            eu.brl(r["a_liquidar"]),
        ])
    table = Table(data, repeatRows=1)
    style = eu.pdf_table_style(align_right_from=3)
    for idx in deficit_rows:
        eu.mark_deficit(style, idx, valor_col=5)  # coluna "A Empenhar"
    table.setStyle(style)
    doc.build([title, subtitle, Spacer(1, 12), table])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=execucao_orcamentaria.pdf"},
    )


@app.get("/api/execucao/export.pdf")
def export_exec_pdf(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    agrupamento: Optional[str] = "assunto",
):
    return _build_execucao_pdf(queries.execucao_tabela({
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
        "agrupamento": agrupamento,
    }))


# --------------------------------------------------------------------------- #
# Inteligência Orçamentária — Radar de Pressões & Déficits
# Aceita os mesmos query-params da execução.
# --------------------------------------------------------------------------- #
def _collect_intel(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
) -> dict:
    return {
        "uo": uo, "programa": programa, "acao": acao, "grupo": grupo,
        "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    }


@app.get("/api/inteligencia/kpis")
def api_intel_kpis(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.inteligencia_kpis(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/inteligencia/esgotamento")
def api_intel_esgotamento(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
    top_n: int = 20,
):
    return queries.projecao_esgotamento(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto), top_n)


@app.get("/api/inteligencia/ritmo")
def api_intel_ritmo(
    dimensao: str = "uo",
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.ritmo_por_dimensao(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto), dimensao)


@app.get("/api/inteligencia/folga-pressao")
def api_intel_folga_pressao(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.folga_vs_pressao(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/inteligencia/creditos")
def api_intel_creditos(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.cobertura_creditos(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/inteligencia/insights")
def api_intel_insights(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    return queries.inteligencia_insights(_collect_intel(
        uo, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/inteligencia/simular")
def api_intel_simular(
    valor: float = 0,
    grupo: Optional[str] = None, fonte: Optional[str] = None,
    uo: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    elemento: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    filtros = _collect_intel(uo, programa, acao, grupo, elemento, fonte,
                             classificacao, assunto)
    return queries.simular_cenario(filtros, valor, grupo=grupo, fonte=fonte, uo=uo)


# --------------------------------------------------------------------------- #
# Export endpoints — Inteligência
# --------------------------------------------------------------------------- #
@app.get("/api/inteligencia/export.csv")
def export_intel_csv(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    filtros = _collect_intel(uo, programa, acao, grupo, elemento, fonte,
                             classificacao, assunto)
    rows = queries.projecao_esgotamento(filtros, top_n=1000)
    header = [
        "UO Codigo", "UO Nome", "Assunto", "Grupo", "Programa", "Ação",
        "Dotação", "Empenhado", "A Empenhar", "Ritmo Mensal",
        "Mês Esgotamento", "Risco",
    ]
    data = [[
        r["uo_codigo"], r["uo_nome"], r["assunto"], r["grupo"],
        r["programa"], r["acao"],
        eu.csv_num(r["dotacao"]), eu.csv_num(r["empenhado"]),
        eu.csv_num(r["a_empenhar"]), eu.csv_num(r["burn_mensal"]),
        "" if r["mes_esgotamento"] is None else f"{r['mes_esgotamento']:.1f}".replace(".", ","),
        r["risco"],
    ] for r in rows]
    return eu.csv_response("inteligencia_orcamentaria.csv", header, data)


@app.get("/api/inteligencia/export.pdf")
def export_intel_pdf(
    uo: Optional[str] = None, programa: Optional[str] = None,
    acao: Optional[str] = None, grupo: Optional[str] = None,
    elemento: Optional[str] = None, fonte: Optional[str] = None,
    classificacao: Optional[str] = None, assunto: Optional[str] = None,
):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    filtros = _collect_intel(uo, programa, acao, grupo, elemento, fonte,
                             classificacao, assunto)
    rows = queries.projecao_esgotamento(filtros, top_n=200)
    insights = queries.inteligencia_insights(filtros)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=20, rightMargin=20, topMargin=24, bottomMargin=20)
    styles = getSampleStyleSheet()
    title = Paragraph(
        "<b>SEDUC - Inteligência Orçamentária · Radar de Pressões &amp; Déficits</b>",
        styles["Title"])
    subtitle = Paragraph(
        f"Linhas em risco de esgotamento: {len(rows)} · "
        f"Data de referência: 08/06/2026", styles["Normal"])

    # Bloco com os 3-4 principais insights no topo
    flow = [title, subtitle, Spacer(1, 10)]
    sev_color = {"critico": "#A10009", "alerta": "#8A5A00",
                 "info": "#3E5C76", "ok": "#3F6B52"}
    ins_style = ParagraphStyle("ins", parent=styles["Normal"], fontSize=9, leading=12)
    flow.append(Paragraph("<b>Principais alertas</b>", styles["Heading3"]))
    for it in insights[:4]:
        cor = sev_color.get(it["severidade"], "#15181F")
        flow.append(Paragraph(
            f'<font color="{cor}"><b>[{it["severidade"].upper()}] {it["titulo"]}</b></font> — '
            f'{it["texto"]}', ins_style))
    flow.append(Spacer(1, 12))

    data = [["UO", "Assunto", "Grp", "Dotação", "Empenhado",
             "A Empenhar", "Ritmo/mês", "Mês Esg.", "Risco"]]
    flag_rows = []
    for i, r in enumerate(rows[:200], start=1):
        if r["risco"] in ("DEFICIT", "CRITICO"):
            flag_rows.append(i)
        data.append([
            (r["uo_codigo"] or "")[:10],
            (r["assunto"] or "")[:38],
            (r["grupo"] or "")[:4],
            eu.brl(r["dotacao"]),
            eu.brl(r["empenhado"]),
            eu.brl(r["a_empenhar"]),
            eu.brl(r["burn_mensal"]),
            "—" if r["mes_esgotamento"] is None else f"{r['mes_esgotamento']:.1f}",
            r["risco"],
        ])
    table = Table(data, repeatRows=1)
    style = eu.pdf_table_style(align_right_from=3)
    for idx in flag_rows:
        eu.mark_deficit(style, idx, valor_col=5)  # coluna "A Empenhar"
    table.setStyle(style)
    flow.append(table)
    doc.build(flow)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=inteligencia_orcamentaria.pdf"},
    )


# --------------------------------------------------------------------------- #
# Pressão Orçamentária — Necessidade Atualizada × Dotação Atual
# Mesmos query-params da execução + uge.
# --------------------------------------------------------------------------- #
def _collect_pressao(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
) -> dict:
    return {
        "uo": uo, "uge": uge, "programa": programa, "acao": acao,
        "grupo": grupo, "elemento": elemento, "fonte": fonte,
        "classificacao": classificacao, "assunto": assunto,
    }


@app.get("/api/pressao/filtros")
def api_pressao_filtros():
    return queries.pressao_filtros_disponiveis()


@app.get("/api/pressao/kpis")
def api_pressao_kpis(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    return queries.pressao_kpis(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/pressao/por-linha")
def api_pressao_por_linha(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    return queries.pressao_por_linha(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/pressao/por-uge")
def api_pressao_por_uge(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    return queries.pressao_por_uge(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto))


@app.get("/api/pressao/ritmo")
def api_pressao_ritmo(
    dimensao: str = "grupo",
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    return queries.pressao_por_dimensao(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto), dimensao)


@app.get("/api/pressao/insights")
def api_pressao_insights(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    return queries.pressao_insights(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto))


# --------------------------------------------------------------------------- #
# Export endpoints — Pressão
# --------------------------------------------------------------------------- #
@app.get("/api/pressao/export.csv")
def export_pressao_csv(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    rows = queries.pressao_por_linha(_collect_pressao(
        uo, uge, programa, acao, grupo, elemento, fonte, classificacao, assunto))
    header = [
        "UGE Codigo", "UGE Nome", "UO Codigo", "Assunto",
        "Programa", "Ação", "Grupo", "Elemento", "Fonte",
        "Necessidade Atualizada", "Dotação Atual", "Pressão", "Cobertura %",
        "Empenhado", "A Empenhar", "Liquidado", "A Liquidar",
        "A Empenhar (planilha)", "A Liquidar (planilha)", "Divergência", "Situação",
    ]
    data = [[
        r["uge_codigo"], r["uge_nome"], r["uo_codigo"], r["assunto"],
        r["programa"], r["acao"], r["grupo"], r["elemento"], r["fonte"],
        eu.csv_num(r["necessidade"]), eu.csv_num(r["dotacao"]), eu.csv_num(r["pressao"]),
        eu.csv_pct(r["cobertura"]),
        eu.csv_num(r["empenhado"]), eu.csv_num(r["a_empenhar"]),
        eu.csv_num(r["liquidado"]), eu.csv_num(r["a_liquidar"]),
        eu.csv_num(r["a_empenhar_plan"]), eu.csv_num(r["a_liquidar_plan"]),
        "SIM" if r["divergencia"] else "NAO", r["situacao"],
    ] for r in rows]
    return eu.csv_response("pressao_orcamentaria.csv", header, data)


@app.get("/api/pressao/export.pdf")
def export_pressao_pdf(
    uo: Optional[str] = None, uge: Optional[str] = None,
    programa: Optional[str] = None, acao: Optional[str] = None,
    grupo: Optional[str] = None, elemento: Optional[str] = None,
    fonte: Optional[str] = None, classificacao: Optional[str] = None,
    assunto: Optional[str] = None,
):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    filtros = _collect_pressao(uo, uge, programa, acao, grupo, elemento,
                               fonte, classificacao, assunto)
    rows = queries.pressao_por_linha(filtros)
    insights = queries.pressao_insights(filtros)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=20, rightMargin=20, topMargin=24, bottomMargin=20)
    styles = getSampleStyleSheet()
    title = Paragraph(
        "<b>SEDUC - Pressão Orçamentária · Necessidade Atualizada × Dotação Atual</b>",
        styles["Title"])
    subtitle = Paragraph(
        f"Linhas: {len(rows)} · Data de referência: 08/06/2026", styles["Normal"])

    flow = [title, subtitle, Spacer(1, 10)]
    sev_color = {"critico": "#A10009", "alerta": "#8A5A00",
                 "info": "#3E5C76", "ok": "#3F6B52"}
    ins_style = ParagraphStyle("ins", parent=styles["Normal"], fontSize=9, leading=12)
    flow.append(Paragraph("<b>Principais alertas</b>", styles["Heading3"]))
    for it in insights[:4]:
        cor = sev_color.get(it["severidade"], "#15181F")
        flow.append(Paragraph(
            f'<font color="{cor}"><b>[{it["severidade"].upper()}] {it["titulo"]}</b></font> — '
            f'{it["texto"]}', ins_style))
    flow.append(Spacer(1, 12))

    data = [["UGE", "Assunto", "Estrutura", "Necessidade", "Dotação",
             "Pressão", "Cob.%", "A Empenhar", "Situação"]]
    flag_rows = []
    for i, r in enumerate(rows[:200], start=1):
        if r["situacao"] in ("DEFICIT", "PRESSAO"):
            flag_rows.append(i)
        estrut = " ".join(x for x in [r["programa"], r["acao"], r["grupo"]] if x)
        cob = "—" if r["cobertura"] is None else f"{r['cobertura']*100:.0f}%"
        data.append([
            (r["uge_codigo"] or "")[:8],
            (r["assunto"] or "")[:36],
            estrut[:16],
            eu.brl(r["necessidade"]),
            eu.brl(r["dotacao"]),
            eu.brl(r["pressao"]),
            cob,
            eu.brl(r["a_empenhar"]),
            r["situacao"],
        ])
    table = Table(data, repeatRows=1)
    style = eu.pdf_table_style(align_right_from=3)
    for idx in flag_rows:
        eu.mark_deficit(style, idx, valor_col=5)  # coluna "Pressão"
    table.setStyle(style)
    flow.append(table)
    doc.build(flow)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=pressao_orcamentaria.pdf"},
    )


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
