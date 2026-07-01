/**
 * Режимы годов на сводках «максимумы» потребления (ОЭС/ФО/ЭЗ):
 * — manual: только диапазон «Год начала» / «Год конца» (кнопки периодов неактивны);
 * — segments: отчётный N−9…N и/или среднесрочный N+1…N+6.
 */
(function (global) {
    var STORAGE_KEY = "powerDemandSummaryMaxYearSegVisibleV3";
    var MEDIUM_YEARS_AFTER_N = 6;

    function parseBaseYear(table) {
        var n = parseInt(table.getAttribute("data-coeff-base-year") || "", 10);
        return n && !isNaN(n) ? n : null;
    }

    function urlHasPdMedium() {
        try {
            var v = new URL(window.location.href).searchParams.get("pd_medium");
            return v === "1" || v === "true" || v === "yes" || v === "on";
        } catch (e) {
            return false;
        }
    }

    function segmentPresets(n) {
        return [
            {
                reporting: true,
                medium: false,
                lo: n - 9,
                hi: n,
                pdMedium: false,
            },
            {
                reporting: false,
                medium: true,
                lo: n + 1,
                hi: n + MEDIUM_YEARS_AFTER_N,
                pdMedium: true,
            },
            {
                reporting: true,
                medium: true,
                lo: n - 9,
                hi: n + MEDIUM_YEARS_AFTER_N,
                pdMedium: true,
            },
        ];
    }

    function emptySegmentState() {
        return { mode: "manual", reporting: false, medium: false };
    }

    function segmentsDefaultState() {
        return { mode: "segments", reporting: true, medium: false };
    }

    function readAppliedYearsFromUrl() {
        try {
            var u = new URL(window.location.href);
            var sy = parseInt(u.searchParams.get("start_year") || "", 10);
            var ey = parseInt(u.searchParams.get("end_year") || "", 10);
            if (!isNaN(sy) && !isNaN(ey)) {
                return { sy: sy, ey: ey };
            }
        } catch (eUrl) { /* */ }
        var sySel = document.getElementById("start_year");
        var eySel = document.getElementById("end_year");
        if (!sySel || !eySel) {
            return null;
        }
        var formSy = parseInt(sySel.value, 10);
        var formEy = parseInt(eySel.value, 10);
        if (isNaN(formSy) || isNaN(formEy)) {
            return null;
        }
        return { sy: formSy, ey: formEy };
    }

    function inferStateFromUrlForm(n) {
        var years = readAppliedYearsFromUrl();
        if (!years) {
            return null;
        }
        var pdMedium = urlHasPdMedium();
        var presets = segmentPresets(n);
        var i;
        for (i = 0; i < presets.length; i++) {
            var c = presets[i];
            if (years.sy === c.lo && years.ey === c.hi && pdMedium === c.pdMedium) {
                return {
                    mode: "segments",
                    reporting: c.reporting,
                    medium: c.medium,
                };
            }
        }
        return emptySegmentState();
    }

    function readState(n, serverMediumLoaded) {
        try {
            var raw = sessionStorage.getItem(STORAGE_KEY);
            if (raw) {
                var p = JSON.parse(raw);
                if (p.mode === "manual") {
                    return emptySegmentState();
                }
                if (p.mode === "segments") {
                    return {
                        mode: "segments",
                        reporting: p.reporting === true,
                        medium: p.medium === true && serverMediumLoaded,
                    };
                }
            }
        } catch (e1) { /* */ }
        var inferred = inferStateFromUrlForm(n);
        if (inferred) {
            return inferred;
        }
        return segmentsDefaultState();
    }

    function writeState(state) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e2) { /* */ }
    }

    function segmentBounds(n, reporting, medium) {
        var lo = null;
        var hi = null;
        if (reporting) {
            lo = n - 9;
            hi = n;
        }
        if (medium) {
            lo = lo === null ? n + 1 : Math.min(lo, n + 1);
            hi = hi === null ? n + MEDIUM_YEARS_AFTER_N : Math.max(hi, n + MEDIUM_YEARS_AFTER_N);
        }
        if (lo === null) {
            return null;
        }
        return { lo: lo, hi: hi };
    }

    function buildVisibleYears(state, n) {
        var visible = {};
        var y;
        if (state.mode === "manual") {
            var years = readAppliedYearsFromUrl();
            if (!years) {
                return visible;
            }
            var lo = Math.min(years.sy, years.ey);
            var hi = Math.max(years.sy, years.ey);
            for (y = lo; y <= hi; y++) {
                visible[y] = true;
            }
            return visible;
        }
        if (state.reporting) {
            for (y = n - 9; y <= n; y++) {
                visible[y] = true;
            }
        }
        if (state.medium) {
            for (y = n + 1; y <= n + MEDIUM_YEARS_AFTER_N; y++) {
                visible[y] = true;
            }
        }
        return visible;
    }

    function applyYearVisibility(state, table, n) {
        var visible = buildVisibleYears(state, n);
        table.querySelectorAll("[data-ec-summary-col-year]").forEach(function (el) {
            var yr = parseInt(el.getAttribute("data-ec-summary-col-year") || "", 10);
            var show = Object.prototype.hasOwnProperty.call(visible, yr);
            el.classList.toggle("pd-ec-year-col-hidden", !show);
        });
    }

    function syncSegmentButtons(state, bar) {
        bar.querySelectorAll("button[data-coeff-seg]").forEach(function (btn) {
            var seg = btn.getAttribute("data-coeff-seg");
            if (seg !== "reporting" && seg !== "medium") {
                return;
            }
            var manual = state.mode === "manual";
            btn.disabled = false;
            btn.classList.remove("disabled");
            if (manual) {
                btn.classList.remove("btn-warning");
                btn.classList.add("btn-outline-warning");
                btn.setAttribute("aria-pressed", "false");
                if (seg === "reporting") {
                    btn.title = "Включить отчётный период (сбросить ручной выбор годов)";
                } else {
                    btn.title = "Включить среднесрочный период (сбросить ручной выбор годов)";
                }
                return;
            }
            if (seg === "reporting") {
                btn.title = "Показать или скрыть отчетный период";
            } else {
                btn.title = "Показать или скрыть среднесрочный период";
            }
            var on = state[seg] === true;
            btn.classList.toggle("btn-warning", on);
            btn.classList.toggle("btn-outline-warning", !on);
            btn.setAttribute("aria-pressed", on ? "true" : "false");
        });
    }

    function replaceUrlWithoutReload(reporting, medium) {
        try {
            var u = new URL(window.location.href);
            if (medium) {
                u.searchParams.set("pd_medium", "1");
            } else {
                u.searchParams.delete("pd_medium");
            }
            var qs = u.searchParams.toString();
            window.history.replaceState(
                window.history.state,
                "",
                u.pathname + (qs ? "?" + qs : "") + u.hash
            );
        } catch (eRm) { /* */ }
    }

    function navigateSegmentMode(reporting, medium, n) {
        var bounds = segmentBounds(n, reporting, medium);
        var u;
        try {
            u = new URL(window.location.href);
        } catch (eNav) {
            return;
        }
        if (bounds) {
            u.searchParams.set("start_year", String(bounds.lo));
            u.searchParams.set("end_year", String(bounds.hi));
        }
        if (medium) {
            u.searchParams.set("pd_medium", "1");
        } else {
            u.searchParams.delete("pd_medium");
        }
        writeState({
            mode: "segments",
            reporting: reporting,
            medium: medium,
        });
        window.location.href = u.toString();
    }

    var yearPeriodCtx = null;

    function reapplyYearColumnVisibility() {
        if (yearPeriodCtx) {
            yearPeriodCtx.applyAll();
        }
    }

    function initEcMaxYearPeriodMode() {
        var table = document.getElementById("powerDemandSummaryTable");
        var bar = document.getElementById("powerDemandCoeffSegToggles");
        if (!table || table.getAttribute("data-ec-max-year-segments") !== "1" || !bar) {
            return;
        }

        var n = parseBaseYear(table);
        if (!n) {
            return;
        }

        var serverMediumLoaded = table.getAttribute("data-pd-server-medium-loaded") === "1";
        var state = readState(n, serverMediumLoaded);

        function applyAll() {
            applyYearVisibility(state, table, n);
            syncSegmentButtons(state, bar);
        }

        yearPeriodCtx = { applyAll: applyAll };
        applyAll();

        if (!global.__pdPdSummaryYearPeriodRowsHooked) {
            global.__pdPdSummaryYearPeriodRowsHooked = true;
            document.addEventListener(
                "pd-summary-rows-rendered",
                reapplyYearColumnVisibility
            );
        }
        if (
            global.__pdSummaryRowsReady &&
            typeof global.__pdSummaryRowsReady.then === "function"
        ) {
            global.__pdSummaryRowsReady
                .then(function () {
                    reapplyYearColumnVisibility();
                })
                .catch(function () { /* */ });
        }

        var yearForm = document.getElementById("powerDemandSummaryYearForm");
        if (yearForm) {
            yearForm.addEventListener("submit", function () {
                writeState(emptySegmentState());
            });
        }

        bar.addEventListener("click", function (e) {
            var btn = e.target.closest("button[data-coeff-seg]");
            if (!btn) {
                return;
            }
            var seg = btn.getAttribute("data-coeff-seg");
            if (seg !== "reporting" && seg !== "medium") {
                return;
            }

            if (state.mode === "manual") {
                var onlyReporting = seg === "reporting";
                var onlyMedium = seg === "medium";
                if (onlyMedium && !serverMediumLoaded) {
                    navigateSegmentMode(onlyReporting, true, n);
                    return;
                }
                navigateSegmentMode(onlyReporting, onlyMedium, n);
                return;
            }

            var nextReporting = seg === "reporting" ? !state.reporting : state.reporting;
            var nextMedium = seg === "medium" ? !state.medium : state.medium;

            if (seg === "medium" && nextMedium && !serverMediumLoaded) {
                navigateSegmentMode(nextReporting, true, n);
                return;
            }

            var noneActive = !nextReporting && !nextMedium;
            if (noneActive) {
                state.mode = "segments";
                state.reporting = false;
                state.medium = false;
                writeState(state);
                replaceUrlWithoutReload(false, false);
                applyAll();
                return;
            }

            navigateSegmentMode(nextReporting, nextMedium, n);
        });
    }

    global.initEcMaxYearPeriodMode = initEcMaxYearPeriodMode;
    global.__pdPdSummaryReapplyYearColumnVisibility = reapplyYearColumnVisibility;
})(window);
