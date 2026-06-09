/* pressao.js – Necessidade Atualizada × Dotação Atual
   Usa helpers globais de common.js: api, moeda/moedaCompleta/moedaCompacta, GESP, PALETTE. */

const pressCharts = {};
const SIT_COR = { DEFICIT: '#7a0010', PRESSAO: GESP.red, EQUILIBRIO: GESP.gray500, FOLGA: GESP.green };

// ── helpers ────────────────────────────────────────────────────────────────
function getPressFiltros() {
    return {
        uge:           document.getElementById('pf-uge').value,
        uo:            document.getElementById('pf-uo').value,
        programa:      document.getElementById('pf-programa').value,
        acao:          document.getElementById('pf-acao').value,
        grupo:         document.getElementById('pf-grupo').value,
        elemento:      document.getElementById('pf-elemento').value,
        fonte:         document.getElementById('pf-fonte').value,
        classificacao: document.getElementById('pf-classificacao').value,
        assunto:       document.getElementById('pf-assunto').value.trim(),
    };
}

function resumoFiltrosPress(f) {
    const partes = [];
    Object.entries(f).forEach(([k, v]) => { if (v) partes.push(`${k}=${v}`); });
    return partes.length ? `Aplicados: ${partes.join(' · ')}` : 'Sem filtros aplicados.';
}

