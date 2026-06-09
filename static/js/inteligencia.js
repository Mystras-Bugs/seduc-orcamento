/* inteligencia.js – Radar de Pressões & Déficits
   Usa helpers globais de common.js: api, moeda/moedaCompleta/moedaCompacta, GESP, PALETTE. */

const intelCharts = {};
const RISCO_COR = { DEFICIT: '#7a0010', CRITICO: GESP.red, ATENCAO: GESP.yellow, OK: GESP.green };
const QUAD_COR  = { PRESSAO: GESP.red, FOLGA: GESP.green, NORMAL: GESP.skyMid };

// ── helpers ────────────────────────────────────────────────────────────────
function getIntelFiltros() {
    return {
        uo:            document.getElementById('if-uo').value,
        programa:      document.getElementById('if-programa').value,
        acao:          document.getElementById('if-acao').value,
        grupo:         document.getElementById('if-grupo').value,
        elemento:      document.getElementById('if-elemento').value,
        fonte:         document.getElementById('if-fonte').value,
        classificacao: document.getElementById('if-classificacao').value,
        assunto:       document.getElementById('if-assunto').value.trim(),
    };
}

function resumoFiltrosIntel(f) {
    const partes = [];
    Object.entries(f).forEach(([k, v]) => { if (v) partes.push(`${k}=${v}`); });
    return partes.length ? `Aplicados: ${partes.join(' · ')}` : 'Sem filtros aplicados.';
}

function populateSelectIntel(id, items, mapper) {
    const el = document.getElementById(id);
    if (!el) return;
    const cur = el.value;
    el.innerHTML = el.options[0].outerHTML;
    items.forEach(it => {
        const opt = document.createElement('option');
        if (mapper) { opt.value = mapper.value(it); opt.textContent = mapper.label(it); }
        else { opt.value = it; opt.textContent = it; }
        el.appendChild(opt);
    });
    el.value = cur;
}

function ensureIntelChart(id, config) {
    if (intelCharts[id]) intelCharts[id].destroy();
    intelCharts[id] = new Chart(document.getElementById(id).getContext('2d'), config);
}

const pctTxt = (v) => `${(Number(v) * 100).toFixed(0)}%`;
const pp = (v) => `${v >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(0)} p.p.`;

// ── load filtros ─────────────────────────────────────────────────────────────
async function carregarFiltrosIntel() {
    const f = await api('/api/execucao/filtros');
    const uoMapper = { value: x => x.codigo, label: x => `${x.codigo} — ${x.nome}` };
    populateSelectIntel('if-uo', f.uos, uoMapper);
    populateSelectIntel('if-programa', f.programas);
    populateSelectIntel('if-acao', f.acoes);
    populateSelectIntel('if-grupo', f.grupos);
    populateSelectIntel('if-elemento', f.elementos);
    populateSelectIntel('if-fonte', f.fontes);
    populateSelectIntel('if-classificacao', f.classificacoes);
    // selects do simulador
    populateSelectIntel('sim-uo', f.uos, uoMapper);
    populateSelectIntel('sim-grupo', f.grupos);
    populateSelectIntel('sim-fonte', f.fontes);
}

// ── main update ──────────────────────────────────────────────────────────────
async function atualizarIntel() {
    const f = getIntelFiltros();
    document.getElementById('intel-filtro-resumo').textContent = resumoFiltrosIntel(f);
    await Promise.all([
        atualizarKpisIntel(f),
        atualizarChartRitmo(f),
        atualizarChartQuadrante(f),
        atualizarChartEsgotamento(f),
        atualizarChartCreditos(f),
        atualizarTabelaIntel(f),
        atualizarInsights(f),
    ]);
}

