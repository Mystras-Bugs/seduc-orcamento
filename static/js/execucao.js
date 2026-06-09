/* execucao.js – Tela de Execução Orçamentária */

const execCharts = {};
let currentView = 'assunto';
const MESES_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

// ── helpers ────────────────────────────────────────────────────────────────
function getExecFiltros() {
    return {
        uo:           document.getElementById('ef-uo').value,
        programa:     document.getElementById('ef-programa').value,
        acao:         document.getElementById('ef-acao').value,
        grupo:        document.getElementById('ef-grupo').value,
        elemento:     document.getElementById('ef-elemento').value,
        fonte:        document.getElementById('ef-fonte').value,
        classificacao:document.getElementById('ef-classificacao').value,
        assunto:      document.getElementById('ef-assunto').value.trim(),
    };
}

function resumoFiltrosExec(f) {
    const partes = [];
    Object.entries(f).forEach(([k, v]) => { if (v) partes.push(`${k}=${v}`); });
    return partes.length ? `Aplicados: ${partes.join(' · ')}` : 'Sem filtros aplicados.';
}

function populateSelectExec(id, items, mapper) {
    const el = document.getElementById(id);
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

function ensureExecChart(id, config) {
    if (execCharts[id]) execCharts[id].destroy();
    execCharts[id] = new Chart(document.getElementById(id).getContext('2d'), config);
}

function pct(a, b) {
    if (!b || b === 0) return 0;
    return Math.min(100, Math.round((a / b) * 100));
}

function pctBar(val, max = 100) {
    const p = Math.min(100, Math.max(0, val));
    const color = p >= 90 ? GESP.green : p >= 60 ? GESP.yellow : GESP.blue;
    return `<div style="background:#e5e7eb;border-radius:4px;height:8px;width:100%;">
        <div style="background:${color};height:8px;border-radius:4px;width:${p}%;" title="${p}%"></div>
    </div><small style="font-size:10px;color:#6b7280;">${p}%</small>`;
}

// ── load filtros ────────────────────────────────────────────────────────────
async function carregarFiltrosExec() {
    const f = await api('/api/execucao/filtros');
    populateSelectExec('ef-uo', f.uos, { value: x => x.codigo, label: x => `${x.codigo} — ${x.nome}` });
    populateSelectExec('ef-programa', f.programas);
    populateSelectExec('ef-acao', f.acoes);
    populateSelectExec('ef-grupo', f.grupos);
    populateSelectExec('ef-elemento', f.elementos);
    populateSelectExec('ef-fonte', f.fontes);
    populateSelectExec('ef-classificacao', f.classificacoes);
}

// ── main update ─────────────────────────────────────────────────────────────
async function atualizarExec() {
    const f = getExecFiltros();
    document.getElementById('exec-filtro-resumo').textContent = resumoFiltrosExec(f);
    await Promise.all([
        atualizarKpisExec(f),
        atualizarChartUO(f),
        atualizarChartDonut(f),
        atualizarChartMensal(f),
        atualizarChartAssunto(f),
        atualizarTabelaExec(f),
    ]);
}

// ── KPIs ────────────────────────────────────────────────────────────────────
async function atualizarKpisExec(f) {
    const k = await api('/api/execucao/kpis', f);
    document.getElementById('ekpi-dotacao').textContent   = moedaCompacta(k.dotacao);
    document.getElementById('ekpi-empenhado').textContent = moedaCompacta(k.empenhado);
    document.getElementById('ekpi-liquidado').textContent = moedaCompacta(k.liquidado);
    document.getElementById('ekpi-aempenhar').textContent = moedaCompacta(k.a_empenhar);
    document.getElementById('ekpi-aliquidar').textContent = moedaCompacta(k.a_liquidar);
    document.getElementById('ekpi-emp-pct').textContent   = `${pct(k.empenhado, k.dotacao)}% da dotação`;
    document.getElementById('ekpi-liq-pct').textContent   = `${pct(k.liquidado, k.empenhado)}% do empenhado`;
}

// ── chart UO ────────────────────────────────────────────────────────────────
async function atualizarChartUO(f) {
    const rows = await api('/api/execucao/por-uo', f);
    const labels = rows.slice(0,15).map(r => (r.uo_codigo||'—') + ' — ' + (r.uo_nome||'').slice(0,30));
    ensureExecChart('exec-chart-uo', {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Dotação',   data: rows.slice(0,15).map(r => r.dotacao),   backgroundColor: GESP.blue,   borderRadius: 3 },
                { label: 'Empenhado', data: rows.slice(0,15).map(r => r.empenhado), backgroundColor: GESP.yellow,  borderRadius: 3 },
                { label: 'Liquidado', data: rows.slice(0,15).map(r => r.liquidado), backgroundColor: GESP.green,  borderRadius: 3 },
            ],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: c => `${c.dataset.label}: ${moedaCompleta(c.parsed.x)}` } },
            },
            scales: {
                x: { ticks: { callback: v => moedaCompacta(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── chart donut ─────────────────────────────────────────────────────────────
async function atualizarChartDonut(f) {
    const k = await api('/api/execucao/kpis', f);
    const liquidado  = Math.max(0, k.liquidado);
    const aLiquidar  = Math.max(0, k.a_liquidar);
    const aEmpenhar  = Math.max(0, k.a_empenhar);
    ensureExecChart('exec-chart-donut', {
        type: 'doughnut',
        data: {
            labels: ['Liquidado', 'A Liquidar', 'A Empenhar'],
            datasets: [{ data: [liquidado, aLiquidar, aEmpenhar],
                backgroundColor: [GESP.green, GESP.skyMid, GESP.blue],
                borderWidth: 2, borderColor: '#fff' }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '60%',
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: c => `${c.label}: ${moedaCompleta(c.parsed)}` } },
            },
        },
    });
}

// ── chart mensal ────────────────────────────────────────────────────────────
async function atualizarChartMensal(f) {
    const d = await api('/api/execucao/mensal', f);
    ensureExecChart('exec-chart-mensal', {
        type: 'bar',
        data: {
            labels: MESES_PT,
            datasets: [
                { label: 'A Empenhar no Mês', data: d.a_empenhar, backgroundColor: GESP.blue, borderRadius: 4 },
                { label: 'Empenhado no Mês',  data: d.empenhado,  backgroundColor: GESP.yellow, borderRadius: 4 },
                { label: 'Liquidado no Mês',  data: d.liquidado,  backgroundColor: GESP.green,  borderRadius: 4 },
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

// ── chart top assuntos ───────────────────────────────────────────────────────
async function atualizarChartAssunto(f) {
    const rows = await api('/api/execucao/top-assuntos', f);
    ensureExecChart('exec-chart-assunto', {
        type: 'bar',
        data: {
            labels: rows.map(r => (r.assunto||'—').slice(0,30)),
            datasets: [{ label: 'Dotação', data: rows.map(r => r.dotacao), backgroundColor: PALETTE, borderRadius: 4 }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false },
                tooltip: { callbacks: { label: c => `Dotação: ${moedaCompleta(c.parsed.x)}` } } },
            scales: {
                x: { ticks: { callback: v => moedaCompacta(v) } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// ── tabela ───────────────────────────────────────────────────────────────────
function setView(view, btn) {
    currentView = view;
    document.querySelectorAll('[id^=view-]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    atualizarTabelaExec(getExecFiltros());
}

async function atualizarTabelaExec(f) {
    const params = Object.assign({}, f, { agrupamento: currentView });
    const rows = await api('/api/execucao/tabela', params);
    const tbody = document.getElementById('exec-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty">Nenhum registro para os filtros aplicados.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        const deficit = r.a_empenhar < 0;
        const execPct = pct(r.empenhado, r.dotacao);
        return `
        <tr class="${deficit ? 'deficit' : ''}">
            <td><strong>${r.uo_codigo || '—'}</strong><br>
                <small style="color:var(--color-text-mute)">${(r.uo_nome||'').slice(0,40)}</small></td>
            <td><span title="${r.assunto||''}">${(r.assunto||'—').slice(0,45)}</span><br>
                <small style="color:var(--color-text-mute)">${r.programa ? 'Prog: '+r.programa : ''} ${r.acao ? '· Ação: '+r.acao : ''}</small></td>
            <td>${r.grupo || '—'}</td>
            <td class="num">${moedaCompleta(r.dotacao)}</td>
            <td class="num">${moedaCompleta(r.empenhado)}</td>
            <td class="num ${deficit ? 'alvo' : ''}">${moedaCompleta(r.a_empenhar)}</td>
            <td class="num">${moedaCompleta(r.liquidado)}</td>
            <td class="num">${moedaCompleta(r.a_liquidar)}</td>
            <td>${deficit
                ? '<span class="pill alert">Déficit</span>'
                : execPct >= 80
                    ? '<span class="pill ok">Avançado</span>'
                    : execPct >= 40
                        ? '<span class="pill warn">Em Execução</span>'
                        : '<span class="pill">Inicial</span>'}</td>
            <td style="padding:8px 12px;">${pctBar(execPct)}</td>
        </tr>`;
    }).join('');
}

// ── export ───────────────────────────────────────────────────────────────────
function buildExecUrl(format) {
    const f = getExecFiltros();
    const url = new URL(`/api/execucao/export.${format}`, window.location.origin);
    Object.entries(f).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
    url.searchParams.set('agrupamento', currentView);
    return url.toString();
}

// ── events ───────────────────────────────────────────────────────────────────
document.getElementById('btn-aplicar-exec').addEventListener('click', atualizarExec);
document.getElementById('btn-reset-exec').addEventListener('click', () => {
    document.querySelectorAll('.filters select').forEach(s => s.value = '');
    document.querySelectorAll('.filters input').forEach(i => i.value = '');
    atualizarExec();
});
document.getElementById('btn-exec-csv').addEventListener('click', () => { window.location.href = buildExecUrl('csv'); });
document.getElementById('btn-exec-pdf').addEventListener('click', () => { window.open(buildExecUrl('pdf'), '_blank'); });

(async () => {
    await carregarFiltrosExec();
    await atualizarExec();
})();
