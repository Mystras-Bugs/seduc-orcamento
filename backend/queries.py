"""SQL queries that power the dashboards."""
from __future__ import annotations

from typing import Any

from .database import get_conn

MESES_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
MESES_COL = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _build_where(filtros: dict[str, Any]) -> tuple[str, list]:
    clauses, params = [], []
    if filtros.get("uo"):
        clauses.append("uo_codigo = ?")
        params.append(filtros["uo"])
    if filtros.get("programa"):
        clauses.append("programa = ?")
        params.append(filtros["programa"])
    if filtros.get("acao"):
        clauses.append("acao = ?")
        params.append(filtros["acao"])
    if filtros.get("grupo"):
        clauses.append("grupo = ?")
        params.append(filtros["grupo"])
    if filtros.get("elemento"):
        clauses.append("elemento = ?")
        params.append(filtros["elemento"])
    if filtros.get("fonte"):
        clauses.append("fonte = ?")
        params.append(filtros["fonte"])
    if filtros.get("assunto"):
        clauses.append("assunto LIKE ?")
        params.append(f"%{filtros['assunto']}%")
    if filtros.get("status"):
        clauses.append("status = ?")
        params.append(filtros["status"])
    if filtros.get("data_inicio"):
        clauses.append("COALESCE(data_conclusao, data_envio) >= ?")
        params.append(filtros["data_inicio"])
    if filtros.get("data_fim"):
        clauses.append("COALESCE(data_conclusao, data_envio) <= ?")
        params.append(filtros["data_fim"])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def filtros_disponiveis() -> dict[str, list]:
    with get_conn() as conn:
        def col(name):
            rows = conn.execute(
                f"SELECT DISTINCT {name} v FROM expedientes WHERE {name} IS NOT NULL ORDER BY 1"
            ).fetchall()
            return [r["v"] for r in rows]

        # Agrupa UOs pelo codigo numerico: o mesmo codigo com nomes
        # ligeiramente diferentes (acento, abreviacao, pontuacao) deve
        # aparecer uma unica vez no filtro. Rotulo canonico = nome com
        # maior numero de ocorrencias; em empate, o mais longo.
        uos = conn.execute(
            """
            SELECT uo_codigo,
                   (SELECT uo_nome FROM expedientes e2
                     WHERE e2.uo_codigo = e1.uo_codigo
                       AND e2.uo_nome IS NOT NULL
                     GROUP BY uo_nome
                     ORDER BY COUNT(*) DESC, LENGTH(uo_nome) DESC, uo_nome
                     LIMIT 1) AS uo_nome
              FROM expedientes e1
             WHERE uo_codigo IS NOT NULL
             GROUP BY uo_codigo
             ORDER BY uo_codigo
            """
        ).fetchall()

        return {
            "uos": [{"codigo": r["uo_codigo"], "nome": r["uo_nome"] or r["uo_codigo"]} for r in uos],
            "programas": col("programa"),
            "acoes": col("acao"),
            "grupos": col("grupo"),
            "elementos": col("elemento"),
            "fontes": col("fonte"),
            "tipos": col("tipo"),
            "status": col("status"),
            "assuntos": col("assunto"),
        }


def metricas_consolidadas(filtros: dict[str, Any]) -> dict:
    where, params = _build_where(filtros)
    with get_conn() as conn:
        row = conn.execute(
            f"""SELECT
                COUNT(*)                                            AS total,
                COALESCE(SUM(suplementacao),0)                      AS sup_total,
                COALESCE(SUM(reducao),0)                            AS red_total,
                SUM(CASE WHEN status='Realizada'    THEN 1 ELSE 0 END) AS realizadas,
                SUM(CASE WHEN status='Em Andamento' THEN 1 ELSE 0 END) AS andamento,
                SUM(CASE WHEN status='Em Elaboracao' THEN 1 ELSE 0 END) AS elaboracao
                FROM expedientes{where}""",
            params,
        ).fetchone()
    return {
        "total_expedientes": row["total"],
        "total_suplementacao": row["sup_total"] or 0,
        "total_reducao": row["red_total"] or 0,
        "saldo_liquido": (row["sup_total"] or 0) - (row["red_total"] or 0),
        "status": {
            "realizadas": row["realizadas"] or 0,
            "em_andamento": row["andamento"] or 0,
            "em_elaboracao": row["elaboracao"] or 0,
        },
    }


def manchete_e_timeline(limite: int = 12) -> dict:
    with get_conn() as conn:
        manchete = conn.execute(
            """SELECT * FROM expedientes
               WHERE suplementacao > 0
               ORDER BY suplementacao DESC, data_conclusao DESC
               LIMIT 1"""
        ).fetchone()
        timeline = conn.execute(
            f"""SELECT * FROM expedientes
                WHERE suplementacao > 0
                ORDER BY COALESCE(data_conclusao, data_envio) DESC,
                         suplementacao DESC
                LIMIT {int(limite)}"""
        ).fetchall()
    return {
        "manchete": dict(manchete) if manchete else None,
        "timeline": [dict(r) for r in timeline],
    }


def distribuicao_por_uo(filtros: dict[str, Any]) -> list[dict]:
    where, params = _build_where(filtros)
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT uo_codigo,
                       MAX(uo_nome) AS uo_nome,
                       SUM(suplementacao) AS sup,
                       SUM(reducao)       AS red
                FROM expedientes
                {where}
                GROUP BY uo_codigo
                HAVING sup > 0 OR red > 0
                ORDER BY sup DESC
                LIMIT 15""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def distribuicao_por_grupo(filtros: dict[str, Any]) -> list[dict]:
    where, params = _build_where(filtros)
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT grupo,
                       SUM(suplementacao) AS sup,
                       SUM(reducao)       AS red
                FROM expedientes
                {where}
                GROUP BY grupo
                ORDER BY sup DESC""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def serie_mensal(filtros: dict[str, Any]) -> dict:
    where, params = _build_where(filtros)
    parts = []
    for col in MESES_COL:
        parts.append(
            f"SUM(CASE WHEN suplementacao>0 THEN {col} ELSE 0 END) AS sup_{col}"
        )
        parts.append(
            f"SUM(CASE WHEN reducao>0 THEN {col} ELSE 0 END) AS red_{col}"
        )
    sql = f"SELECT {', '.join(parts)} FROM expedientes {where}"
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    sup_series, red_series = [], []
    cum_sup, cum_red = 0.0, 0.0
    cum_sup_series, cum_red_series = [], []
    for col in MESES_COL:
        s = row[f"sup_{col}"] or 0
        r = abs(row[f"red_{col}"] or 0)
        sup_series.append(s)
        red_series.append(r)
        cum_sup += s
        cum_red += r
        cum_sup_series.append(cum_sup)
        cum_red_series.append(cum_red)
    return {
        "labels": MESES_PT,
        "suplementacao_mes": sup_series,
        "reducao_mes": red_series,
        "suplementacao_acum": cum_sup_series,
        "reducao_acum": cum_red_series,
    }


