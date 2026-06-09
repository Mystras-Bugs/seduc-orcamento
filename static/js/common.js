/* Utilidades globais - SEDUC Orcamento */

/* Paleta 2D profissional — núcleo cinza/preto/vermelho + tons de apoio
   dessaturados e harmônicos. Vermelho reservado a déficit/alerta.
   As chaves são mantidas para compatibilidade com as telas existentes. */
const GESP = {
    blue:        "#3E5C76",   /* azul-ardósia (série principal / info) */
    blueDark:    "#2A3F52",
    blueLight:   "#6B8299",
    red:         "#C8101A",   /* acento / déficit */
    yellow:      "#B08A3E",   /* ocre suave (atenção) */
    green:       "#5B7B6F",   /* verde-sálvia (positivo) */
    sky:         "#9DB4C4",
    skyMid:      "#6B8299",
    skyPale:     "#C3D0DA",
    wine:        "#7A3B33",
    olive:       "#8A9A6B",
    blueNight:   "#2A3F52",
    gray50:      "#F7F8FA",
    gray200:     "#DDE1E8",
    gray500:     "#6B7280",
    gray700:     "#2E3440",
};

/* Sequência harmônica para séries categóricas (déficit sempre em vermelho). */
const PALETTE = [
    GESP.blue, GESP.gray500, GESP.green, GESP.yellow,
    GESP.skyMid, GESP.olive, GESP.wine, GESP.blueNight,
    GESP.sky, GESP.blueLight, GESP.skyPale, GESP.red,
];

const moeda = (v) => {
    const n = Number(v) || 0;
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
};
const moedaCompleta = (v) => {
    const n = Number(v) || 0;
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
};
const moedaCompacta = (v) => {
    const n = Number(v) || 0;
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2).replace(".", ",") + " bi";
    if (abs >= 1e6) return (n / 1e6).toFixed(2).replace(".", ",") + " mi";
    if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(".", ",") + " mil";
    return n.toLocaleString("pt-BR");
};
const dataPt = (s) => {
    if (!s) return "";
    const d = new Date(s);
    if (isNaN(d)) return s;
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
};

async function api(path, params = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, v);
    });
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Falha em " + path + ": " + resp.status);
    return resp.json();
}

// Chart.js global defaults — estilo 2D plano e profissional
if (window.Chart) {
    Chart.defaults.font.family = "Montserrat, Verdana, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = GESP.gray700;
    Chart.defaults.borderColor = "rgba(21,24,31,0.06)";   // grade discreta

    // Barras chapadas, bordas finas, cantos levemente arredondados
    Chart.defaults.elements.bar.borderWidth = 0;
    Chart.defaults.elements.bar.borderRadius = 3;
    Chart.defaults.elements.bar.borderSkipped = false;
    Chart.defaults.elements.bar.maxBarThickness = 34;

    // Linhas finas, pontos discretos
    Chart.defaults.elements.line.borderWidth = 2;
    Chart.defaults.elements.line.tension = 0.25;
    Chart.defaults.elements.point.radius = 2;
    Chart.defaults.elements.point.hoverRadius = 4;

    // Donut/pizza: aro fino branco entre fatias (sem sombra/3D)
    Chart.defaults.elements.arc.borderWidth = 1;
    Chart.defaults.elements.arc.borderColor = "#FFFFFF";

    // Legendas limpas com marcadores em ponto
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 14;

    // Tooltip sóbrio (fundo escuro neutro, sem caret exagerado)
    Chart.defaults.plugins.tooltip.backgroundColor = "rgba(21,24,31,0.92)";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.titleColor = "#FFFFFF";
    Chart.defaults.plugins.tooltip.bodyColor = "#E4E7EC";
    Chart.defaults.plugins.tooltip.usePointStyle = true;
}