// ── KPIs ─────────────────────────────────────────────────────────────────────
async function atualizarKpisIntel(f) {
    const [k, c] = await Promise.all([
        api('/api/inteligencia/kpis', f),
        api('/api/inteligencia/creditos', f),
    ]);
    document.getElementById('ikpi-taxa').textContent    = pctTxt(k.taxa_execucao);
    document.getElementById('ikpi-gap').textContent     =
        `${pp(k.gap_ritmo)} vs. esperado ${pctTxt(k.ritmo_esperado)}`;
    document.getElementById('ikpi-deficit').textContent = moedaCompacta(k.deficit_total);
    document.getElementById('ikpi-ndef').textContent    = k.n_linhas_deficit;
    document.getElementById('ikpi-nrisco').textContent  = k.n_linhas_risco;
    document.getElementById('ikpi-folga').textContent   = moedaCompacta(k.folga_remanejavel);
    document.getElementById('ikpi-nfolga').textContent  = `${k.n_linhas_folga} linhas subexecutadas`;
    document.getElementById('ikpi-creditos').textContent = moedaCompacta(c.saldo_liquido);
}

// ── chart ritmo (barras h., cor por gap) ──────────────────────────────────────
function corGap(gap) {
    if (gap > 0.10) return GESP.red;
    if (gap > 0)    return GESP.yellow;
    if (gap > -0.10) return GESP.skyMid;
    return GESP.green;
}