def status_funil(filtros: dict[str, Any]) -> list[dict]:
    where, params = _build_where(filtros)
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT status, COUNT(*) AS n
                FROM expedientes {where} GROUP BY status""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def execucao_filtros_disponiveis() -> dict:
    """Return distinct filter values from the execucao_orcamentaria table."""
    with get_conn() as conn:
        def col(name):
            rows = conn.execute(
                f"SELECT DISTINCT {name} v FROM execucao_orcamentaria"
                f" WHERE {name} IS NOT NULL ORDER BY 1"
            ).fetchall()
            return [r["v"] for r in rows]

        uos = conn.execute(
            """SELECT uo_codigo,
                      (SELECT uo_nome FROM execucao_orcamentaria e2
                        WHERE e2.uo_codigo = e1.uo_codigo
                          AND e2.uo_nome IS NOT NULL
                        GROUP BY uo_nome ORDER BY COUNT(*) DESC LIMIT 1) AS uo_nome
               FROM execucao_orcamentaria e1
              WHERE uo_codigo IS NOT NULL
              GROUP BY uo_codigo ORDER BY uo_codigo"""
        ).fetchall()

        return {
            "uos": [{"codigo": r["uo_codigo"], "nome": r["uo_nome"] or r["uo_codigo"]} for r in uos],
            "programas":      col("programa"),
            "acoes":          col("acao"),
            "grupos":         col("grupo"),
            "elementos":      col("elemento"),
            "fontes":         col("fonte"),
            "classificacoes": col("classificacao"),
        }


def _exec_where(filtros: dict) -> tuple[str, list]:
    """Build WHERE clause filtering the execucao_orcamentaria table."""
    clauses, params = [], []
    if filtros.get("uo"):
        clauses.append("uo_codigo = ?")
        params.append(filtros["uo"])
    if filtros.get("programa"):
        clauses.append("programa = ?")
        params.append(filtros["programa"])
    if filtros.get("acao"):
        clauses.append("acao = ?")
        params.append(filtros["acao"])
    if filtros.get("grupo"):
        clauses.append("grupo = ?")
        params.append(filtros["grupo"])
    if filtros.get("elemento"):
        clauses.append("elemento = ?")
        params.append(filtros["elemento"])
    if filtros.get("fonte"):
        clauses.append("fonte = ?")
        params.append(filtros["fonte"])
    if filtros.get("classificacao"):
        clauses.append("classificacao = ?")
        params.append(filtros["classificacao"])
    if filtros.get("assunto"):
        clauses.append("assunto LIKE ?")
        params.append(f"%{filtros['assunto']}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _pivot_exec(filtros: dict,
                group_by: str = "uo_codigo, uo_nome, assunto, programa, acao, grupo",
                group_cols: str | None = None) -> list[dict]:
    """
    Pivot the 5 TABELA rows per budget line into a single object with:
    dotacao, empenhado, a_empenhar, liquidado, a_liquidar.

    ``group_by``   -> projeção do SELECT (pode conter MAX(col) AS alias);
    ``group_cols`` -> chaves reais do GROUP BY (apenas colunas simples). Quando
    None, usa ``group_by`` (caso em que ele não pode conter agregações/alias).
    """
    where, params = _exec_where(filtros)
    group_clause = group_cols or group_by
    sql = f"""
        SELECT {group_by},
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
               SUM(CASE WHEN tabela LIKE '35%' THEN valor ELSE 0 END) AS a_empenhar,
               SUM(CASE WHEN tabela LIKE '40%' THEN valor ELSE 0 END) AS liquidado,
               SUM(CASE WHEN tabela LIKE '45%' THEN valor ELSE 0 END) AS a_liquidar
        FROM execucao_orcamentaria {where}
        GROUP BY {group_clause}
        HAVING dotacao > 0 OR empenhado > 0
        ORDER BY dotacao DESC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execucao_kpis(filtros: dict) -> dict:
    """Consolidated KPI totals for the execução page."""
    where, params = _exec_where(filtros)
    sql = f"""
        SELECT
            SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
            SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
            SUM(CASE WHEN tabela LIKE '35%' THEN valor ELSE 0 END) AS a_empenhar,
            SUM(CASE WHEN tabela LIKE '40%' THEN valor ELSE 0 END) AS liquidado,
            SUM(CASE WHEN tabela LIKE '45%' THEN valor ELSE 0 END) AS a_liquidar
        FROM execucao_orcamentaria {where}
    """
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    return {
        "dotacao":    row["dotacao"]    or 0,
        "empenhado":  row["empenhado"]  or 0,
        "a_empenhar": row["a_empenhar"] or 0,
        "liquidado":  row["liquidado"]  or 0,
        "a_liquidar": row["a_liquidar"] or 0,
    }


def execucao_por_uo(filtros: dict) -> list[dict]:
    """Dotacao / empenhado / liquidado grouped by UO (top 15)."""
    where, params = _exec_where(filtros)
    sql = f"""
        SELECT uo_codigo, MAX(uo_nome) AS uo_nome,
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
               SUM(CASE WHEN tabela LIKE '40%' THEN valor ELSE 0 END) AS liquidado
        FROM execucao_orcamentaria {where}
        GROUP BY uo_codigo
        HAVING dotacao > 0
        ORDER BY dotacao DESC
        LIMIT 15
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execucao_mensal(filtros: dict) -> dict:
    """Monthly execution values (summed across TABELA codes 30, 35, 40)."""
    where, params = _exec_where(filtros)
    meses = [f"mes_{str(i).zfill(2)}" for i in range(1, 13)]
    parts_emp  = [f"SUM(CASE WHEN tabela LIKE '30%' THEN {m} ELSE 0 END) AS emp_{m}"  for m in meses]
    parts_aem  = [f"SUM(CASE WHEN tabela LIKE '35%' THEN {m} ELSE 0 END) AS aem_{m}"  for m in meses]
    parts_liq  = [f"SUM(CASE WHEN tabela LIKE '40%' THEN {m} ELSE 0 END) AS liq_{m}"  for m in meses]
    sql = f"SELECT {', '.join(parts_emp + parts_aem + parts_liq)} FROM execucao_orcamentaria {where}"
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    empenhado, a_empenhar, liquidado = [], [], []
    for m in meses:
        empenhado.append(row[f"emp_{m}"]  or 0)
        a_empenhar.append(row[f"aem_{m}"] or 0)
        liquidado.append(row[f"liq_{m}"]  or 0)
    return {"empenhado": empenhado, "a_empenhar": a_empenhar, "liquidado": liquidado}


