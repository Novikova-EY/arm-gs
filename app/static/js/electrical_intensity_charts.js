/**

 * Scatter-графики электроёмкости — стиль как в Excel «Таблица 1».

 * Фактическая: маркеры accent5 (#4BACC6), без линии.

 * Расчётная: линия accent6 (#F79646), без маркеров.

 */

(function () {

    "use strict";



    var EXCEL = {

        colorFact: "#4BACC6",

        colorCalc: "#F79646",

        fontFamily: "'Roboto', sans-serif",

        fontSize: 22,

        lineWidthCalc: 2,

        pointRadiusFact: 5,

        gridColor: "rgba(89, 89, 89, 0.28)",

        gridDash: [5, 5],

        axisColor: "#595959",

        legendChartGap: 24,

    };

    var legendChartGapPlugin = {

        id: "ltEiLegendChartGap",

        beforeInit: function (chart) {

            var legend = chart.legend;

            if (!legend) return;

            var originalFit = legend.fit.bind(legend);

            legend.fit = function () {

                originalFit();

                if (this.options.position === "right") {

                    this.width += EXCEL.legendChartGap;

                }

            };

        },

        afterLayout: function (chart) {

            var legend = chart.legend;

            if (!legend || !legend.options.display || legend.options.position !== "right") return;

            legend.left += EXCEL.legendChartGap;

        },

    };



    function parseChartPayload(host) {

        var script = host.querySelector("script.lt-ei-chart-data");

        if (!script || !script.textContent) return null;

        try {

            return JSON.parse(script.textContent);

        } catch (e) {

            return null;

        }

    }



    function sortByX(points) {

        return points.slice().sort(function (a, b) {

            return a.x - b.x;

        });

    }



    function formatAxisX(v) {

        if (v === null || v === undefined || Number.isNaN(v)) return "";

        return Number(v).toLocaleString("ru-RU", {

            maximumFractionDigits: 0,

            minimumFractionDigits: 0,

        });

    }



    function formatAxisY(v) {

        if (v === null || v === undefined || Number.isNaN(v)) return "";

        return Number(v).toLocaleString("ru-RU", {

            minimumFractionDigits: 1,

            maximumFractionDigits: 1,

        });

    }



    function formatNum(n) {

        if (n === null || n === undefined || Number.isNaN(n)) return "—";

        var abs = Math.abs(n);

        if (abs >= 1e6 || (abs > 0 && abs < 0.001)) {

            return n.toLocaleString("ru-RU", { maximumFractionDigits: 6 });

        }

        return n.toLocaleString("ru-RU", { maximumFractionDigits: 4 });

    }



    function parseDecimalInput(raw) {

        if (raw == null) return null;

        var s = String(raw).trim().replace(/\u00a0/g, "").replace(/\s/g, "");

        if (!s || s === "—" || s === "-" || s === "–") return null;

        s = s.replace(",", ".");

        var n = parseFloat(s);

        return Number.isFinite(n) ? n : null;

    }



    function computeCalculatedY(accumX, coefA, coefX) {

        if (accumX == null || coefA == null || coefX == null) return null;

        if (!(accumX > 0) || !(coefA > 0)) return null;

        var powered = Math.pow(accumX, coefX);

        if (!Number.isFinite(powered)) return null;

        var y = coefA * powered;

        return Number.isFinite(y) ? y : null;

    }



    function buildCalcSeries(payload, coefA) {

        var bases = payload.calc_bases;

        var coefX = payload.coef_x;

        if (!bases || !bases.length || coefX == null) return [];

        var a = coefA;

        if (a == null) a = payload.initial_coef_a;

        if (a == null) return [];

        var out = [];

        bases.forEach(function (b) {

            var y = computeCalculatedY(b.x, a, coefX);

            if (y == null) return;

            out.push({ x: b.x, y: y, year: b.year });

        });

        return sortByX(out);

    }



    function destroyChart(host) {

        if (host.__ltEiChartInstance) {

            host.__ltEiChartInstance.destroy();

            host.__ltEiChartInstance = null;

        }

    }



    var pageFontFamilyCache = null;

    function resolvePageFontFamily() {
        if (pageFontFamilyCache) return pageFontFamilyCache;
        var el = document.body || document.documentElement;
        if (!el) return EXCEL.fontFamily;
        var family = window.getComputedStyle(el).fontFamily;
        pageFontFamilyCache = family || EXCEL.fontFamily;
        return pageFontFamilyCache;
    }

    function chartFont() {
        return { family: resolvePageFontFamily(), size: EXCEL.fontSize };
    }



    function buildDatasets(fact, calc) {

        var datasets = [];

        if (fact.length) {

            datasets.push({

                label: "Фактическая",

                data: sortByX(fact),

                type: "scatter",

                showLine: false,

                pointStyle: "circle",

                pointRadius: EXCEL.pointRadiusFact,

                pointHoverRadius: EXCEL.pointRadiusFact + 2,

                backgroundColor: EXCEL.colorFact,

                borderColor: EXCEL.colorFact,

                borderWidth: 1,

                order: 1,

            });

        }

        if (calc.length) {

            datasets.push({

                label: "Расчетная",

                data: sortByX(calc),

                type: "scatter",

                showLine: true,

                pointRadius: 0,

                pointHoverRadius: 6,

                pointHitRadius: 8,

                backgroundColor: EXCEL.colorCalc,

                borderColor: EXCEL.colorCalc,

                borderWidth: EXCEL.lineWidthCalc,

                order: 2,

            });

        }

        return datasets;

    }



    function renderChart(host, payload, calcData) {

        var canvas = host.querySelector("canvas.lt-ei-scatter-chart-canvas");

        if (!canvas || typeof Chart === "undefined") return;



        var fact = payload.fact || [];

        var calc = calcData != null ? calcData : buildCalcSeries(payload, payload.initial_coef_a);

        if (!calc.length && payload.calc && payload.calc.length) {

            calc = payload.calc;

        }

        if (!fact.length && !calc.length) return;



        destroyChart(host);



        host.__ltEiChartInstance = new Chart(canvas, {

            type: "scatter",

            data: { datasets: buildDatasets(fact, calc) },

            plugins: [legendChartGapPlugin],

            options: {

                responsive: true,

                maintainAspectRatio: false,

                layout: { padding: { top: 4, right: 4, bottom: 2, left: 2 } },

                plugins: {

                    legend: {

                        position: "right",

                        align: "center",

                        labels: {

                            usePointStyle: true,

                            pointStyle: "circle",

                            boxWidth: 10,

                            padding: 12,

                            font: chartFont(),

                            color: EXCEL.axisColor,

                            generateLabels: function (chart) {

                                var defaults = Chart.defaults.plugins.legend.labels.generateLabels(chart);

                                defaults.forEach(function (item) {

                                    if (item.text === "Расчетная") {

                                        item.pointStyle = "line";

                                        item.lineWidth = EXCEL.lineWidthCalc;

                                        item.strokeStyle = EXCEL.colorCalc;

                                        item.fillStyle = EXCEL.colorCalc;

                                    } else if (item.text === "Фактическая") {

                                        item.fillStyle = EXCEL.colorFact;

                                        item.strokeStyle = EXCEL.colorFact;

                                    }

                                });

                                return defaults;

                            },

                        },

                    },

                    tooltip: {

                        titleFont: chartFont(),

                        bodyFont: chartFont(),

                        callbacks: {

                            label: function (ctx) {

                                var raw = ctx.raw || {};

                                var year = raw.year != null ? raw.year : "";

                                var x = formatNum(ctx.parsed.x);

                                var y = formatNum(ctx.parsed.y);

                                var prefix = ctx.dataset.label || "";

                                return (

                                    prefix +

                                    (year ? " (" + year + ")" : "") +

                                    ": " +

                                    x +

                                    " → " +

                                    y +

                                    " кВт·ч/тыс. руб."

                                );

                            },

                        },

                    },

                },

                scales: {

                    x: {

                        type: "linear",

                        position: "bottom",

                        title: {

                            display: true,

                            text: payload.x_axis_label || "Накопленные инвестиции, млн руб.",

                            font: chartFont(),

                            color: EXCEL.axisColor,

                            padding: { top: 6 },

                        },

                        ticks: {

                            font: chartFont(),

                            color: EXCEL.axisColor,

                            maxTicksLimit: 8,

                            callback: function (v) {

                                return formatAxisX(v);

                            },

                        },

                        grid: {

                            color: EXCEL.gridColor,

                            borderDash: EXCEL.gridDash,

                            drawOnChartArea: true,

                        },

                        border: { color: EXCEL.axisColor },

                    },

                    y: {

                        title: {

                            display: true,

                            text: payload.y_axis_label || "Электроемкость, кВт·ч/тыс. руб.",

                            font: chartFont(),

                            color: EXCEL.axisColor,

                            padding: { bottom: 6 },

                        },

                        ticks: {

                            font: chartFont(),

                            color: EXCEL.axisColor,

                            callback: function (v) {

                                return formatAxisY(v);

                            },

                        },

                        grid: {

                            color: "rgba(89, 89, 89, 0.18)",

                            drawOnChartArea: true,

                        },

                        border: { color: EXCEL.axisColor },

                    },

                },

            },

        });

        host.dataset.ltEiChartReady = "1";

    }



    function findCoefRowForChartHost(host) {

        var key = host.getAttribute("data-lt-ei-chart-key");

        if (!key) return null;

        var rows = document.querySelectorAll("tr.lt-ei-coef-row[data-lt-ei-coef-chart]");

        for (var i = 0; i < rows.length; i++) {

            if (rows[i].getAttribute("data-lt-ei-chart-key") === key) {

                return rows[i];

            }

        }

        return null;

    }



    function calcSeriesForHost(host, payload, coefRow) {

        if (!payload) return [];

        if (payload.calc_bases && payload.calc_bases.length) {

            var coefA = payload.initial_coef_a;

            if (coefRow) {

                var inp = coefRow.querySelector('input.lt-ei-coef-input[name="coef_a[]"]');

                coefA = inp ? parseDecimalInput(inp.value) : null;

                if (coefA == null) {

                    coefA = parseDecimalInput(

                        inp && inp.getAttribute("data-db-full") ? inp.getAttribute("data-db-full") : null

                    );

                }

                if (coefA == null) coefA = payload.initial_coef_a;

            }

            return buildCalcSeries(payload, coefA);

        }

        return payload.calc || [];

    }



    function initHost(host) {

        var payload = parseChartPayload(host);

        if (!payload) return;

        host.__ltEiChartPayload = payload;

        var coefRow = findCoefRowForChartHost(host);

        renderChart(host, payload, calcSeriesForHost(host, payload, coefRow));

    }



    function findChartHost(coefRow) {

        var key = coefRow.getAttribute("data-lt-ei-chart-key");

        if (!key) return null;

        var hosts = document.querySelectorAll(".lt-ei-scatter-chart-host");

        for (var i = 0; i < hosts.length; i++) {

            if (hosts[i].getAttribute("data-lt-ei-chart-key") === key) {

                return hosts[i];

            }

        }

        return null;

    }



    function refreshChartForCoefRow(coefRow) {

        var host = findChartHost(coefRow);

        if (!host) return;

        var payload = host.__ltEiChartPayload || parseChartPayload(host);

        if (!payload) return;

        host.__ltEiChartPayload = payload;

        renderChart(host, payload, calcSeriesForHost(host, payload, coefRow));

    }



    function bindCoefAInputs() {

        document.querySelectorAll("tr.lt-ei-coef-row[data-lt-ei-coef-chart]").forEach(function (coefRow) {

            var inp = coefRow.querySelector('input.lt-ei-coef-input[name="coef_a[]"]');

            if (!inp || inp.dataset.ltEiCoefChartBound === "1") return;

            inp.dataset.ltEiCoefChartBound = "1";

            var handler = function () {

                refreshChartForCoefRow(coefRow);

            };

            inp.addEventListener("input", handler);

            inp.addEventListener("change", handler);

        });

    }



    function initAll() {

        var hosts = document.querySelectorAll(".lt-ei-scatter-chart-host");

        if (!hosts.length) return;

        if (typeof Chart === "undefined") return;



        function onHostReady(host) {

            initHost(host);

        }



        if (!("IntersectionObserver" in window)) {

            hosts.forEach(onHostReady);

            bindCoefAInputs();

            return;

        }



        var observer = new IntersectionObserver(

            function (entries) {

                entries.forEach(function (entry) {

                    if (!entry.isIntersecting) return;

                    var host = entry.target;

                    observer.unobserve(host);

                    onHostReady(host);

                });

            },

            { root: null, rootMargin: "120px 0px", threshold: 0.01 }

        );



        hosts.forEach(function (host) {

            observer.observe(host);

        });



        setTimeout(function () {

            hosts.forEach(function (host) {

                if (host.dataset.ltEiChartReady !== "1") {

                    onHostReady(host);

                }

            });

        }, 800);



        bindCoefAInputs();

    }



    function bindScrollWrapResize() {
        var wrap = document.getElementById("powerDemandSummaryScrollWrap");
        if (!wrap) return;
        var scrollEl = wrap.closest(".page-table-scroll") || wrap;
        var resizeCharts = function () {
            document.querySelectorAll(".lt-ei-scatter-chart-host").forEach(function (host) {
                if (host.__ltEiChartInstance) {
                    host.__ltEiChartInstance.resize();
                }
            });
        };
        scrollEl.addEventListener("scroll", resizeCharts, { passive: true });
        window.addEventListener("resize", resizeCharts);
    }

    function boot() {
        initAll();
        bindScrollWrapResize();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

})();


