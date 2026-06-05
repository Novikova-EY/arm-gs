/**
 * Режимы годов на сводках «максимумы» (ОЭС/ФО/ЭЗ) и электроёмкости:
 * — manual: только диапазон «Год начала» / «Год конца» (кнопки периодов неактивны);
 * — segments: отчётный N−9…N, среднесрочный N+1…N+6 и/или долгосрочный N+1…N+17.
 */
(function (global) {
    var STORAGE_KEY = "energyConsumptionSummaryMaxYearSegVisibleV6";
    var MEDIUM_YEARS_AFTER_N = 6;
    var LONG_YEARS_AFTER_N = 17;

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

    function urlHasPdLong() {
        try {
            var v = new URL(window.location.href).searchParams.get("pd_long");
            return v === "1" || v === "true" || v === "yes" || v === "on";
        } catch (e) {
            return false;
        }
    }

    function segmentPresets(n, longSegEnabled) {
        var presets = [
            {
                reporting: true,
                medium: false,
                long: false,
                lo: n - 9,
                hi: n,
                pdMedium: false,
                pdLong: false,
            },
            {
                reporting: false,
                medium: true,
                long: false,
                lo: n + 1,
                hi: n + MEDIUM_YEARS_AFTER_N,
                pdMedium: true,
                pdLong: false,
            },
            {
                reporting: true,
                medium: true,
                long: false,
                lo: n - 9,
                hi: n + MEDIUM_YEARS_AFTER_N,
                pdMedium: true,
                pdLong: false,
            },
        ];
        if (!longSegEnabled) {
            return presets;
        }
        return presets.concat([
            {
                reporting: false,
                medium: false,
                long: true,
                lo: n + 1,
                hi: n + LONG_YEARS_AFTER_N,
                pdMedium: false,
                pdLong: true,
            },
            {
                reporting: true,
                medium: false,
                long: true,
                lo: n - 9,
                hi: n + LONG_YEARS_AFTER_N,
                pdMedium: false,
                pdLong: true,
            },
            {
                reporting: false,
                medium: true,
                long: true,
                lo: n + 1,
                hi: n + LONG_YEARS_AFTER_N,
                pdMedium: true,
                pdLong: true,
            },
            {
                reporting: true,
                medium: true,
                long: true,
                lo: n - 9,
                hi: n + LONG_YEARS_AFTER_N,
                pdMedium: true,
                pdLong: true,
            },
        ]);
    }

    function emptySegmentState() {
        return { mode: "manual", reporting: false, medium: false, long: false };
    }

    function segmentsDefaultState(longSegEnabled) {
        if (longSegEnabled) {
            return { mode: "segments", reporting: true, medium: true, long: true };
        }
        return { mode: "segments", reporting: true, medium: false, long: false };
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

    function inferStateFromUrlForm(n, longSegEnabled) {
        var years = readFormYears();
        if (!years) {
            return null;
        }
        var pdMedium = urlHasPdMedium();
        var pdLong = longSegEnabled && urlHasPdLong();
        var presets = segmentPresets(n, longSegEnabled);
        var i;
        for (i = 0; i < presets.length; i++) {
            var c = presets[i];
            if (
                years.sy === c.lo &&
                years.ey === c.hi &&
                pdMedium === c.pdMedium &&
                pdLong === c.pdLong
            ) {
                return {
                    mode: "segments",
                    reporting: c.reporting,
                    medium: c.medium,
                    long: c.long,
                };
            }
        }
        return emptySegmentState();
    }

    function readState(n, serverMediumLoaded, serverLongLoaded, longSegEnabled) {
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
                        long:
                            longSegEnabled &&
                            p.long === true &&
                            serverLongLoaded,
                    };
                }
            }
        } catch (e1) { /* */ }
        var inferred = inferStateFromUrlForm(n, longSegEnabled);
        if (inferred) {
            return inferred;
        }
        return segmentsDefaultState(longSegEnabled);
    }

    function writeState(state) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e2) { /* */ }
    }

    function segmentBounds(n, reporting, medium, long, longSegEnabled) {
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
        if (longSegEnabled && long) {
            lo = lo === null ? n + 1 : Math.min(lo, n + 1);
            hi = hi === null ? n + LONG_YEARS_AFTER_N : Math.max(hi, n + LONG_YEARS_AFTER_N);
        }
        if (lo === null) {
            return null;
        }
        return { lo: lo, hi: hi };
    }

    function buildVisibleYears(state, n, longSegEnabled) {
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
        if (longSegEnabled && state.long) {
            for (y = n + 1; y <= n + LONG_YEARS_AFTER_N; y++) {
                visible[y] = true;
            }
        }
        return visible;
    }

    function applyYearVisibility(state, table, n, longSegEnabled) {
        var visible = buildVisibleYears(state, n, longSegEnabled);
        table.querySelectorAll("[data-ec-summary-col-year]").forEach(function (el) {
            var yr = parseInt(el.getAttribute("data-ec-summary-col-year") || "", 10);
            var show = Object.prototype.hasOwnProperty.call(visible, yr);
            el.classList.toggle("pd-ec-year-col-hidden", !show);
        });
    }

    function syncSegmentButtons(state, bar, longSegEnabled) {
        bar.querySelectorAll("button[data-coeff-seg]").forEach(function (btn) {
            var seg = btn.getAttribute("data-coeff-seg");
            if (seg !== "reporting" && seg !== "medium" && seg !== "long") {
                return;
            }
            if (seg === "long" && !longSegEnabled) {
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
                } else if (seg === "medium") {
                    btn.title = "Включить среднесрочный период (сбросить ручной выбор годов)";
                } else {
                    btn.title =
                        "Включить долгосрочный период (сбросить ручной выбор годов)";
                }
                return;
            }
            if (seg === "reporting") {
                btn.title = "Показать или скрыть отчетный период";
            } else if (seg === "medium") {
                btn.title = "Показать или скрыть среднесрочный период";
            } else {
                btn.title = "Показать или скрыть долгосрочный период";
            }
            var on = state[seg] === true;
            btn.classList.toggle("btn-warning", on);
            btn.classList.toggle("btn-outline-warning", !on);
            btn.setAttribute("aria-pressed", on ? "true" : "false");
        });
    }

    function replaceUrlWithoutReload(reporting, medium, long, longSegEnabled) {
        try {
            var u = new URL(window.location.href);
            if (medium) {
                u.searchParams.set("pd_medium", "1");
            } else {
                u.searchParams.delete("pd_medium");
            }
            if (longSegEnabled) {
                if (long) {
                    u.searchParams.set("pd_long", "1");
                } else {
                    u.searchParams.delete("pd_long");
                }
            }
            var qs = u.searchParams.toString();
            window.history.replaceState(
                window.history.state,
                "",
                u.pathname + (qs ? "?" + qs : "") + u.hash
            );
        } catch (eRm) { /* */ }
    }

    function navigateSegmentMode(reporting, medium, long, n, longSegEnabled) {
        var bounds = segmentBounds(n, reporting, medium, long, longSegEnabled);
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
        if (longSegEnabled) {
            if (long) {
                u.searchParams.set("pd_long", "1");
            } else {
                u.searchParams.delete("pd_long");
            }
        }
        writeState({
            mode: "segments",
            reporting: reporting,
            medium: medium,
            long: longSegEnabled ? long : false,
        });
        window.location.href = u.toString();
    }

    function removeLtEiYearColBootStyle() {
        var boot = document.getElementById("lt-ei-year-col-boot");
        if (boot) {
            boot.remove();
        }
    }

    function inferStateFromBootConfig(boot, n, longSegEnabled) {
        if (!boot || boot.n !== n) {
            return null;
        }
        var sy = parseInt(boot.startYear, 10);
        var ey = parseInt(boot.endYear, 10);
        if (isNaN(sy) || isNaN(ey)) {
            return null;
        }
        var pdMedium = boot.serverMediumLoaded === 1;
        var pdLong = longSegEnabled && boot.serverLongLoaded === 1;
        var presets = segmentPresets(n, longSegEnabled);
        var i;
        for (i = 0; i < presets.length; i++) {
            var c = presets[i];
            if (sy === c.lo && ey === c.hi && pdMedium === c.pdMedium && pdLong === c.pdLong) {
                return {
                    mode: "segments",
                    reporting: c.reporting,
                    medium: c.medium,
                    long: c.long,
                };
            }
        }
        return emptySegmentState();
    }

    function readStateFromBootOrDefaults(
        n,
        serverMediumLoaded,
        serverLongLoaded,
        longSegEnabled
    ) {
        var boot = global.__ltEiYearSegBoot;
        if (boot && boot.n === n) {
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
                            long:
                                longSegEnabled &&
                                p.long === true &&
                                serverLongLoaded,
                        };
                    }
                }
            } catch (eBoot) { /* */ }
            var inferred =
                inferStateFromBootConfig(boot, n, longSegEnabled) ||
                inferStateFromUrlForm(n, longSegEnabled);
            if (inferred) {
                return inferred;
            }
            return segmentsDefaultState(longSegEnabled);
        }
        return readState(n, serverMediumLoaded, serverLongLoaded, longSegEnabled);
    }

    function applyLtEiYearColBootFromConfig() {
        var boot = global.__ltEiYearSegBoot;
        if (!boot || !boot.years || !boot.years.length || !boot.n) {
            return;
        }
        var longSegEnabled = true;
        var serverMediumLoaded = boot.serverMediumLoaded === 1;
        var serverLongLoaded = boot.serverLongLoaded === 1;
        var state = readStateFromBootOrDefaults(
            boot.n,
            serverMediumLoaded,
            serverLongLoaded,
            longSegEnabled
        );
        var visible = buildVisibleYears(state, boot.n, longSegEnabled);
        var rules = [];
        boot.years.forEach(function (y) {
            if (!Object.prototype.hasOwnProperty.call(visible, y)) {
                rules.push(
                    ".pd-ec-max-year-visibility-table [data-ec-summary-col-year=\"" +
                        y +
                        "\"]{display:none!important}"
                );
            }
        });
        if (!rules.length) {
            return;
        }
        var el = document.createElement("style");
        el.id = "lt-ei-year-col-boot";
        el.textContent = rules.join("");
        document.head.appendChild(el);
    }

    function initEcMaxYearPeriodMode() {
        removeLtEiYearColBootStyle();
        var table = document.getElementById("powerDemandSummaryTable");
        var bar = document.getElementById("powerDemandCoeffSegToggles");
        if (!table || table.getAttribute("data-ec-max-year-segments") !== "1" || !bar) {
            return;
        }

        var n = parseBaseYear(table);
        if (!n) {
            return;
        }

        var longSegEnabled = bar.querySelector('button[data-coeff-seg="long"]') !== null;
        var serverMediumLoaded = table.getAttribute("data-pd-server-medium-loaded") === "1";
        var serverLongLoaded = table.getAttribute("data-pd-server-long-loaded") === "1";
        var state = readStateFromBootOrDefaults(
            n,
            serverMediumLoaded,
            serverLongLoaded,
            longSegEnabled
        );

        function applyAll() {
            applyYearVisibility(state, table, n, longSegEnabled);
            syncSegmentButtons(state, bar, longSegEnabled);
        }

        function resetManualState() {
            state.mode = "manual";
            state.reporting = false;
            state.medium = false;
            state.long = false;
            writeState(state);
            applyAll();
        }

        applyAll();

        var yearForm = document.getElementById("powerDemandSummaryYearForm");
        if (yearForm) {
            yearForm.addEventListener("submit", function () {
                writeState(emptySegmentState());
            });
        }

        ["start_year", "end_year"].forEach(function (id) {
            var sel = document.getElementById(id);
            if (!sel) {
                return;
            }
            sel.addEventListener("change", resetManualState);
        });

        bar.addEventListener("click", function (e) {
            var btn = e.target.closest("button[data-coeff-seg]");
            if (!btn) {
                return;
            }
            var seg = btn.getAttribute("data-coeff-seg");
            if (seg !== "reporting" && seg !== "medium" && seg !== "long") {
                return;
            }
            if (seg === "long" && !longSegEnabled) {
                return;
            }

            if (state.mode === "manual") {
                var onlyReporting = seg === "reporting";
                var onlyMedium = seg === "medium";
                var onlyLong = seg === "long";
                if (onlyMedium && !serverMediumLoaded) {
                    navigateSegmentMode(onlyReporting, true, onlyLong, n, longSegEnabled);
                    return;
                }
                if (onlyLong && !serverLongLoaded) {
                    navigateSegmentMode(onlyReporting, onlyMedium, true, n, longSegEnabled);
                    return;
                }
                navigateSegmentMode(onlyReporting, onlyMedium, onlyLong, n, longSegEnabled);
                return;
            }

            var nextReporting = seg === "reporting" ? !state.reporting : state.reporting;
            var nextMedium = seg === "medium" ? !state.medium : state.medium;
            var nextLong = seg === "long" ? !state.long : state.long;

            if (seg === "medium" && nextMedium && !serverMediumLoaded) {
                navigateSegmentMode(nextReporting, true, nextLong, n, longSegEnabled);
                return;
            }
            if (seg === "long" && nextLong && !serverLongLoaded) {
                navigateSegmentMode(nextReporting, nextMedium, true, n, longSegEnabled);
                return;
            }

            var noneActive = !nextReporting && !nextMedium && (!longSegEnabled || !nextLong);
            if (noneActive) {
                state.mode = "segments";
                state.reporting = false;
                state.medium = false;
                state.long = false;
                writeState(state);
                replaceUrlWithoutReload(false, false, false, longSegEnabled);
                applyAll();
                return;
            }

            navigateSegmentMode(nextReporting, nextMedium, nextLong, n, longSegEnabled);
        });
    }

    global.initEcMaxYearPeriodMode = initEcMaxYearPeriodMode;
    if (global.__ltEiYearSegBoot) {
        applyLtEiYearColBootFromConfig();
    }
})(window);