def execucao_top_assuntos(filtros: dict, top_n: int = 10) -> list[dict]:
    """Top N assuntos by dotacao."""
    where, params = _exec_where(filtros)
    sql = f"""
        SELECT assunto,
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao
        FROM execucao_orcamentaria {where}
        GROUP BY assunto
        HAVING dotacao > 0
        ORDER BY dotacao DESC
        LIMIT {int(top_n)}
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execucao_tabela(filtros: dict) -> list[dict]:
    """
    Full execution table pivoted per budget key, with derived fields.
    agrupamento hint in filtros selects the GROUP BY level.
    """
    agrupamento = filtros.get("agrupamento", "assunto")
    # (projeção do SELECT, chaves reais do GROUP BY)
    group_map = {
        "assunto":  ("uo_codigo, MAX(uo_nome) AS uo_nome, assunto, grupo, MAX(programa) AS programa, MAX(acao) AS acao",
                     "uo_codigo, assunto, grupo"),
        "uo":       ("uo_codigo, MAX(uo_nome) AS uo_nome, MAX(assunto) AS assunto, MAX(grupo) AS grupo, MAX(programa) AS programa, MAX(acao) AS acao",
                     "uo_codigo"),
        "programa": ("uo_codigo, MAX(uo_nome) AS uo_nome, MAX(assunto) AS assunto, MAX(grupo) AS grupo, programa, acao",
                     "uo_codigo, programa, acao"),
        "elemento": ("uo_codigo, MAX(uo_nome) AS uo_nome, MAX(assunto) AS assunto, grupo, elemento, MAX(programa) AS programa, MAX(acao) AS acao",
                     "uo_codigo, grupo, elemento"),
    }
    select_cols, group_cols = group_map.get(agrupamento, group_map["assunto"])

    rows = _pivot_exec(filtros, group_by=select_cols, group_cols=group_cols)
    result = []
    for r in rows:
        dotacao    = r.get("dotacao")    or 0
        empenhado  = r.get("empenhado")  or 0
        a_empenhar = r.get("a_empenhar") or 0
        liquidado  = r.get("liquidado")  or 0
        a_liquidar = r.get("a_liquidar") or 0
        result.append({
            "uo_codigo":  r.get("uo_codigo"),
            "uo_nome":    r.get("uo_nome"),
            "assunto":    r.get("assunto"),
            "grupo":      r.get("grupo"),
            "programa":   r.get("programa"),
            "acao":       r.get("acao"),
            "elemento":   r.get("elemento"),
            "dotacao":    dotacao,
            "empenhado":  empenhado,
            "a_empenhar": a_empenhar,
            "liquidado":  liquidado,
            "a_liquidar": a_liquidar,
            "deficit":    a_empenhar < 0,
        })
    return result


def alertas_deficit(filtros: dict, top_n: int = 5) -> list[dict]:
    """Top N budget lines with negative a_empenhar (deficit)."""
    rows = execucao_tabela(filtros)
    rows = [r for r in rows if r["deficit"]]
    rows.sort(key=lambda r: r["a_empenhar"])
    return rows[:top_n]


def resumo_deficit_jornal(top_n: int = 8) -> dict:
    """Resumo executivo de déficits para o Jornal — APENAS grupos 33 (Custeio)
    e 44 (Capital); a folha de pessoal (grupo 31) é SEMPRE excluída.

    Pivota execucao_orcamentaria por (uo, uge, assunto, grupo, programa, acao),
    deriva a_empenhar = dotacao − empenhado e devolve as linhas em déficit
    (a_empenhar < 0) ordenadas do mais negativo para o menos, além de totais
    consolidados.
    """
    sql = """
        SELECT uo_codigo, MAX(uo_nome) AS uo_nome,
               uge_codigo, MAX(uge_nome) AS uge_nome,
               assunto, grupo,
               MAX(programa) AS programa, MAX(acao) AS acao,
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado
        FROM execucao_orcamentaria
        WHERE grupo IN ('33', '44')
        GROUP BY uo_codigo, uge_codigo, assunto, grupo, programa, acao
        HAVING dotacao > 0 OR empenhado > 0
    """
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql).fetchall()]

    deficit = []
    for r in rows:
        dotacao   = r.get("dotacao")   or 0
        empenhado = r.get("empenhado") or 0
        a_empenhar = dotacao - empenhado
        if a_empenhar < 0:
            r["dotacao"] = dotacao
            r["empenhado"] = empenhado
            r["a_empenhar"] = a_empenhar
            deficit.append(r)

    deficit.sort(key=lambda r: r["a_empenhar"])  # mais negativo primeiro

    deficit_total = sum(-r["a_empenhar"] for r in deficit)
    por_grupo = {"33": 0.0, "44": 0.0}
    uge_acc: dict[str, dict] = {}
    ass_acc: dict[str, float] = {}
    for r in deficit:
        g = r.get("grupo")
        if g in por_grupo:
            por_grupo[g] += -r["a_empenhar"]
        cod = r.get("uge_codigo") or r.get("uo_codigo") or "—"
        u = uge_acc.setdefault(cod, {
            "uge_codigo": cod,
            "uge_nome": r.get("uge_nome") or r.get("uo_nome"),
            "deficit": 0.0,
        })
        if not u["uge_nome"] and (r.get("uge_nome") or r.get("uo_nome")):
            u["uge_nome"] = r.get("uge_nome") or r.get("uo_nome")
        u["deficit"] += -r["a_empenhar"]
        a = r.get("assunto") or "—"
        ass_acc[a] = ass_acc.get(a, 0.0) + -r["a_empenhar"]

    top_uges = sorted(uge_acc.values(), key=lambda x: x["deficit"], reverse=True)[:3]
    top_assuntos = sorted(
        ({"assunto": k, "deficit": v} for k, v in ass_acc.items()),
        key=lambda x: x["deficit"], reverse=True,
    )[:3]

    linhas = [{
        "uo_codigo":  r.get("uo_codigo"),
        "uo_nome":    r.get("uo_nome"),
        "uge_codigo": r.get("uge_codigo"),
        "uge_nome":   r.get("uge_nome"),
        "assunto":    r.get("assunto"),
        "grupo":      r.get("grupo"),
        "programa":   r.get("programa"),
        "acao":       r.get("acao"),
        "dotacao":    r["dotacao"],
        "empenhado":  r["empenhado"],
        "a_empenhar": r["a_empenhar"],
    } for r in deficit[:top_n]]

    return {
        "deficit_total_33_44": deficit_total,
        "n_linhas":            len(deficit),
        "deficit_por_grupo":   por_grupo,
        "top_uges":            top_uges,
        "top_assuntos":        top_assuntos,
        "linhas":              linhas,
    }


# =========================================================================== #
# INTELIGÊNCIA ORÇAMENTÁRIA — Radar de Pressões & Déficits
# Análise de risco preditiva: antecipar pressões/déficits frente a despesas
# novas não previstas na LOA e/ou dotação inicial insuficiente.
# =========================================================================== #

# Data de referência do exercício (usar como "hoje"). Exercício = 2026.
DATA_REF = "2026-06-08"
EXERCICIO = 2026
MESES_DECORRIDOS = int(DATA_REF[5:7])          # 6 (janeiro..junho)
FRACAO_ANO = MESES_DECORRIDOS / 12.0           # ritmo esperado = 0.5

# Limiares de classificação
BANDA_QUADRANTE = 0.15                          # folga/pressão vs FRACAO_ANO
BANDA_RITMO = 0.10                              # acelerado/subexecução global
MES_CRITICO = 9                                 # esgota até setembro
MES_ATENCAO = 12                                # esgota dentro do exercício

_SEVERIDADE_ORDEM = {"critico": 0, "alerta": 1, "info": 2, "ok": 3}


def _exp_where(filtros: dict) -> tuple[str, list]:
    """WHERE clause for the expedientes table (créditos adicionais).

    Espelha _exec_where mas só usa colunas existentes em expedientes
    (classificacao não existe nessa tabela e é ignorada)."""
    clauses, params = [], []
    if filtros.get("uo"):
        clauses.append("uo_codigo = ?")
        params.append(filtros["uo"])
    if filtros.get("programa"):
        clauses.append("programa = ?")
        params.append(filtros["programa"])
    if filtros.get("acao"):
        clauses.append("acao = ?")
        params.append(filtros["acao"])
    if filtros.get("grupo"):
        clauses.append("grupo = ?")
        params.append(filtros["grupo"])
    if filtros.get("elemento"):
        clauses.append("elemento = ?")
        params.append(filtros["elemento"])
    if filtros.get("fonte"):
        clauses.append("fonte = ?")
        params.append(filtros["fonte"])
    if filtros.get("assunto"):
        clauses.append("assunto LIKE ?")
        params.append(f"%{filtros['assunto']}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _linhas_intel(filtros: dict) -> list[dict]:
    """Pivot por linha (uo, assunto, grupo, programa, acao) com os campos
    derivados de risco usados por todas as visões de inteligência.

    Calcula, por linha:
      - dotacao/empenhado/a_empenhar/liquidado/a_liquidar (pivot tabela 10/30/35/40/45)
      - taxa_execucao = empenhado / dotacao
      - burn_mensal   = média dos meses decorridos com empenho>0 (tabela 30);
                        fallback = empenhado / MESES_DECORRIDOS
      - meses_restantes = a_empenhar / burn_mensal
      - mes_esgotamento = MESES_DECORRIDOS + meses_restantes
      - risco: DEFICIT (a_empenhar<0) | CRITICO (<=9) | ATENCAO (<=12) | OK
      - quadrante: PRESSAO | FOLGA | NORMAL
    """
    where, params = _exec_where(filtros)
    meses = [f"mes_{str(i).zfill(2)}" for i in range(1, MESES_DECORRIDOS + 1)]
    emp_parts = [f"SUM(CASE WHEN tabela LIKE '30%' THEN {m} ELSE 0 END) AS emp_{m}" for m in meses]
    emp_sql = (", " + ", ".join(emp_parts)) if emp_parts else ""
    sql = f"""
        SELECT uo_codigo, MAX(uo_nome) AS uo_nome, assunto, grupo,
               MAX(programa) AS programa, MAX(acao) AS acao,
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
               SUM(CASE WHEN tabela LIKE '35%' THEN valor ELSE 0 END) AS a_empenhar,
               SUM(CASE WHEN tabela LIKE '40%' THEN valor ELSE 0 END) AS liquidado,
               SUM(CASE WHEN tabela LIKE '45%' THEN valor ELSE 0 END) AS a_liquidar
               {emp_sql}
        FROM execucao_orcamentaria {where}
        GROUP BY uo_codigo, assunto, grupo, programa, acao
        HAVING dotacao > 0 OR empenhado > 0
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    linhas = []
    for row in rows:
        r = dict(row)
        dotacao    = r.get("dotacao")    or 0
        empenhado  = r.get("empenhado")  or 0
        a_empenhar = r.get("a_empenhar") or 0
        liquidado  = r.get("liquidado")  or 0
        a_liquidar = r.get("a_liquidar") or 0

        meses_vals = [r.get(f"emp_mes_{str(i).zfill(2)}") or 0 for i in range(1, MESES_DECORRIDOS + 1)]
        positivos = [v for v in meses_vals if v > 0]
        if positivos:
            burn = sum(positivos) / len(positivos)
        else:
            burn = (empenhado / MESES_DECORRIDOS) if MESES_DECORRIDOS else 0.0

        taxa = (empenhado / dotacao) if dotacao else 0.0

        if burn > 0:
            meses_restantes = a_empenhar / burn
        else:
            # sem ritmo de empenho: não esgota (saldo positivo) ou já estourou
            meses_restantes = float("inf") if a_empenhar >= 0 else 0.0
        mes_esg = MESES_DECORRIDOS + meses_restantes

        if a_empenhar < 0:
            risco = "DEFICIT"
        elif mes_esg <= MES_CRITICO:
            risco = "CRITICO"
        elif mes_esg <= MES_ATENCAO:
            risco = "ATENCAO"
        else:
            risco = "OK"

        if a_empenhar < 0 or taxa > FRACAO_ANO + BANDA_QUADRANTE:
            quadrante = "PRESSAO"
        elif a_empenhar > 0 and taxa < FRACAO_ANO - BANDA_QUADRANTE:
            quadrante = "FOLGA"
        else:
            quadrante = "NORMAL"

        linhas.append({
            "uo_codigo":       r.get("uo_codigo"),
            "uo_nome":         r.get("uo_nome"),
            "assunto":         r.get("assunto"),
            "grupo":           r.get("grupo"),
            "programa":        r.get("programa"),
            "acao":            r.get("acao"),
            "dotacao":         dotacao,
            "empenhado":       empenhado,
            "a_empenhar":      a_empenhar,
            "liquidado":       liquidado,
            "a_liquidar":      a_liquidar,
            "taxa_execucao":   round(taxa, 4),
            "burn_mensal":     round(burn, 2),
            "meses_restantes": meses_restantes,
            "mes_esgotamento": mes_esg,
            "risco":           risco,
            "quadrante":       quadrante,
        })
    return linhas


