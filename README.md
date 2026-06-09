# SEDUC · Sistema de Monitoramento Orçamentário

Sistema web para a equipe de orçamento da Secretaria da Educação do Estado de
São Paulo. Dois eixos:

- **Jornal do Dia** — comunicação editorial com manchete, timeline, KPIs e
  radar de déficits.
- **Painel Gerencial / BI** — filtros dinâmicos, gráficos interativos e
  relatório de execução orçamentária com alertas visuais.

A identidade visual segue o **Manual de Identidade Visual do Governo do Estado
de São Paulo (GESP) v1.12 — JUN 2023**: paleta principal vermelho `#FF161F`,
amarelo `#FBB900` e azul `#034EA2`; tipografia **Montserrat** (secundária do
manual, escolhida como fonte web por ser open-source) com Verdana como
fallback de sistema.

---

## Como executar (Windows)

```bat
cd sistema_orcamento
run.bat
```

Ou manualmente:

```bat
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Abra <http://127.0.0.1:8000>.

### Importando dados

1. Acesse **Importar Dados** no topo da página.
2. Arraste a planilha `Expedientes Consolidados - Reduções e Suplementações
   2026.xlsx` (ou clique para escolher).
3. O ETL substitui a base anterior e exibe um resumo com período e totais.

---

## Estrutura do projeto

```
sistema_orcamento/
├── backend/
│   ├── app.py          # FastAPI + rotas REST e páginas
│   ├── database.py     # SQLite + schema
│   ├── etl.py          # Importação .xlsx
│   ├── queries.py      # Consultas dos painéis
│   └── requirements.txt
├── static/
│   ├── css/identity.css   # Variáveis e tokens da identidade GESP
│   ├── css/styles.css     # Componentes e layout
│   └── js/{common,jornal,painel}.js
├── templates/
│   ├── base.html  jornal.html  painel.html  admin.html
├── data/orcamento.db   # criado automaticamente
└── run.bat
```

## Endpoints REST

| Método | URL                              | Descrição                                |
|-------:|----------------------------------|------------------------------------------|
| GET    | `/api/metricas`                  | KPIs consolidados (com filtros)          |
| GET    | `/api/jornal`                    | Manchete + timeline                      |
| GET    | `/api/filtros`                   | Listas para selects do Painel            |
| GET    | `/api/distribuicao-uo`           | Suplementação/Redução por UO             |
| GET    | `/api/distribuicao-grupo`        | Donut por Grupo de Despesa               |
| GET    | `/api/serie-mensal`              | Tendência mensal (mês e acumulado)       |
| GET    | `/api/status-funil`              | Contagem por status                      |
| GET    | `/api/execucao`                  | Tabela de execução com cálculos          |
| GET    | `/api/alertas`                   | Top déficits (Valor a Empenhar < 0)      |
| GET    | `/api/export/execucao.csv`       | Exporta CSV da tabela                    |
| GET    | `/api/export/execucao.pdf`       | Exporta PDF estilizado                   |
| POST   | `/api/importar`                  | Upload da planilha `.xlsx`               |

Todos os endpoints de leitura aceitam os mesmos filtros (query string):
`uo, programa, acao, grupo, elemento, fonte, assunto, status, data_inicio,
data_fim`.

## Regras de cálculo

Conforme planejamento estratégico:

```
Valor a Liquidar = Valor Empenhado - Valor Liquidado
Valor a Empenhar = Dotação - Valor Reservado - Valor Empenhado
```

Linhas onde **Valor a Empenhar < 0** são marcadas em vermelho (déficit) tanto
na UI quanto no PDF.
