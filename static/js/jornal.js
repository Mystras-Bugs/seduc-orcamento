/* Jornal do Dia */

document.getElementById("edicao-data").textContent =
    new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });

function shortenUO(uo) {
    if (!uo) return "uma Unidade Orçamentária";
    const t = uo.replace(/^0+/, "");
    return t.length > 60 ? t.slice(0, 58) + "…" : t;
}

function pluralize(n, s, p) { return n === 1 ? `${n} ${s}` : `${n} ${p}`; }

async function carregarMetricas() {
    try {
        const m = await api("/api/metricas");
        document.getElementById("kpi-sup").textContent   = moedaCompacta(m.total_suplementacao);
        document.getElementById("kpi-sup-sub").textContent =
            moedaCompleta(m.total_suplementacao);
        document.getElementById("kpi-red").textContent   = moedaCompacta(m.total_reducao);
        document.getElementById("kpi-red-sub").textContent =
            moedaCompleta(m.total_reducao);
        document.getElementById("kpi-saldo").textContent = moedaCompacta(m.saldo_liquido);
        document.getElementById("kpi-total").textContent = m.total_expedientes.toLocaleString("pt-BR");
        const s = m.status;
        document.getElementById("kpi-status").textContent =
            `${pluralize(s.realizadas, "realizada", "realizadas")} · ` +
            `${pluralize(s.em_andamento, "em andamento", "em andamento")} · ` +
            `${pluralize(s.em_elaboracao, "em elaboração", "em elaboração")}`;
    } catch (e) {
        console.warn(e);
    }
}

async function carregarJornal() {
    const dados = await api("/api/jornal");
    const m = dados.manchete;
    const box = document.getElementById("manchete");
    if (!m) {
        box.innerHTML = `<div class="empty warn">Nenhum dado importado ainda. ` +
            `Acesse <a href="/admin">Importar Dados</a> para subir a planilha de expedientes.</div>`;
        document.getElementById("timeline").innerHTML =
            `<li><div class="data">--</div><div class="corpo">—</div></li>`;
        return;
    }

    box.innerHTML = `
        <div class="chapeu">Manchete · Maior Suplementação</div>
        <h2>${shortenUO(m.uo_nome || m.uo_codigo)} recebe ${moedaCompacta(m.suplementacao)}
            para <em>${(m.assunto || "execução orçamentária").toLowerCase()}</em></h2>
        <p class="lead">
            Expediente <strong>${m.expediente || "—"}</strong> (${m.tipo || "—"})
            destinou <strong>${moedaCompleta(m.suplementacao)}</strong> à
            ação <em>${m.acao || "—"}</em>, dentro do programa <strong>${m.programa || "—"}</strong>.
        </p>
        <div class="meta">
            <span><b>UO:</b> ${m.uo_codigo || "—"}</span>
            <span><b>Grupo:</b> ${m.grupo || "—"}</span>
            <span><b>Fonte:</b> ${m.fonte || "—"}</span>
            <span><b>Envio:</b> ${dataPt(m.data_envio)}</span>
            <span><b>Conclusão:</b> ${dataPt(m.data_conclusao)}</span>
            <span><b>Status:</b> ${m.status || "—"}</span>
        </div>
    `;

    const timeline = document.getElementById("timeline");
    timeline.innerHTML = "";
    if (!dados.timeline.length) {
        timeline.innerHTML = `<li><div class="data">--</div><div class="corpo">Nenhum expediente disponível.</div></li>`;
    } else {
        dados.timeline.forEach((r) => {
            const li = document.createElement("li");
            const data = r.data_conclusao || r.data_envio;
            li.innerHTML = `
                <div class="data">${dataPt(data)}</div>
                <div class="corpo">
                    A <strong>${shortenUO(r.uo_nome || r.uo_codigo)}</strong>
                    recebeu suplementação para
                    <em>${(r.assunto || "—").toLowerCase()}</em>
                    <span class="valor">${moedaCompacta(r.suplementacao)}</span>
                </div>`;
            timeline.appendChild(li);
        });
    }
}

async function carregarAlertas() {
    try {
        const alertas = await api("/api/alertas");
        const box = document.getElementById("alertas-box");
        if (!alertas.length) {
            box.innerHTML = `<div class="empty">Sem alertas de déficit no momento.</div>`;
            return;
        }
        box.innerHTML = alertas.map((a) => `
            <div class="alerta-item">
                <div class="uo">${shortenUO(a.uo_nome || a.uo_codigo)}</div>
                <div>
                    <em>${(a.assunto || "—").toLowerCase()}</em>
                    — <span class="delta">${moedaCompleta(a.a_empenhar)}</span>
                    a empenhar
                </div>
            </div>
        `).join("");
    } catch (e) {
        console.warn(e);
    }
}

async function carregarResumoDeficit() {
    try {
        const d = await api("/api/jornal/resumo-deficit");
        const g = d.deficit_por_grupo || {};
        document.getElementById("rd-total").textContent   = moedaCompacta(-(d.deficit_total_33_44 || 0));
        document.getElementById("rd-custeio").textContent = moedaCompacta(-(g["33"] || 0));
        document.getElementById("rd-capital").textContent = moedaCompacta(-(g["44"] || 0));
        document.getElementById("rd-ntemas").textContent  = (d.n_linhas || 0).toLocaleString("pt-BR");

        const tbody = document.getElementById("rd-tbody");
        const linhas = d.linhas || [];
        if (!linhas.length) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty">Nenhuma linha em déficit nos grupos 33/44.</td></tr>`;
            return;
        }
        tbody.innerHTML = linhas.map((r) => `
            <tr class="deficit">
                <td><strong>${r.uge_codigo || r.uo_codigo || "—"}</strong><br>
                    <small style="color:var(--color-text-mute)">${(r.uge_nome || r.uo_nome || "").slice(0, 38)}</small></td>
                <td><span title="${r.assunto || ""}">${(r.assunto || "—").slice(0, 48)}</span></td>
                <td style="text-align:center">${r.grupo || "—"}</td>
                <td class="num alvo">${moedaCompleta(r.a_empenhar)}</td>
            </tr>`).join("");
    } catch (e) {
        console.warn(e);
    }
}

document.getElementById("btn-pdf-jornal").addEventListener("click", () => {
    window.open("/api/export/jornal.pdf", "_blank");
});

carregarMetricas();
carregarJornal();
carregarAlertas();
carregarResumoDeficit();