def inteligencia_kpis(filtros: dict) -> dict:
    """KPIs de risco consolidados para o cabeçalho da Inteligência."""
    linhas = _linhas_intel(filtros)
    dotacao    = sum(l["dotacao"]    for l in linhas)
    empenhado  = sum(l["empenhado"]  for l in linhas)
    a_empenhar = sum(l["a_empenhar"] for l in linhas)
    liquidado  = sum(l["liquidado"]  for l in linhas)
    a_liquidar = sum(l["a_liquidar"] for l in linhas)
    taxa = (empenhado / dotacao) if dotacao else 0.0
    deficit_total = sum(-l["a_empenhar"] for l in linhas if l["a_empenhar"] < 0)
    return {
        "dotacao":           dotacao,
        "empenhado":         empenhado,
        "a_empenhar":        a_empenhar,
        "liquidado":         liquidado,
        "a_liquidar":        a_liquidar,
        "taxa_execucao":     round(taxa, 4),
        "ritmo_esperado":    round(FRACAO_ANO, 4),
        "gap_ritmo":         round(taxa - FRACAO_ANO, 4),
        "deficit_total":     deficit_total,
        "n_linhas_deficit":  sum(1 for l in linhas if l["risco"] == "DEFICIT"),
        "n_linhas_risco":    sum(1 for l in linhas if l["risco"] in ("CRITICO", "ATENCAO")),
        "n_linhas_folga":    sum(1 for l in linhas if l["quadrante"] == "FOLGA"),
        "folga_remanejavel": sum(l["a_empenhar"] for l in linhas
                                 if l["quadrante"] == "FOLGA" and l["a_empenhar"] > 0),
    }


def projecao_esgotamento(filtros: dict, top_n: int = 20) -> list[dict]:
    """Linhas em risco de esgotamento antecipado do saldo a empenhar.

    Retorna apenas {DEFICIT, CRITICO, ATENCAO} ordenadas por mês de
    esgotamento ascendente (déficits primeiro, pois mes_esgotamento < hoje)."""
    linhas = _linhas_intel(filtros)
    risco = [l for l in linhas if l["risco"] in ("DEFICIT", "CRITICO", "ATENCAO")]
    risco.sort(key=lambda l: l["mes_esgotamento"])
    out = []
    for l in risco[:top_n]:
        mr = l["meses_restantes"]
        out.append({
            "uo_codigo":       l["uo_codigo"],
            "uo_nome":         l["uo_nome"],
            "assunto":         l["assunto"],
            "grupo":           l["grupo"],
            "programa":        l["programa"],
            "acao":            l["acao"],
            "dotacao":         l["dotacao"],
            "empenhado":       l["empenhado"],
            "a_empenhar":      l["a_empenhar"],
            "burn_mensal":     l["burn_mensal"],
            "meses_restantes": round(mr, 1) if mr not in (float("inf"), float("-inf")) else None,
            "mes_esgotamento": round(l["mes_esgotamento"], 1),
            "risco":           l["risco"],
        })
    return out