async function atualizarChartRitmo(f) {
    const dim = document.getElementById('intel-dim').value;
    const rows = await api('/api/inteligencia/ritmo', Object.assign({}, f, { dimensao: dim }));
    const labels = rows.map(r => {
        const base = (r.categoria || '—').toString();
        return r.nome ? `${base} — ${(r.nome || '').slice(0, 26)}` : base.slice(0, 34);
    });
    ensureIntelChart('intel-chart-ritmo', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Taxa de execução',
                data: rows.map(r => +(r.taxa_execucao * 100).toFixed(1)),
                backgroundColor: rows.map(r => corGap(r.gap_ritmo)),
                borderRadius: 3,
            }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: {
                    label: c => {
                        const r = rows[c.dataIndex];
                        return [
                            `Execução: ${(r.taxa_execucao * 100).toFixed(1)}% (gap ${pp(r.gap_ritmo)})`,
                            `Dotação: ${moedaCompleta(r.dotacao)}`,
                            `A empenhar: ${moedaCompleta(r.a_empenhar)}`,
                        ];
                    },
                } },
                annotation: undefined,
            },
            scales: {
                x: { suggestedMax: 100, ticks: { callback: v => v + '%' },
                     grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart quadrante (bubble) ──────────────────────────────────────────────────
async function atualizarChartQuadrante(f) {
    const d = await api('/api/inteligencia/folga-pressao', f);
    const pts = d.pontos || [];
    const maxDot = Math.max(1, ...pts.map(p => Math.abs(p.dotacao)));
    const raio = (dot) => {
        const r = Math.sqrt(Math.abs(dot) / maxDot) * 26;
        return Math.max(4, Math.min(28, r));
    };
    const grupos = ['PRESSAO', 'FOLGA', 'NORMAL'];
    const datasets = grupos.map(q => ({
        label: q.charAt(0) + q.slice(1).toLowerCase(),
        data: pts.filter(p => p.quadrante === q).map(p => ({
            x: p.x, y: p.y, r: raio(p.dotacao),
            assunto: p.assunto, uo: p.uo_codigo, dotacao: p.dotacao,
        })),
        backgroundColor: QUAD_COR[q] + 'CC',
        borderColor: QUAD_COR[q],
        borderWidth: 1,
    }));
    ensureIntelChart('intel-chart-quadrante', {
        type: 'bubble',
        data: { datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: {
                    label: c => {
                        const p = c.raw;
                        return [
                            `${(p.assunto || '—').slice(0, 40)} (UO ${p.uo || '—'})`,
                            `Execução: ${p.x}% · A empenhar: ${moedaCompleta(p.y)}`,
                            `Dotação: ${moedaCompleta(p.dotacao)}`,
                        ];
                    },
                } },
            },
            scales: {
                x: { title: { display: true, text: 'Taxa de execução (%)' },
                     suggestedMin: 0, suggestedMax: 100,
                     grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { title: { display: true, text: 'A empenhar (R$)' },
                     ticks: { callback: v => moedaCompacta(v) },
                     grid: { color: 'rgba(0,0,0,0.05)' } },
            },
        },
    });
}

// ── chart esgotamento (barras meses, cor por risco) ───────────────────────────
async function atualizarChartEsgotamento(f) {
    const rows = await api('/api/inteligencia/esgotamento', Object.assign({}, f, { top_n: 15 }));
    ensureIntelChart('intel-chart-esgotamento', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.assunto || '—').slice(0, 28)),
            datasets: [{
                label: 'Mês de esgotamento',
                data: rows.map(r => r.mes_esgotamento),
                backgroundColor: rows.map(r => RISCO_COR[r.risco] || GESP.gray500),
                borderRadius: 3,
            }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: {
                    label: c => {
                        const r = rows[c.dataIndex];
                        return [
                            `Risco: ${r.risco}`,
                            `Mês de esgotamento: ${r.mes_esgotamento}`,
                            `A empenhar: ${moedaCompleta(r.a_empenhar)} · Ritmo/mês: ${moedaCompleta(r.burn_mensal)}`,
                        ];
                    },
                } },
            },
            scales: {
                x: { suggestedMin: 0, suggestedMax: 12,
                     title: { display: true, text: 'Mês do exercício (1–12)' },
                     grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart créditos (supl vs red por grupo) ────────────────────────────────────
async function atualizarChartCreditos(f) {
    const c = await api('/api/inteligencia/creditos', f);
    const rows = c.por_grupo || [];
    ensureIntelChart('intel-chart-creditos', {
        type: 'bar',
        data: {
            labels: rows.map(r => r.grupo || '—'),
            datasets: [
                { label: 'Suplementação', data: rows.map(r => r.suplementacao), backgroundColor: GESP.green, borderRadius: 3 },
                { label: 'Redução',       data: rows.map(r => r.reducao),       backgroundColor: GESP.red,   borderRadius: 3 },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: c => `${c.dataset.label}: ${moedaCompleta(c.parsed.y)}` } },
            },
            scales: {
                y: { ticks: { callback: v => moedaCompacta(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
                x: { grid: { display: false } },
            },
        },
    });
}

// ── insights ──────────────────────────────────────────────────────────────────
async function atualizarInsights(f) {
    const items = await api('/api/inteligencia/insights', f);
    renderInsights(items);
}

function renderInsights(items) {
    const box = document.getElementById('insights-cards');
    if (!items || !items.length) {
        box.innerHTML = '<div class="insight-card"><div class="insight-card__texto">Sem insights para os filtros aplicados.</div></div>';
        return;
    }
    box.innerHTML = items.map(it => `
        <div class="insight-card ${it.severidade}">
            <div class="insight-card__head">
                <span class="insight-card__sev">${it.severidade}</span>
                <span class="insight-card__titulo">${it.titulo}</span>
            </div>
            <div class="insight-card__texto">${it.texto}</div>
        </div>`).join('');
}

// ── tabela ──────────────────────────────────────────────────────────────────
function pillRisco(risco) {
    if (risco === 'DEFICIT') return '<span class="pill def">Déficit</span>';
    if (risco === 'CRITICO') return '<span class="pill crit">Crítico</span>';
    if (risco === 'ATENCAO') return '<span class="pill warn">Atenção</span>';
    return '<span class="pill ok">OK</span>';
}

async function atualizarTabelaIntel(f) {
    const rows = await api('/api/inteligencia/esgotamento', Object.assign({}, f, { top_n: 50 }));
    const tbody = document.getElementById('intel-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty">Nenhuma linha em risco para os filtros aplicados.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        const grave = (r.risco === 'DEFICIT' || r.risco === 'CRITICO');
        return `
        <tr class="${grave ? 'deficit' : ''}">
            <td><strong>${r.uo_codigo || '—'}</strong><br>
                <small style="color:var(--color-text-mute)">${(r.uo_nome || '').slice(0, 40)}</small></td>
            <td><span title="${r.assunto || ''}">${(r.assunto || '—').slice(0, 45)}</span><br>
                <small style="color:var(--color-text-mute)">${r.programa ? 'Prog: ' + r.programa : ''} ${r.acao ? '· Ação: ' + r.acao : ''}</small></td>
            <td>${r.grupo || '—'}</td>
            <td class="num">${moedaCompleta(r.dotacao)}</td>
            <td class="num">${moedaCompleta(r.empenhado)}</td>
            <td class="num ${grave ? 'alvo' : ''}">${moedaCompleta(r.a_empenhar)}</td>
            <td class="num">${moedaCompleta(r.burn_mensal)}</td>
            <td class="num">${r.mes_esgotamento === null ? '—' : r.mes_esgotamento}</td>
            <td>${pillRisco(r.risco)}</td>
        </tr>`;
    }).join('');
}

// ── simulador ────────────────────────────────────────────────────────────────
async function simular() {
    const valor = parseFloat(document.getElementById('sim-valor').value) || 0;
    if (valor <= 0) { alert('Informe um valor de despesa nova maior que zero.'); return; }
    const f = getIntelFiltros();
    const params = Object.assign({}, f, {
        valor,
        grupo: document.getElementById('sim-grupo').value,
        fonte: document.getElementById('sim-fonte').value,
        uo:    document.getElementById('sim-uo').value,
    });
    const r = await api('/api/inteligencia/simular', params);

    document.getElementById('sim-resultado').style.display = 'block';
    document.getElementById('sim-folga').textContent     = moedaCompleta(r.folga_disponivel);
    document.getElementById('sim-cobertura').textContent = moedaCompleta(r.cobertura);
    document.getElementById('sim-gap').textContent       = moedaCompleta(r.gap_descoberto);

    document.getElementById('sim-box-cob').className = 'sim-box ' + (r.coberto ? 'ok' : '');
    document.getElementById('sim-box-gap').className = 'sim-box ' + (r.coberto ? 'ok' : 'bad');

    const ver = document.getElementById('sim-veredito');
    ver.className = 'sim-veredito ' + (r.coberto ? 'ok' : 'bad');
    ver.innerHTML = `<strong>${r.coberto ? '✓ Coberto por remanejamento' : '⚠ Exige nova fonte'}.</strong> `
        + r.veredito
        + ` <small style="color:var(--color-text-mute)">(nova taxa de execução do escopo: ${pctTxt(r.nova_taxa_execucao)})</small>`;

    const tbody = document.getElementById('sim-tbody');
    if (!r.candidatas.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">Sem folga remanejável no escopo.</td></tr>';
    } else {
        tbody.innerHTML = r.candidatas.map(c => `
            <tr>
                <td><strong>${c.uo_codigo || '—'}</strong><br>
                    <small style="color:var(--color-text-mute)">${(c.uo_nome || '').slice(0, 38)}</small></td>
                <td>${(c.assunto || '—').slice(0, 45)}</td>
                <td>${c.grupo || '—'}</td>
                <td class="num">${moedaCompleta(c.a_empenhar)}</td>
                <td class="num"><strong>${moedaCompleta(c.remanejar)}</strong></td>
            </tr>`).join('');
    }
}

// ── export ────────────────────────────────────────────────────────────────────
function buildIntelUrl(format) {
    const f = getIntelFiltros();
    const url = new URL(`/api/inteligencia/export.${format}`, window.location.origin);
    Object.entries(f).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
    return url.toString();
}

// ── events ────────────────────────────────────────────────────────────────────
document.getElementById('btn-aplicar-intel').addEventListener('click', atualizarIntel);
document.getElementById('btn-reset-intel').addEventListener('click', () => {
    document.querySelectorAll('.filters select').forEach(s => s.value = '');
    document.querySelectorAll('.filters input').forEach(i => i.value = '');
    atualizarIntel();
});
document.getElementById('intel-dim').addEventListener('change', () => atualizarChartRitmo(getIntelFiltros()));
document.getElementById('btn-simular').addEventListener('click', simular);
document.getElementById('btn-sim-limpar').addEventListener('click', () => {
    document.getElementById('sim-valor').value = '';
    document.getElementById('sim-grupo').value = '';
    document.getElementById('sim-fonte').value = '';
    document.getElementById('sim-uo').value = '';
    document.getElementById('sim-resultado').style.display = 'none';
});
document.getElementById('btn-intel-csv').addEventListener('click', () => { window.location.href = buildIntelUrl('csv'); });
document.getElementById('btn-intel-pdf').addEventListener('click', () => { window.open(buildIntelUrl('pdf'), '_blank'); });

(async () => {
    await carregarFiltrosIntel();
    await atualizarIntel();
})();
