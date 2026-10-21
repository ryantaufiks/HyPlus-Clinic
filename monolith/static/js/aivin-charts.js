/*
 * Chart.js theme and helpers shared by the dashboard and patient pages.
 * Colours come from the design-system tokens in aivin.css.
 */
(function () {
    "use strict";

    const css = getComputedStyle(document.documentElement);
    const token = (name) => css.getPropertyValue(name).trim();

    const COLORS = {
        series1: token("--chart-series-1"),
        series2: token("--chart-series-2"),
        grid: token("--chart-grid"),
        axis: token("--chart-axis"),
        label: token("--chart-label"),
        ink: token("--aivin-ink"),
        surface: token("--aivin-surface"),
        status: {
            good: token("--aivin-good"),
            warning: token("--aivin-warning"),
            serious: token("--aivin-serious"),
            critical: token("--aivin-critical"),
        },
    };

    Chart.defaults.font.family = token("--aivin-font");
    Chart.defaults.font.size = 12;
    Chart.defaults.color = COLORS.label;
    Chart.defaults.borderColor = COLORS.grid;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 300;
    Chart.defaults.plugins.legend.display = false; // legends are rendered in HTML
    Object.assign(Chart.defaults.plugins.tooltip, {
        backgroundColor: COLORS.ink,
        titleColor: "#fff",
        bodyColor: "#fff",
        padding: 10,
        cornerRadius: 8,
        boxPadding: 4,
        usePointStyle: true,
    });

    function axes(yTitle, extraY = {}) {
        return {
            x: {
                grid: { display: false },
                border: { color: COLORS.axis },
                ticks: { maxRotation: 0, autoSkipPadding: 12 },
            },
            y: {
                grid: { color: COLORS.grid },
                border: { display: false },
                ticks: { padding: 6 },
                title: yTitle ? { display: true, text: yTitle, color: COLORS.label } : undefined,
                ...extraY,
            },
        };
    }

    /** Fill a <details class="chart-table"> with an accessible table of the data. */
    function renderTable(details, columns, rows) {
        if (!details) return;
        const head = columns.map((c) => `<th${c.num ? ' class="num"' : ""}>${esc(c.label)}</th>`).join("");
        const body = rows.length
            ? rows
                  .map((r) => `<tr>${columns.map((c) => `<td${c.num ? ' class="num"' : ""}>${esc(c.value(r))}</td>`).join("")}</tr>`)
                  .join("")
            : `<tr><td colspan="${columns.length}" class="text-muted">No data</td></tr>`;
        details.innerHTML = `<summary>View as table</summary>
            <div class="table-responsive"><table class="table table-sm table-aivin"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
    }

    function lineDataset(label, data, color) {
        return {
            label,
            data,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBorderColor: COLORS.surface,
            pointBorderWidth: 2,
            tension: 0.25,
            spanGaps: true,
        };
    }

    /** Line chart over time-ordered points. `series`: [{label, key, color}]. */
    function timeLine(canvas, points, series, { yTitle, labelFor, suggestedMin, suggestedMax } = {}) {
        return new Chart(canvas, {
            type: "line",
            data: {
                labels: points.map(labelFor),
                datasets: series.map((s) => lineDataset(s.label, points.map((p) => p[s.key]), s.color)),
            },
            options: {
                interaction: { mode: "index", intersect: false },
                scales: axes(yTitle, { suggestedMin, suggestedMax }),
            },
        });
    }

    /** Replace a chart's data in place (keeps hover state and avoids flicker). */
    function update(chart, labels, datasets) {
        chart.data.labels = labels;
        datasets.forEach((data, i) => (chart.data.datasets[i].data = data));
        chart.update("none");
    }

    window.AivinCharts = { COLORS, axes, renderTable, timeLine, update, lineDataset };
})();