function populateSelectPress(id, items, mapper) {
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

function ensurePressChart(id, config) {
    if (pressCharts[id]) pressCharts[id].destroy();
    pressCharts[id] = new Chart(document.getElementById(id).getContext('2d'), config);
}

const pctTxt = (v) => (v === null || v === undefined) ? '—' : `${(Number(v) * 100).toFixed(0)}%`;

// barra de cobertura % com cor por faixa (verde>=100, amarelo 70-99, vermelho<70)
function coberturaBar(cob) {
    if (cob === null || cob === undefined) {
        return '<small style="font-size:10px;color:#6b7280;">—</small>';
    }
    const p = Math.round(cob * 100);
    const largura = Math.min(100, Math.max(0, p));
    const cor = p >= 100 ? GESP.green : p >= 70 ? GESP.yellow : GESP.red;
    return `<div style="background:#e5e7eb;border-radius:4px;height:8px;width:100%;">
        <div style="background:${cor};height:8px;border-radius:4px;width:${largura}%;" title="${p}%"></div>
    </div><small style="font-size:10px;color:#6b7280;">${p}%</small>`;
}

// ── load filtros ─────────────────────────────────────────────────────────────
async function carregarFiltrosPress() {
    const f = await api('/api/pressao/filtros');
    populateSelectPress('pf-uge', f.uges || [], { value: x => x.codigo, label: x => `${x.codigo} — ${x.nome}` });
    populateSelectPress('pf-uo', f.uos, { value: x => x.codigo, label: x => `${x.codigo} — ${x.nome}` });
    populateSelectPress('pf-programa', f.programas);
    populateSelectPress('pf-acao', f.acoes);
    populateSelectPress('pf-grupo', f.grupos);
    populateSelectPress('pf-elemento', f.elementos);
    populateSelectPress('pf-fonte', f.fontes);
    populateSelectPress('pf-classificacao', f.classificacoes);
}

// ── main update ──────────────────────────────────────────────────────────────
async function atualizarPress() {
    const f = getPressFiltros();
    document.getElementById('press-filtro-resumo').textContent = resumoFiltrosPress(f);
    await Promise.all([
        atualizarKpisPress(f),
        atualizarChartUge(f),
        atualizarChartCobertura(f),
        atualizarChartPressao(f),
        atualizarChartDim(f),
        atualizarTabelaPress(f),
        atualizarInsightsPress(f),
    ]);
}

// ── KPIs ─────────────────────────────────────────────────────────────────────
async function atualizarKpisPress(f) {
    const k = await api('/api/pressao/kpis', f);
    document.getElementById('pkpi-necessidade').textContent = moedaCompacta(k.necessidade_total);
    document.getElementById('pkpi-dotacao').textContent     = moedaCompacta(k.dotacao_atual);
    document.getElementById('pkpi-pressao').textContent     = moedaCompacta(k.pressao_total);
    document.getElementById('pkpi-deficit').textContent     = moedaCompacta(k.deficit_dotacional);
    document.getElementById('pkpi-cobertura').textContent   = pctTxt(k.cobertura_media);
    document.getElementById('pkpi-npressao').textContent    = k.n_linhas_pressao;
    document.getElementById('pkpi-nfolga').textContent      = `${k.n_linhas_folga} linhas em folga`;
}

// ── chart UGE (barras agrupadas Necessidade vs Dotação) ───────────────────────
async function atualizarChartUge(f) {
    const rows = (await api('/api/pressao/por-uge', f)).slice(0, 15);
    ensurePressChart('press-chart-uge', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.uge_codigo || '—') + ' — ' + (r.uge_nome || '').slice(0, 26)),
            datasets: [
                { label: 'Necessidade', data: rows.map(r => r.necessidade),   backgroundColor: GESP.blue,   borderRadius: 3 },
                { label: 'Dotação',     data: rows.map(r => r.dotacao_atual), backgroundColor: GESP.yellow, borderRadius: 3 },
            ],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: {
                    label: c => `${c.dataset.label}: ${moedaCompleta(c.parsed.x)}`,
                    footer: () => 'Pressão = Necessidade − Dotação (falta de teto para a despesa)',
                } },
            },
            scales: {
                x: { ticks: { callback: v => moedaCompacta(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart cobertura % por UGE (cor por faixa) ─────────────────────────────────
function corCobertura(cob) {
    if (cob === null || cob === undefined) return GESP.gray500;
    if (cob >= 1.0) return GESP.green;
    if (cob >= 0.70) return GESP.yellow;
    return GESP.red;
}

async function atualizarChartCobertura(f) {
    const rows = (await api('/api/pressao/por-uge', f))
        .filter(r => r.cobertura !== null).slice(0, 15);
    ensurePressChart('press-chart-cobertura', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.uge_codigo || '—')),
            datasets: [{
                label: 'Cobertura %',
                data: rows.map(r => +(r.cobertura * 100).toFixed(1)),
                backgroundColor: rows.map(r => corCobertura(r.cobertura)),
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
                            `Cobertura: ${(r.cobertura * 100).toFixed(1)}%`,
                            `Necessidade: ${moedaCompleta(r.necessidade)}`,
                            `Dotação: ${moedaCompleta(r.dotacao_atual)}`,
                        ];
                    },
                } },
            },
            scales: {
                x: { suggestedMax: 100, ticks: { callback: v => v + '%' }, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart pressão por assunto (vermelho) ──────────────────────────────────────
async function atualizarChartPressao(f) {
    const rows = (await api('/api/pressao/por-linha', f))
        .filter(r => r.pressao > 0).slice(0, 12);
    ensurePressChart('press-chart-pressao', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.assunto || '—').slice(0, 30)),
            datasets: [{ label: 'Pressão', data: rows.map(r => r.pressao),
                backgroundColor: GESP.red, borderRadius: 3 }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: {
                    label: c => {
                        const r = rows[c.dataIndex];
                        return [
                            `Pressão: ${moedaCompleta(r.pressao)}`,
                            `Necessidade: ${moedaCompleta(r.necessidade)} · Dotação: ${moedaCompleta(r.dotacao)}`,
                        ];
                    },
                } },
            },
            scales: {
                x: { ticks: { callback: v => moedaCompacta(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart por dimensão (Necessidade vs Dotação) ───────────────────────────────
async function atualizarChartDim(f) {
    const dim = document.getElementById('press-dim').value;
    const rows = (await api('/api/pressao/ritmo', Object.assign({}, f, { dimensao: dim }))).slice(0, 15);
    ensurePressChart('press-chart-dim', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.categoria || '—')),
            datasets: [
                { label: 'Necessidade', data: rows.map(r => r.necessidade),   backgroundColor: GESP.blue,   borderRadius: 3 },
                { label: 'Dotação',     data: rows.map(r => r.dotacao_atual), backgroundColor: GESP.yellow, borderRadius: 3 },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: {
                    label: c => `${c.dataset.label}: ${moedaCompleta(c.parsed.y)}`,
                    footer: () => 'Dotação = teto disponível · Necessidade = quanto o órgão precisa',
                } },
            },
            scales: {
                y: { ticks: { callback: v => moedaCompacta(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
                x: { grid: { display: false } },
            },
        },
    });
}

// ── insights ──────────────────────────────────────────────────────────────────
async function atualizarInsightsPress(f) {
    const items = await api('/api/pressao/insights', f);
    renderInsights(items);
}

function renderInsights(items) {
    const box = document.getElementById('insights-cards');
    if (!items || !items.length) {
        box.innerHTML = '<div class="insight-card"><div class="insight-card__texto">Sem insights para os filtros aplicados. Importe a planilha de necessidade em Importar Dados.</div></div>';
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
function pillSituacao(sit) {
    if (sit === 'DEFICIT')    return '<span class="pill def">Déficit</span>';
    if (sit === 'PRESSAO')    return '<span class="pill alert">Pressão</span>';
    if (sit === 'FOLGA')      return '<span class="pill folga">Folga</span>';
    return '<span class="pill ok">Equilíbrio</span>';
}

async function atualizarTabelaPress(f) {
    const rows = await api('/api/pressao/por-linha', f);
    const tbody = document.getElementById('press-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="empty">Nenhum registro. Importe a planilha de necessidade em Importar Dados.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        const grave = (r.situacao === 'DEFICIT' || r.situacao === 'PRESSAO');
        const cls = grave ? 'deficit' : (r.situacao === 'FOLGA' ? 'folga' : '');
        const estrut = [r.programa ? 'P' + r.programa : '', r.acao ? 'A' + r.acao : '', r.grupo || '']
            .filter(Boolean).join(' · ');
        const negEmp = r.a_empenhar < 0;
        // marcador de divergência entre o derivado e o que a planilha trouxe (35/45)
        const diverg = r.divergencia
            ? ` <span title="A Empenhar/A Liquidar derivados divergem do que a planilha trouxe (tabela 35: ${moedaCompleta(r.a_empenhar_plan)} · tabela 45: ${moedaCompleta(r.a_liquidar_plan)})" style="color:var(--gesp-yellow);cursor:help;font-weight:800;">⚠</span>`
            : '';
        return `
        <tr class="${cls}">
            <td><strong>${r.uge_codigo || '—'}</strong><br>
                <small style="color:var(--color-text-mute)">${(r.uge_nome || '').slice(0, 32)}</small></td>
            <td><span title="${r.assunto || ''}">${(r.assunto || '—').slice(0, 42)}</span><br>
                <small style="color:var(--color-text-mute)">UO ${r.uo_codigo || '—'}</small></td>
            <td><small>${estrut || '—'}</small></td>
            <td class="num">${moedaCompleta(r.necessidade)}</td>
            <td class="num">${moedaCompleta(r.dotacao)}</td>
            <td class="num ${grave ? 'alvo' : ''}">${moedaCompleta(r.pressao)}</td>
            <td style="padding:8px 12px;">${coberturaBar(r.cobertura)}</td>
            <td class="num">${moedaCompleta(r.empenhado)}</td>
            <td class="num ${negEmp ? 'alvo' : ''}">${moedaCompleta(r.a_empenhar)}${diverg}</td>
            <td class="num">${moedaCompleta(r.a_liquidar)}</td>
            <td>${pillSituacao(r.situacao)}</td>
        </tr>`;
    }).join('');
}

// ── export ────────────────────────────────────────────────────────────────────
function buildPressUrl(format) {
    const f = getPressFiltros();
    const url = new URL(`/api/pressao/export.${format}`, window.location.origin);
    Object.entries(f).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
    return url.toString();
}

// ── events ────────────────────────────────────────────────────────────────────
document.getElementById('btn-aplicar-press').addEventListener('click', atualizarPress);
document.getElementById('btn-reset-press').addEventListener('click', () => {
    document.querySelectorAll('.filters select').forEach(s => s.value = '');
    document.querySelectorAll('.filters input').forEach(i => i.value = '');
    atualizarPress();
});
document.getElementById('press-dim').addEventListener('change', () => atualizarChartDim(getPressFiltros()));
document.getElementById('btn-press-csv').addEventListener('click', () => { window.location.href = buildPressUrl('csv'); });
document.getElementById('btn-press-pdf').addEventListener('click', () => { window.open(buildPressUrl('pdf'), '_blank'); });

(async () => {
    await carregarFiltrosPress();
    await atualizarPress();
})();
