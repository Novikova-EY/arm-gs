/**
 * Режимы годов на сводках «максимумы» (ОЭС/ФО/ЭЗ):
 * — manual: только диапазон «Год начала» / «Год конца» (кнопки периодов неактивны);
 * — segments: отчётный N−9…N и/или среднесрочный N+1…N+6 (ручной диапазон сбрасывается через URL).
 */
(function (global) {
    var STORAGE_KEY = "energyConsumptionSummaryMaxYearSegVisibleV4";

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
            { reporting: true, medium: false, lo: n - 9, hi: n, pdMedium: false },
            { reporting: false, medium: true, lo: n + 1, hi: n + 6, pdMedium: true },
            { reporting: true, medium: true, lo: n - 9, hi: n + 6, pdMedium: true },
        ];
    }

    function readFormYears() {
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
        var years = readFormYears();
        if (!years) {
            return null;
        }
        var pd = urlHasPdMedium();
        var presets = segmentPresets(n);
        var i;
        for (i = 0; i < presets.length; i++) {
            var c = presets[i];
            if (years.sy === c.lo && years.ey === c.hi && pd === c.pdMedium) {
                return { mode: "segments", reporting: c.reporting, medium: c.medium };
            }
        }
        return { mode: "manual", reporting: false, medium: false };
    }

    function readState(n, serverMediumLoaded) {
        try {
            var raw = sessionStorage.getItem(STORAGE_KEY);
            if (raw) {
                var p = JSON.parse(raw);
                if (p.mode === "manual") {
                    return { mode: "manual", reporting: false, medium: false };
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
        if (serverMediumLoaded) {
            return { mode: "segments", reporting: true, medium: true };
        }
        return { mode: "segments", reporting: true, medium: false };
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
            hi = hi === null ? n + 6 : Math.max(hi, n + 6);
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
            var years = readFormYears();
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
        if (state.reporting && state.medium) {
            for (y = n - 9; y <= n + 6; y++) {
                visible[y] = true;
            }
        } else if (state.reporting) {
            for (y = n - 9; y <= n; y++) {
                visible[y] = true;
            }
        } else if (state.medium) {
            for (y = n + 1; y <= n + 6; y++) {
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
                btn.title =
                    seg === "reporting"
                        ? "Включить отчётный период (сбросить ручной выбор годов)"
                        : "Включить среднесрочный период (сбросить ручной выбор годов)";
                return;
            }
            btn.title =
                seg === "reporting"
                    ? "Показать или скрыть отчетный период"
                    : "Показать или скрыть среднесрочный период";
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
        writeState({ mode: "segments", reporting: reporting, medium: medium });
        window.location.href = u.toString();
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

        applyAll();

        var yearForm = document.getElementById("powerDemandSummaryYearForm");
        if (yearForm) {
            yearForm.addEventListener("submit", function () {
                writeState({ mode: "manual", reporting: false, medium: false });
            });
        }

        ["start_year", "end_year"].forEach(function (id) {
            var sel = document.getElementById(id);
            if (!sel) {
                return;
            }
            sel.addEventListener("change", function () {
                state.mode = "manual";
                state.reporting = false;
                state.medium = false;
                writeState(state);
                applyAll();
            });
        });

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

            if (!nextReporting && !nextMedium) {
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
})(window);
