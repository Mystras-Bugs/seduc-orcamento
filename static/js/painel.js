/* Painel Gerencial - filtros, graficos e tabela de execucao */

const charts = {};
const FIELDS = ["uo", "programa", "acao", "grupo", "elemento", "fonte",
                "status", "assunto"];

function getFiltros() {
    return {
        uo:          document.getElementById("f-uo").value,
        programa:    document.getElementById("f-programa").value,
        acao:        document.getElementById("f-acao").value,
        grupo:       document.getElementById("f-grupo").value,
        elemento:    document.getElementById("f-elemento").value,
        fonte:       document.getElementById("f-fonte").value,
        status:      document.getElementById("f-status").value,
        assunto:     document.getElementById("f-assunto").value.trim(),
        data_inicio: document.getElementById("f-de").value,
        data_fim:    document.getElementById("f-ate").value,
    };
}

function resumoFiltros(f) {
    const partes = [];
    Object.entries(f).forEach(([k, v]) => { if (v) partes.push(`${k}=${v}`); });
    return partes.length ? `Aplicados: ${partes.join(" · ")}` : "Sem filtros aplicados.";
}

function populateSelect(id, items, mapper) {
    const el = document.getElementById(id);
    const cur = el.value;
    el.innerHTML = el.options[0].outerHTML;
    items.forEach((it) => {
        const opt = document.createElement("option");
        if (mapper) { opt.value = mapper.value(it); opt.textContent = mapper.label(it); }
        else { opt.value = it; opt.textContent = it; }
        el.appendChild(opt);
    });
    el.value = cur;
}

async function carregarFiltros() {
    const f = await api("/api/filtros");
    populateSelect("f-uo",       f.uos,       { value: (x) => x.codigo, label: (x) => `${x.codigo} — ${x.nome}` });
    populateSelect("f-programa", f.programas);
    populateSelect("f-acao",     f.acoes);
    populateSelect("f-grupo",    f.grupos);
    populateSelect("f-elemento", f.elementos);
    populateSelect("f-fonte",    f.fontes);
    populateSelect("f-status",   f.status);
}

async function atualizarTudo() {
    const f = getFiltros();
    document.getElementById("filtro-resumo").textContent = resumoFiltros(f);
    await Promise.all([
        atualizarMetricas(f),
        atualizarTendencia(f),
        atualizarGrupo(f),
        atualizarUO(f),
        atualizarStatus(f),
        atualizarExecucao(f),
    ]);
}

async function atualizarMetricas(f) {
    const m = await api("/api/metricas", f);
    document.getElementById("kpi-sup").textContent     = moedaCompacta(m.total_suplementacao);
    document.getElementById("kpi-sup-sub").textContent = moedaCompleta(m.total_suplementacao);
    document.getElementById("kpi-red").textContent     = moedaCompacta(m.total_reducao);
    document.getElementById("kpi-red-sub").textContent = moedaCompleta(m.total_reducao);
    document.getElementById("kpi-saldo").textContent   = moedaCompacta(m.saldo_liquido);
    document.getElementById("kpi-total").textContent   = m.total_expedientes.toLocaleString("pt-BR");
    const s = m.status;
    document.getElementById("kpi-status").textContent =
        `${s.realizadas} realizadas · ${s.em_andamento} em andamento · ${s.em_elaboracao} em elaboração`;
}

function ensureChart(id, config) {
    if (charts[id]) { charts[id].destroy(); }
    charts[id] = new Chart(document.getElementById(id).getContext("2d"), config);
}

