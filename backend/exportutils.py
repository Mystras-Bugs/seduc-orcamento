"""Helpers únicos de exportação (CSV/PDF) compartilhados por app.py e
pdf_jornal.py — garantem que telas e arquivos usem a MESMA formatação pt-BR,
a MESMA marcação de déficit e a MESMA paleta visual.

Padrões:
- CSV: UTF-8 com BOM (abre certo no Excel pt-BR), delimitador ';', números com
  vírgula decimal.
- PDF (ReportLab): cabeçalho escuro com texto branco, zebra cinza suave, grade
  discreta, déficit em vermelho discreto, números alinhados à direita.
"""
from __future__ import annotations

import csv
import io

from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.platypus import TableStyle

# --------------------------------------------------------------------------- #
# Paleta única (espelha o redesign de identity.css) — coerência tela ↔ PDF
# --------------------------------------------------------------------------- #
PDF_INK     = colors.HexColor("#15181F")   # cabeçalho de tabela
PDF_WHITE   = colors.white
PDF_ZEBRA   = colors.HexColor("#F4F5F7")   # linha alternada
PDF_LINE    = colors.HexColor("#D9DCE2")   # grade discreta
PDF_RED     = colors.HexColor("#C8101A")   # acento / déficit
PDF_DEF_BG  = colors.HexColor("#FBE3E4")   # fundo discreto de déficit
PDF_DEF_TXT = colors.HexColor("#A10009")   # texto de déficit
PDF_MUTE    = colors.HexColor("#4E5663")

# BOM UTF-8 — prefixo que faz o Excel pt-BR ler acentos corretamente
_BOM = "﻿"


# --------------------------------------------------------------------------- #
# Formatação pt-BR
# --------------------------------------------------------------------------- #
def brl(v) -> str:
    """R$ 1.234.567,89 (pt-BR), com sinal negativo visível em déficit."""
    n = float(v or 0)
    s = f"R$ {n:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl_compacta(v) -> str:
    """R$ 1,23 bi / 4,56 mi / 7,8 mil — rótulo curto pt-BR."""
    n = float(v or 0)
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1e9:  return f"{sign}R$ {a/1e9:.2f} bi".replace(".", ",")
    if a >= 1e6:  return f"{sign}R$ {a/1e6:.2f} mi".replace(".", ",")
    if a >= 1e3:  return f"{sign}R$ {a/1e3:.1f} mil".replace(".", ",")
    return f"{sign}R$ {a:,.0f}".replace(",", ".")


def csv_num(v) -> str:
    """Número pt-BR para CSV/Excel: vírgula decimal, sem separador de milhar."""
    return f"{float(v or 0):.2f}".replace(".", ",")


def csv_pct(v) -> str:
    """Percentual pt-BR (recebe fração 0..1) -> '83,5'. Vazio se None."""
    if v is None:
        return ""
    return f"{float(v) * 100:.1f}".replace(".", ",")


# --------------------------------------------------------------------------- #
# Resposta CSV padronizada (BOM + ';')
# --------------------------------------------------------------------------- #
def csv_response(filename: str, header: list, rows) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --------------------------------------------------------------------------- #
# Estilo de tabela PDF padronizado
# --------------------------------------------------------------------------- #
def pdf_table_style(align_right_from: int = 3) -> TableStyle:
    """TableStyle base: cabeçalho escuro, zebra, grade fina, números à direita
    a partir da coluna ``align_right_from``."""
    return TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), PDF_INK),
        ("TEXTCOLOR",      (0, 0), (-1, 0), PDF_WHITE),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 7),
        ("GRID",           (0, 0), (-1, -1), 0.25, PDF_LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PDF_WHITE, PDF_ZEBRA]),
        ("ALIGN",          (align_right_from, 1), (-1, -1), "RIGHT"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
    ])


def mark_deficit(style: TableStyle, row_idx: int, valor_col: int) -> None:
    """Realça uma linha de déficit: fundo vermelho discreto e valor em negrito."""
    style.add("BACKGROUND", (0, row_idx), (-1, row_idx), PDF_DEF_BG)
    style.add("TEXTCOLOR", (valor_col, row_idx), (valor_col, row_idx), PDF_DEF_TXT)
    style.add("FONTNAME", (valor_col, row_idx), (valor_col, row_idx), "Helvetica-Bold")