def ritmo_por_dimensao(filtros: dict, dimensao: str = "uo") -> list[dict]:
    """Mapa de calor de ritmo por categoria de uma dimensão.

    dimensao ∈ {uo, grupo, fonte, classificacao, programa}."""
    col_map = {
        "uo":            "uo_codigo",
        "grupo":         "grupo",
        "fonte":         "fonte",
        "classificacao": "classificacao",
        "programa":      "programa",
    }
    col = col_map.get(dimensao, "uo_codigo")
    where, params = _exec_where(filtros)
    nome_sel = "MAX(uo_nome) AS nome," if col == "uo_codigo" else ""
    sql = f"""
        SELECT {col} AS categoria, {nome_sel}
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
               SUM(CASE WHEN tabela LIKE '35%' THEN valor ELSE 0 END) AS a_empenhar
        FROM execucao_orcamentaria {where}
        GROUP BY {col}
        HAVING dotacao > 0
        ORDER BY dotacao DESC
        LIMIT 20
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        r = dict(row)
        dotacao   = r.get("dotacao")   or 0
        empenhado = r.get("empenhado") or 0
        taxa = (empenhado / dotacao) if dotacao else 0.0
        out.append({
            "categoria":     r.get("categoria") or "—",
            "nome":          r.get("nome"),
            "dotacao":       dotacao,
            "empenhado":     empenhado,
            "a_empenhar":    r.get("a_empenhar") or 0,
            "taxa_execucao": round(taxa, 4),
            "gap_ritmo":     round(taxa - FRACAO_ANO, 4),
        })
    return out


def folga_vs_pressao(filtros: dict) -> dict:
    """Classifica cada linha em PRESSAO / FOLGA / NORMAL e devolve contagem +
    soma por quadrante, top 15 folgas e top 15 pressões, e os pontos do
    gráfico de bolhas (taxa x a_empenhar, raio ~ dotação)."""
    linhas = _linhas_intel(filtros)
    quad = {
        q: {"n": 0, "soma_a_empenhar": 0.0, "soma_dotacao": 0.0}
        for q in ("PRESSAO", "FOLGA", "NORMAL")
    }
    for l in linhas:
        b = quad[l["quadrante"]]
        b["n"] += 1
        b["soma_a_empenhar"] += l["a_empenhar"]
        b["soma_dotacao"] += l["dotacao"]

    folgas = sorted(
        (l for l in linhas if l["quadrante"] == "FOLGA"),
        key=lambda l: l["a_empenhar"], reverse=True,
    )[:15]
    pressoes = sorted(
        (l for l in linhas if l["quadrante"] == "PRESSAO"),
        key=lambda l: l["a_empenhar"],
    )[:15]

    def slim(l):
        return {
            "uo_codigo": l["uo_codigo"], "uo_nome": l["uo_nome"],
            "assunto": l["assunto"], "grupo": l["grupo"],
            "dotacao": l["dotacao"], "empenhado": l["empenhado"],
            "a_empenhar": l["a_empenhar"], "taxa_execucao": l["taxa_execucao"],
        }

    # pontos para o bubble chart (limita aos 150 maiores por dotação)
    bubble = sorted(linhas, key=lambda l: l["dotacao"], reverse=True)[:150]
    pontos = [{
        "x": round(l["taxa_execucao"] * 100, 1),
        "y": l["a_empenhar"],
        "dotacao": l["dotacao"],
        "quadrante": l["quadrante"],
        "assunto": l["assunto"],
        "uo_codigo": l["uo_codigo"],
    } for l in bubble]

    return {
        "quadrantes":  quad,
        "top_folgas":  [slim(l) for l in folgas],
        "top_pressoes": [slim(l) for l in pressoes],
        "pontos":      pontos,
    }


def cobertura_creditos(filtros: dict) -> dict:
    """Resumo dos créditos adicionais (expedientes): suplementação, redução,
    saldo líquido, nº por status e suplementação/redução por grupo (31/33/44)."""
    where, params = _exp_where(filtros)
    with get_conn() as conn:
        tot = conn.execute(
            f"""SELECT COALESCE(SUM(suplementacao),0) AS sup,
                       COALESCE(SUM(reducao),0)       AS red,
                       COUNT(*)                       AS n
                FROM expedientes{where}""",
            params,
        ).fetchone()
        status = conn.execute(
            f"""SELECT status, COUNT(*) AS n
                FROM expedientes{where}
                GROUP BY status ORDER BY n DESC""",
            params,
        ).fetchall()
        grupos = conn.execute(
            f"""SELECT grupo,
                       COALESCE(SUM(suplementacao),0) AS sup,
                       COALESCE(SUM(reducao),0)       AS red
                FROM expedientes{where}
                GROUP BY grupo ORDER BY sup DESC""",
            params,
        ).fetchall()
    sup = tot["sup"] or 0
    red = tot["red"] or 0
    return {
        "suplementacao": sup,
        "reducao":       red,
        "saldo_liquido": sup - red,
        "n_expedientes": tot["n"] or 0,
        "por_status":    [{"status": r["status"] or "—", "n": r["n"]} for r in status],
        "por_grupo":     [{"grupo": r["grupo"] or "—",
                           "suplementacao": r["sup"] or 0,
                           "reducao": r["red"] or 0} for r in grupos],
    }


def inteligencia_insights(filtros: dict) -> list[dict]:
    """Regras de leitura automática do radar. Cada insight:
    {severidade, titulo, texto, valor}. Ordenado por severidade."""
    linhas = _linhas_intel(filtros)
    creditos = cobertura_creditos(filtros)
    insights: list[dict] = []

    def add(sev, titulo, texto, valor=None):
        insights.append({"severidade": sev, "titulo": titulo,
                         "texto": texto, "valor": valor})

    def _rs(v):  # rótulo monetário compacto pt-BR
        n = float(v or 0)
        s = "-" if n < 0 else ""
        n = abs(n)
        if n >= 1e9:  return f"{s}R$ {n/1e9:.2f} bi".replace(".", ",")
        if n >= 1e6:  return f"{s}R$ {n/1e6:.2f} mi".replace(".", ",")
        if n >= 1e3:  return f"{s}R$ {n/1e3:.1f} mil".replace(".", ",")
        return f"{s}R$ {n:,.0f}"

    dotacao   = sum(l["dotacao"]   for l in linhas)
    empenhado = sum(l["empenhado"] for l in linhas)
    taxa = (empenhado / dotacao) if dotacao else 0.0
    gap = taxa - FRACAO_ANO

    # (1) ritmo global vs FRACAO_ANO ± 0,10
    if gap > BANDA_RITMO:
        add("alerta", "Ritmo de execução acelerado",
            f"Empenho em {taxa*100:.0f}% da dotação, acima do ritmo esperado de "
            f"{FRACAO_ANO*100:.0f}% para {MESES_DECORRIDOS} meses decorridos. "
            f"Pressão de esgotamento antecipado.", round(gap, 4))
    elif gap < -BANDA_RITMO:
        add("info", "Subexecução frente ao calendário",
            f"Empenho em {taxa*100:.0f}% da dotação, abaixo do ritmo esperado de "
            f"{FRACAO_ANO*100:.0f}%. Há margem de execução, mas avalie risco de "
            f"contingenciamento.", round(gap, 4))
    else:
        add("ok", "Ritmo de execução equilibrado",
            f"Empenho em {taxa*100:.0f}% da dotação, alinhado ao ritmo esperado de "
            f"{FRACAO_ANO*100:.0f}%.", round(gap, 4))

    # (2) déficit instalado com top 3 linhas
    deficit_lines = sorted((l for l in linhas if l["a_empenhar"] < 0),
                           key=lambda l: l["a_empenhar"])
    deficit_total = sum(-l["a_empenhar"] for l in deficit_lines)
    if deficit_lines:
        top3 = "; ".join(
            f"{(l['assunto'] or '—')[:40]} ({_rs(l['a_empenhar'])})"
            for l in deficit_lines[:3]
        )
        add("critico", f"{len(deficit_lines)} linha(s) em déficit orçamentário",
            f"Déficit instalado de {_rs(deficit_total)} (A Empenhar < 0). "
            f"Maiores: {top3}.", deficit_total)
    else:
        add("ok", "Sem déficits instalados",
            "Nenhuma linha com A Empenhar negativo nos filtros atuais.", 0)

    # (3) linhas CRITICO de esgotamento antecipado
    criticos = sorted((l for l in linhas if l["risco"] == "CRITICO"),
                      key=lambda l: l["mes_esgotamento"])
    if criticos:
        nomes = [f"{(l['assunto'] or '—')[:35]} (mês {l['mes_esgotamento']:.0f})"
                 for l in criticos[:5]]
        extra = f" e mais {len(criticos) - 5}" if len(criticos) > 5 else ""
        add("alerta", f"{len(criticos)} linha(s) com esgotamento até setembro",
            f"Saldo a empenhar projetado para acabar antes do mês {MES_CRITICO}: "
            f"{'; '.join(nomes)}{extra}.", len(criticos))

    # (4) concentração: top 5 linhas > 50% do a_empenhar negativo
    if deficit_total > 0:
        top5 = sum(-l["a_empenhar"] for l in deficit_lines[:5])
        share = top5 / deficit_total
        if share > 0.50:
            add("info", "Risco concentrado em poucas linhas",
                f"As 5 maiores linhas concentram {share*100:.0f}% do déficit total "
                f"({_rs(top5)} de {_rs(deficit_total)}). Ação focada resolve a maior parte.",
                round(share, 4))

    # (5) folga remanejável com top 3
    folgas = sorted((l for l in linhas
                     if l["quadrante"] == "FOLGA" and l["a_empenhar"] > 0),
                    key=lambda l: l["a_empenhar"], reverse=True)
    folga_total = sum(l["a_empenhar"] for l in folgas)
    if folga_total > 0:
        top3 = "; ".join(
            f"{(l['assunto'] or '—')[:40]} ({_rs(l['a_empenhar'])})"
            for l in folgas[:3]
        )
        add("info", "Folga remanejável disponível",
            f"{_rs(folga_total)} em linhas subexecutadas que podem cobrir pressões. "
            f"Maiores: {top3}.", folga_total)

    # (6) déficit > saldo de créditos → exige nova fonte
    saldo_cred = creditos["saldo_liquido"]
    if deficit_total > 0 and deficit_total > saldo_cred:
        add("critico", "Déficit supera saldo de créditos — exige nova fonte",
            f"Déficit de {_rs(deficit_total)} é maior que o saldo líquido de créditos "
            f"adicionais ({_rs(saldo_cred)}). Faltam {_rs(deficit_total - saldo_cred)} "
            f"sem cobertura por remanejamento já formalizado.", deficit_total - saldo_cred)

    # (7) grupo com maior gap de ritmo
    grupos = ritmo_por_dimensao(filtros, "grupo")
    if grupos:
        pior = max(grupos, key=lambda g: g["gap_ritmo"])
        if pior["gap_ritmo"] > BANDA_RITMO:
            add("info", f"Grupo {pior['categoria']} com maior descompasso de ritmo",
                f"Execução de {pior['taxa_execucao']*100:.0f}% vs esperado "
                f"{FRACAO_ANO*100:.0f}% (gap +{pior['gap_ritmo']*100:.0f} p.p.).",
                round(pior["gap_ritmo"], 4))

    insights.sort(key=lambda i: _SEVERIDADE_ORDEM.get(i["severidade"], 9))
    return insights


def simular_cenario(filtros: dict, valor_novo: float,
                    grupo: str | None = None, fonte: str | None = None,
                    uo: str | None = None) -> dict:
    """Simula uma despesa nova não prevista dentro de um escopo e avalia se a
    folga remanejável a cobre.

    folga_disponivel = Σ a_empenhar positivo das linhas FOLGA do escopo;
    cobertura = min(valor_novo, folga_disponivel);
    gap_descoberto = max(0, valor_novo - folga_disponivel)."""
    valor_novo = float(valor_novo or 0)
    escopo = dict(filtros)
    if grupo:
        escopo["grupo"] = grupo
    if fonte:
        escopo["fonte"] = fonte
    if uo:
        escopo["uo"] = uo

    linhas = _linhas_intel(escopo)
    folgas = sorted((l for l in linhas
                     if l["quadrante"] == "FOLGA" and l["a_empenhar"] > 0),
                    key=lambda l: l["a_empenhar"], reverse=True)
    folga_disponivel = sum(l["a_empenhar"] for l in folgas)
    cobertura = min(valor_novo, folga_disponivel)
    gap_descoberto = max(0.0, valor_novo - folga_disponivel)

    # candidatas a remanejamento até cobrir valor_novo
    candidatas, acumulado = [], 0.0
    for l in folgas:
        if acumulado >= valor_novo:
            break
        usar = min(l["a_empenhar"], valor_novo - acumulado)
        acumulado += usar
        candidatas.append({
            "uo_codigo":   l["uo_codigo"],
            "uo_nome":     l["uo_nome"],
            "assunto":     l["assunto"],
            "grupo":       l["grupo"],
            "a_empenhar":  l["a_empenhar"],
            "remanejar":   usar,
        })

    dotacao_escopo   = sum(l["dotacao"]   for l in linhas)
    empenhado_escopo = sum(l["empenhado"] for l in linhas)
    nova_taxa = ((empenhado_escopo + valor_novo) / dotacao_escopo) if dotacao_escopo else 0.0

    if valor_novo <= 0:
        veredito = "Informe um valor de despesa nova para simular."
    elif gap_descoberto <= 0:
        veredito = (f"Despesa de {_fmt_brl(valor_novo)} é integralmente absorvível "
                    f"pela folga remanejável do escopo ({_fmt_brl(folga_disponivel)} "
                    f"disponíveis) usando {len(candidatas)} linha(s). Sem necessidade "
                    f"de nova fonte.")
    else:
        veredito = (f"Folga remanejável de {_fmt_brl(folga_disponivel)} cobre apenas "
                    f"{_fmt_brl(cobertura)}. Faltam {_fmt_brl(gap_descoberto)} que exigem "
                    f"crédito adicional / nova fonte de recursos.")

    return {
        "valor_novo":       valor_novo,
        "escopo":           {"grupo": grupo or filtros.get("grupo"),
                             "fonte": fonte or filtros.get("fonte"),
                             "uo": uo or filtros.get("uo")},
        "folga_disponivel": folga_disponivel,
        "cobertura":        cobertura,
        "gap_descoberto":   gap_descoberto,
        "coberto":          gap_descoberto <= 0,
        "n_candidatas":     len(candidatas),
        "candidatas":       candidatas,
        "dotacao_escopo":   dotacao_escopo,
        "empenhado_escopo": empenhado_escopo,
        "nova_taxa_execucao": round(nova_taxa, 4),
        "veredito":         veredito,
    }


def _fmt_brl(v) -> str:
    """R$ 1.234.567,89 — formato pt-BR para textos do backend."""
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =========================================================================== #
# PRESSÃO ORÇAMENTÁRIA — Necessidade Atualizada × Dotação Atual
# Cruza a tabela `necessidade` (por UGE e assunto planejado) com o pivot de
# `execucao_orcamentaria` para projetar a pressão dotacional.
# Casamento no grão (uge_codigo, id_assunto_planejado) — fallback assunto.
# =========================================================================== #

# tolerância relativa para classificar uma linha como EQUILIBRIO
BANDA_EQUILIBRIO = 0.01


def pressao_filtros_disponiveis() -> dict:
    """Filtros da tela de Pressão: os mesmos da execução + lista de UGEs
    (de execucao_orcamentaria e da tabela necessidade)."""
    base = execucao_filtros_disponiveis()
    with get_conn() as conn:
        uges = conn.execute(
            """
            SELECT uge_codigo,
                   (SELECT uge_nome FROM execucao_orcamentaria e2
                     WHERE e2.uge_codigo = e1.uge_codigo AND e2.uge_nome IS NOT NULL
                     GROUP BY uge_nome ORDER BY COUNT(*) DESC LIMIT 1) AS uge_nome
              FROM execucao_orcamentaria e1
             WHERE uge_codigo IS NOT NULL
             GROUP BY uge_codigo ORDER BY uge_codigo
            """
        ).fetchall()
    base["uges"] = [{"codigo": r["uge_codigo"], "nome": r["uge_nome"] or r["uge_codigo"]} for r in uges]
    return base


def _press_exec_where(filtros: dict) -> tuple[str, list]:
    """WHERE sobre execucao_orcamentaria, incluindo UGE."""
    clauses, params = [], []
    pares = [
        ("uo", "uo_codigo"), ("uge", "uge_codigo"), ("programa", "programa"),
        ("acao", "acao"), ("grupo", "grupo"), ("elemento", "elemento"),
        ("fonte", "fonte"), ("classificacao", "classificacao"),
    ]
    for chave, col in pares:
        if filtros.get(chave):
            clauses.append(f"{col} = ?")
            params.append(filtros[chave])
    if filtros.get("assunto"):
        clauses.append("assunto LIKE ?")
        params.append(f"%{filtros['assunto']}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _press_nec_where(filtros: dict) -> tuple[str, list]:
    """WHERE sobre a tabela necessidade (classificacao não existe — ignorada)."""
    clauses, params = [], []
    pares = [
        ("uo", "uo_codigo"), ("uge", "uge_codigo"), ("programa", "programa"),
        ("acao", "acao"), ("grupo", "grupo"), ("elemento", "elemento"),
        ("fonte", "fonte"),
    ]
    for chave, col in pares:
        if filtros.get(chave):
            clauses.append(f"{col} = ?")
            params.append(filtros[chave])
    if filtros.get("assunto"):
        clauses.append("assunto LIKE ?")
        params.append(f"%{filtros['assunto']}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _press_key(uge_codigo, id_assunto, assunto) -> tuple:
    """Chave de casamento: (uge, id_assunto) ou fallback (uge, ASSUNTO)."""
    if id_assunto:
        return (uge_codigo or "", "ID:" + str(id_assunto))
    return (uge_codigo or "", "AS:" + (assunto or "").upper())


def _pressao_linhas(filtros: dict) -> list[dict]:
    """Une necessidade × dotação atual por (uge, assunto planejado) e calcula
    pressão, cobertura e situação por linha."""
    # ── lado execução (dotação atual / empenhado / a empenhar) ──
    ex_where, ex_params = _press_exec_where(filtros)
    ex_sql = f"""
        SELECT uo_codigo, MAX(uo_nome) AS uo_nome,
               uge_codigo, MAX(uge_nome) AS uge_nome,
               id_assunto_planejado, assunto,
               MAX(programa) AS programa, MAX(acao) AS acao,
               MAX(grupo) AS grupo, MAX(elemento) AS elemento,
               MAX(fonte) AS fonte, MAX(classificacao) AS classificacao,
               SUM(CASE WHEN tabela LIKE '10%' THEN valor ELSE 0 END) AS dotacao,
               SUM(CASE WHEN tabela LIKE '30%' THEN valor ELSE 0 END) AS empenhado,
               SUM(CASE WHEN tabela LIKE '40%' THEN valor ELSE 0 END) AS liquidado,
               SUM(CASE WHEN tabela LIKE '35%' THEN valor ELSE 0 END) AS a_empenhar_plan,
               SUM(CASE WHEN tabela LIKE '45%' THEN valor ELSE 0 END) AS a_liquidar_plan
        FROM execucao_orcamentaria {ex_where}
        GROUP BY uge_codigo, id_assunto_planejado, assunto
        HAVING dotacao > 0 OR empenhado > 0
    """
    # ── lado necessidade ──
    nc_where, nc_params = _press_nec_where(filtros)
    nc_sql = f"""
        SELECT uo_codigo, MAX(uo_nome) AS uo_nome,
               uge_codigo, MAX(uge_nome) AS uge_nome,
               id_assunto_planejado, assunto,
               MAX(programa) AS programa, MAX(acao) AS acao,
               MAX(grupo) AS grupo, MAX(elemento) AS elemento, MAX(fonte) AS fonte,
               SUM(necessidade_atualizada) AS necessidade
        FROM necessidade {nc_where}
        GROUP BY uge_codigo, id_assunto_planejado, assunto
        HAVING necessidade <> 0
    """

    with get_conn() as conn:
        ex_rows = [dict(r) for r in conn.execute(ex_sql, ex_params).fetchall()]
        nc_rows = [dict(r) for r in conn.execute(nc_sql, nc_params).fetchall()]

    linhas: dict[tuple, dict] = {}

    def base(r):
        return {
            "uo_codigo":  r.get("uo_codigo"), "uo_nome":  r.get("uo_nome"),
            "uge_codigo": r.get("uge_codigo"), "uge_nome": r.get("uge_nome"),
            "id_assunto_planejado": r.get("id_assunto_planejado"),
            "assunto":    r.get("assunto"),
            "programa":   r.get("programa"), "acao": r.get("acao"),
            "grupo":      r.get("grupo"), "elemento": r.get("elemento"),
            "fonte":      r.get("fonte"), "classificacao": r.get("classificacao"),
            "necessidade": 0.0, "dotacao": 0.0, "empenhado": 0.0, "liquidado": 0.0,
            # valores que a planilha já traz (tabela 35/45) — exibidos junto
            # aos derivados para checagem de coerência
            "a_empenhar_plan": 0.0, "a_liquidar_plan": 0.0,
        }

    for r in ex_rows:
        k = _press_key(r.get("uge_codigo"), r.get("id_assunto_planejado"), r.get("assunto"))
        item = linhas.setdefault(k, base(r))
        item["dotacao"]         += r.get("dotacao")         or 0
        item["empenhado"]       += r.get("empenhado")       or 0
        item["liquidado"]       += r.get("liquidado")       or 0
        item["a_empenhar_plan"] += r.get("a_empenhar_plan") or 0
        item["a_liquidar_plan"] += r.get("a_liquidar_plan") or 0

    for r in nc_rows:
        k = _press_key(r.get("uge_codigo"), r.get("id_assunto_planejado"), r.get("assunto"))
        item = linhas.get(k)
        if item is None:
            item = base(r)
            linhas[k] = item
        else:
            # completa campos de exibição ausentes a partir da necessidade
            for campo in ("uo_codigo", "uo_nome", "uge_nome", "programa", "acao",
                          "grupo", "elemento", "fonte", "assunto"):
                if not item.get(campo) and r.get(campo):
                    item[campo] = r.get(campo)
        item["necessidade"] += r.get("necessidade") or 0

    out = []
    for item in linhas.values():
        nec = item["necessidade"]
        dot = item["dotacao"]
        emp = item["empenhado"]
        liq = item["liquidado"]
        # derivados (definição do glossário): a_empenhar = dotacao − empenhado;
        # a_liquidar = empenhado − liquidado. São os valores primários exibidos.
        a_empenhar = dot - emp
        a_liquidar = emp - liq
        item["a_empenhar"] = a_empenhar
        item["a_liquidar"] = a_liquidar
        # divergência entre o derivado e o que a planilha trouxe (35/45)
        tol = max(1.0, 0.005 * max(abs(dot), abs(emp), 1.0))
        item["divergencia"] = (
            abs(a_empenhar - item["a_empenhar_plan"]) > tol
            or abs(a_liquidar - item["a_liquidar_plan"]) > tol
        )

        pressao = nec - dot
        banda = BANDA_EQUILIBRIO * max(abs(nec), abs(dot), 1.0)
        if pressao > banda:
            situacao = "DEFICIT" if a_empenhar < 0 else "PRESSAO"
        elif pressao < -banda:
            situacao = "FOLGA"
        else:
            situacao = "EQUILIBRIO"
        item["pressao"] = pressao
        item["pressao_pos"] = max(0.0, pressao)
        item["cobertura"] = round(dot / nec, 4) if nec > 0 else None
        item["situacao"] = situacao
        out.append(item)

    out.sort(key=lambda l: l["pressao"], reverse=True)
    return out


def pressao_kpis(filtros: dict) -> dict:
    linhas = _pressao_linhas(filtros)
    dotacao_atual    = sum(l["dotacao"]     for l in linhas)
    empenhado        = sum(l["empenhado"]   for l in linhas)
    a_empenhar       = sum(l["a_empenhar"]  for l in linhas)
    a_liquidar       = sum(l["a_liquidar"]  for l in linhas)
    necessidade_total = sum(l["necessidade"] for l in linhas)
    pressao_total    = sum(l["pressao_pos"] for l in linhas)
    return {
        "dotacao_atual":      dotacao_atual,
        "empenhado":          empenhado,
        "a_empenhar":         a_empenhar,
        "a_liquidar":         a_liquidar,
        "necessidade_total":  necessidade_total,
        "pressao_total":      pressao_total,
        "deficit_dotacional": necessidade_total - dotacao_atual,
        "cobertura_media":    round(dotacao_atual / necessidade_total, 4) if necessidade_total > 0 else None,
        "n_linhas_pressao":   sum(1 for l in linhas if l["necessidade"] > l["dotacao"]),
        "n_linhas_folga":     sum(1 for l in linhas if l["dotacao"] > l["necessidade"]),
    }


def pressao_por_linha(filtros: dict) -> list[dict]:
    """Linhas necessidade × dotação, ordenadas por pressão desc."""
    return _pressao_linhas(filtros)


def pressao_por_uge(filtros: dict) -> list[dict]:
    """Agrega necessidade, dotação, pressão e cobertura por UGE."""
    linhas = _pressao_linhas(filtros)
    uges: dict[str, dict] = {}
    for l in linhas:
        cod = l["uge_codigo"] or "—"
        u = uges.setdefault(cod, {
            "uge_codigo": cod, "uge_nome": l["uge_nome"],
            "necessidade": 0.0, "dotacao_atual": 0.0,
            "empenhado": 0.0, "a_empenhar": 0.0, "pressao": 0.0,
        })
        if not u["uge_nome"] and l["uge_nome"]:
            u["uge_nome"] = l["uge_nome"]
        u["necessidade"]   += l["necessidade"]
        u["dotacao_atual"] += l["dotacao"]
        u["empenhado"]     += l["empenhado"]
        u["a_empenhar"]    += l["a_empenhar"]
        u["pressao"]       += l["pressao_pos"]
    out = list(uges.values())
    for u in out:
        u["cobertura"] = round(u["dotacao_atual"] / u["necessidade"], 4) if u["necessidade"] > 0 else None
    out.sort(key=lambda u: u["pressao"], reverse=True)
    return out


def pressao_por_dimensao(filtros: dict, dimensao: str = "grupo") -> list[dict]:
    """Necessidade vs dotação vs pressão por categoria de uma dimensão.
    dimensao ∈ {grupo, fonte, programa, classificacao}."""
    campo = dimensao if dimensao in ("grupo", "fonte", "programa", "classificacao") else "grupo"
    linhas = _pressao_linhas(filtros)
    cats: dict[str, dict] = {}
    for l in linhas:
        cat = l.get(campo) or "—"
        c = cats.setdefault(cat, {
            "categoria": cat, "necessidade": 0.0,
            "dotacao_atual": 0.0, "pressao": 0.0,
        })
        c["necessidade"]   += l["necessidade"]
        c["dotacao_atual"] += l["dotacao"]
        c["pressao"]       += l["pressao_pos"]
    out = list(cats.values())
    for c in out:
        c["cobertura"] = round(c["dotacao_atual"] / c["necessidade"], 4) if c["necessidade"] > 0 else None
    out.sort(key=lambda c: c["pressao"], reverse=True)
    return out


def pressao_insights(filtros: dict) -> list[dict]:
    linhas = _pressao_linhas(filtros)
    insights: list[dict] = []

    def add(sev, titulo, texto, valor=None):
        insights.append({"severidade": sev, "titulo": titulo,
                         "texto": texto, "valor": valor})

    necessidade_total = sum(l["necessidade"] for l in linhas)
    dotacao_atual     = sum(l["dotacao"]     for l in linhas)
    pressao_total     = sum(l["pressao_pos"] for l in linhas)
    linhas_pressao    = [l for l in linhas if l["pressao"] > 0]
    cobertura_media   = (dotacao_atual / necessidade_total) if necessidade_total > 0 else None

    # (1) pressão total e nº de linhas
    if pressao_total > 0:
        add("alerta", f"Pressão de {_fmt_brl(pressao_total)} sobre a dotação atual",
            f"{len(linhas_pressao)} linha(s) com necessidade acima da dotação atual. "
            f"Necessidade total {_fmt_brl(necessidade_total)} vs dotação {_fmt_brl(dotacao_atual)}.",
            pressao_total)
    else:
        add("ok", "Sem pressão dotacional",
            "Nenhuma linha com necessidade acima da dotação atual nos filtros.", 0)

    # (2) top 3 UGEs com maior pressão
    uges = pressao_por_uge(filtros)
    top_uges = [u for u in uges if u["pressao"] > 0][:3]
    if top_uges:
        txt = "; ".join(
            f"{(u['uge_nome'] or u['uge_codigo'] or '—')[:35]} ({_fmt_brl(u['pressao'])})"
            for u in top_uges)
        add("alerta", "UGEs com maior pressão",
            f"Concentram a maior necessidade descoberta: {txt}.", top_uges[0]["pressao"])

    # (3) top 5 assuntos descobertos
    top_ass = sorted(linhas_pressao, key=lambda l: l["pressao"], reverse=True)[:5]
    if top_ass:
        txt = "; ".join(
            f"{(l['assunto'] or '—')[:35]} ({_fmt_brl(l['pressao'])})" for l in top_ass)
        add("info", "Principais despesas descobertas", f"{txt}.", top_ass[0]["pressao"])

    # (4) cobertura média global
    if cobertura_media is not None:
        if cobertura_media >= 1.0:
            add("ok", "Dotação cobre a necessidade total",
                f"Cobertura média de {cobertura_media*100:.0f}% da necessidade atualizada.",
                round(cobertura_media, 4))
        elif cobertura_media >= 0.70:
            add("alerta", "Cobertura parcial da necessidade",
                f"Dotação atual cobre {cobertura_media*100:.0f}% da necessidade atualizada.",
                round(cobertura_media, 4))
        else:
            add("critico", "Cobertura crítica da necessidade",
                f"Dotação atual cobre apenas {cobertura_media*100:.0f}% da necessidade atualizada.",
                round(cobertura_media, 4))

    # (5) linhas em DEFICIT — necessidade não cabe nem no que resta a empenhar
    deficit = [l for l in linhas if l["situacao"] == "DEFICIT"]
    if deficit:
        soma = sum(l["pressao_pos"] for l in deficit)
        add("critico", f"{len(deficit)} linha(s) em déficit com saldo esgotado",
            f"Necessidade acima da dotação E A Empenhar negativo: a necessidade não cabe "
            f"nem no que resta a empenhar. Pressão sem saldo de {_fmt_brl(soma)}.", soma)

    # (6) folgas que podem compensar — só folgas com saldo a empenhar > 0
    folgas = [l for l in linhas if l["situacao"] == "FOLGA" and l["a_empenhar"] > 0]
    folga_total = sum(-l["pressao"] for l in folgas)  # pressao<0 → módulo
    if folga_total > 0:
        cobre = min(folga_total, pressao_total)
        add("info", "Folga dotacional remanejável",
            f"{_fmt_brl(folga_total)} em linhas com dotação acima da necessidade e ainda "
            f"com saldo a empenhar ({len(folgas)} linha(s)) — cobre até {_fmt_brl(cobre)} "
            f"da pressão.", folga_total)

    insights.sort(key=lambda i: _SEVERIDADE_ORDEM.get(i["severidade"], 9))
    return insights