async function atualizarTendencia(f) {
    const s = await api("/api/serie-mensal", f);
    ensureChart("chart-tendencia", {
        type: "line",
        data: {
            labels: s.labels,
            datasets: [
                {
                    label: "Suplementação Acumulada",
                    data: s.suplementacao_acum,
                    borderColor: GESP.blue,
                    backgroundColor: "rgba(3, 78, 162, 0.12)",
                    tension: 0.3, fill: true, borderWidth: 2.5,
                    pointRadius: 3, pointBackgroundColor: GESP.blue,
                },
                {
                    label: "Redução Acumulada",
                    data: s.reducao_acum,
                    borderColor: GESP.red,
                    backgroundColor: "rgba(255, 22, 31, 0.08)",
                    tension: 0.3, fill: true, borderWidth: 2.5,
                    pointRadius: 3, pointBackgroundColor: GESP.red,
                },
                {
                    label: "Suplementação no Mês",
                    data: s.suplementacao_mes,
                    borderColor: GESP.green, borderDash: [5, 4],
                    tension: 0.3, fill: false, borderWidth: 1.6,
                    pointRadius: 2,
                },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" },
                tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${moedaCompleta(c.parsed.y)}` } },
            },
            scales: {
                y: { ticks: { callback: (v) => moedaCompacta(v) }, grid: { color: "rgba(0,0,0,0.05)" } },
                x: { grid: { display: false } },
            },
        },
    });
}

async function atualizarGrupo(f) {
    const rows = await api("/api/distribuicao-grupo", f);
    const labels = rows.map((r) => r.grupo ? `Grupo ${r.grupo}` : "Sem grupo");
    const data = rows.map((r) => r.sup || 0);
    ensureChart("chart-grupo", {
        type: "doughnut",
        data: { labels, datasets: [{ data, backgroundColor: PALETTE, borderWidth: 2, borderColor: "#fff" }] },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: "60%",
            plugins: {
                legend: { position: "bottom" },
                tooltip: { callbacks: { label: (c) => `${c.label}: ${moedaCompleta(c.parsed)}` } },
            },
        },
    });
}

async function atualizarUO(f) {
    const rows = await api("/api/distribuicao-uo", f);
    const labels = rows.map((r) => (r.uo_codigo || "—") + " — " + (r.uo_nome || "").slice(0, 36));
    const sup = rows.map((r) => r.sup || 0);
    const red = rows.map((r) => Math.abs(r.red || 0));
    ensureChart("chart-uo", {
        type: "bar",
        data: {
            labels,
            datasets: [
                { label: "Suplementação", data: sup, backgroundColor: GESP.blue },
                { label: "Redução",       data: red, backgroundColor: GESP.red },
            ],
        },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" },
                tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${moedaCompleta(c.parsed.x)}` } },
            },
            scales: {
                x: { ticks: { callback: (v) => moedaCompacta(v) }, grid: { color: "rgba(0,0,0,0.05)" } },
                y: { ticks: { font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

async function atualizarStatus(f) {
    const rows = await api("/api/status-funil", f);
    const order = ["Em Elaboracao", "Em Andamento", "Realizada"];
    const lookup = Object.fromEntries(rows.map((r) => [r.status, r.n]));
    const labels = order.map((s) => s.replace("Em Elaboracao", "Em Elaboração"));
    const data = order.map((s) => lookup[s] || 0);
    ensureChart("chart-status", {
        type: "bar",
        data: { labels, datasets: [{ data, backgroundColor: [GESP.yellow, GESP.skyMid, GESP.green] }] },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } }, y: { grid: { display: false } } },
        },
    });
}

async function atualizarExecucao(f) {
    const rows = await api("/api/execucao", f);
    const tbody = document.getElementById("execucao-body");
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="empty">Nenhum registro para os filtros aplicados.</td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map((r) => `
        <tr class="${r.deficit ? "deficit" : ""}">
            <td><strong>${r.uo_codigo || "—"}</strong><br>
                <small style="color:var(--color-text-mute)">${(r.uo_nome || "").slice(0, 42)}</small></td>
            <td>${r.assunto || "—"}</td>
            <td>${r.grupo || "—"}</td>
            <td class="num">${moedaCompleta(r.dotacao_inicial)}</td>
            <td class="num">${moedaCompleta(r.valor_reservado)}</td>
            <td class="num">${moedaCompleta(r.valor_empenhado)}</td>
            <td class="num">${moedaCompleta(r.valor_liquidado)}</td>
            <td class="num">${moedaCompleta(r.valor_a_liquidar)}</td>
            <td class="num alvo">${moedaCompleta(r.valor_a_empenhar)}</td>
            <td>${r.deficit ? '<span class="pill alert">Déficit</span>'
                            : '<span class="pill ok">Saudável</span>'}</td>
        </tr>
    `).join("");
}

function buildExportUrl(format) {
    const f = getFiltros();
    const url = new URL(`/api/export/execucao.${format}`, window.location.origin);
    Object.entries(f).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
    return url.toString();
}

document.getElementById("btn-aplicar").addEventListener("click", atualizarTudo);
document.getElementById("btn-reset").addEventListener("click", () => {
    document.querySelectorAll(".filters select").forEach((s) => (s.value = ""));
    document.querySelectorAll(".filters input").forEach((i) => (i.value = ""));
    atualizarTudo();
});
document.getElementById("btn-csv").addEventListener("click", () => {
    window.location.href = buildExportUrl("csv");
});
document.getElementById("btn-pdf").addEventListener("click", () => {
    window.open(buildExportUrl("pdf"), "_blank");
});

(async () => {
    await carregarFiltros();
    await atualizarTudo();
})();
