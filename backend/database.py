"""SQLite schema and connection helper for the SEDUC budget monitor."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "orcamento.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT,
    expediente      TEXT,
    data_envio      TEXT,
    data_conclusao  TEXT,
    assunto         TEXT,
    uo_codigo       TEXT,
    uo_nome         TEXT,
    programa        TEXT,
    acao            TEXT,
    grupo           TEXT,
    elemento        TEXT,
    fonte           TEXT,
    reducao         REAL DEFAULT 0,
    suplementacao   REAL DEFAULT 0,
    descricao       TEXT,
    valor_minutado  REAL,
    janeiro REAL, fevereiro REAL, marco REAL, abril REAL,
    maio REAL, junho REAL, julho REAL, agosto REAL,
    setembro REAL, outubro REAL, novembro REAL, dezembro REAL,
    status          TEXT,
    importado_em    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exp_uo       ON expedientes (uo_codigo);
CREATE INDEX IF NOT EXISTS idx_exp_data     ON expedientes (data_conclusao);
CREATE INDEX IF NOT EXISTS idx_exp_tipo     ON expedientes (tipo);
CREATE INDEX IF NOT EXISTS idx_exp_assunto  ON expedientes (assunto);

CREATE TABLE IF NOT EXISTS execucao_orcamentaria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uo_codigo              TEXT,
    uo_nome                TEXT,
    uge_codigo             TEXT,
    uge_nome               TEXT,
    funcao_codigo          TEXT,
    funcao_nome            TEXT,
    subfuncao_codigo       TEXT,
    subfuncao_nome         TEXT,
    programa               TEXT,
    programa_nome          TEXT,
    acao                   TEXT,
    acao_codigo            TEXT,
    acao_nome              TEXT,
    fonte                  TEXT,
    fonte_nome             TEXT,
    grupo                  TEXT,
    grupo_nome             TEXT,
    elemento               TEXT,
    elemento_nome          TEXT,
    id_assunto_planejado   TEXT,
    assunto                TEXT, -- ASSUNTO_PLANEJADO
    classificacao          TEXT,
    vinculacao             TEXT,
    pode_ser_fundeb        TEXT,
    tabela                 TEXT,
    valor                  REAL DEFAULT 0,
    mes_01 REAL, mes_02 REAL, mes_03 REAL, mes_04 REAL,
    mes_05 REAL, mes_06 REAL, mes_07 REAL, mes_08 REAL,
    mes_09 REAL, mes_10 REAL, mes_11 REAL, mes_12 REAL,
    importado_em           TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exec_uo ON execucao_orcamentaria (uo_codigo);
CREATE INDEX IF NOT EXISTS idx_exec_prog ON execucao_orcamentaria (programa);
CREATE INDEX IF NOT EXISTS idx_exec_acao ON execucao_orcamentaria (acao);
CREATE INDEX IF NOT EXISTS idx_exec_grupo ON execucao_orcamentaria (grupo);
CREATE INDEX IF NOT EXISTS idx_exec_fonte ON execucao_orcamentaria (fonte);
CREATE INDEX IF NOT EXISTS idx_exec_assunto ON execucao_orcamentaria (assunto);

CREATE TABLE IF NOT EXISTS necessidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uge_codigo             TEXT,
    uge_nome               TEXT,
    uo_codigo              TEXT,
    uo_nome                TEXT,
    programa               TEXT,
    acao                   TEXT,
    grupo                  TEXT,
    elemento               TEXT,
    fonte                  TEXT,
    id_assunto_planejado   TEXT,
    assunto                TEXT,
    necessidade_atualizada REAL DEFAULT 0,
    observacao             TEXT,
    importado_em           TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nec_uge     ON necessidade (uge_codigo);
CREATE INDEX IF NOT EXISTS idx_nec_uo      ON necessidade (uo_codigo);
CREATE INDEX IF NOT EXISTS idx_nec_assunto ON necessidade (assunto);

CREATE TABLE IF NOT EXISTS importacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo       TEXT,
    linhas        INTEGER,
    importado_em  TEXT DEFAULT CURRENT_TIMESTAMP,
    observacao    TEXT
);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
