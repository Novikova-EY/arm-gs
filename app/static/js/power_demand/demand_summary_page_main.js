document.addEventListener("DOMContentLoaded", function () {
    /* Мультивыбор без «вечно раскрытого» списка: как station_filters_first_row.js (без Select2) */
    function initPdSummaryFilterDropdowns() {
        function ensureDropdownMultiSelectFromEl(selectEl) {
            if (!selectEl || selectEl.dataset.multiDropdownInit === "1") return;
            var placeholder =
                (selectEl.getAttribute("data-pd-placeholder") || "").trim() || "Выберите";
            selectEl.dataset.multiDropdownInit = "1";

            var wrapper = document.createElement("div");
            wrapper.className = "dropdown";

            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "form-select text-start";
            btn.setAttribute("data-bs-toggle", "dropdown");
            btn.setAttribute("data-bs-auto-close", "outside");
            btn.setAttribute("aria-expanded", "false");

            var menu = document.createElement("div");
            menu.className = "dropdown-menu p-2 filter-dropdown-menu";

            selectEl.classList.add("d-none");

            var parent = selectEl.parentNode;
            if (!parent) return;
            parent.replaceChild(wrapper, selectEl);
            wrapper.appendChild(btn);
            wrapper.appendChild(menu);
            wrapper.appendChild(selectEl);

            function setButtonText() {
                var selected = Array.from(selectEl.selectedOptions || [])
                    .map(function (o) {
                        return (o.textContent || "").trim();
                    })
                    .filter(Boolean);
                if (!selected.length) {
                    btn.textContent = placeholder;
                    return;
                }
                var preview = selected.slice(0, 1).join(", ");
                var suffix = selected.length > 1 ? " (+" + (selected.length - 1) + ")" : "";
                btn.textContent = preview + suffix;
            }

            function renderMenu() {
                menu.innerHTML = "";
                var actions = document.createElement("div");
                actions.className = "d-flex justify-content-end align-items-center mb-2";
                var clearBtn = document.createElement("button");
                clearBtn.type = "button";
                clearBtn.className = "btn btn-sm btn-outline-danger";
                clearBtn.textContent = "Сбросить";
                clearBtn.addEventListener("click", function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    Array.from(selectEl.options).forEach(function (opt) {
                        opt.selected = false;
                    });
                    setButtonText();
                    selectEl.dispatchEvent(new Event("change", { bubbles: true }));
                    renderMenu();
                });
                actions.appendChild(clearBtn);
                menu.appendChild(actions);

                var searchWrap = document.createElement("div");
                searchWrap.className = "mb-2";
                var searchInput = document.createElement("input");
                searchInput.type = "text";
                searchInput.className = "form-control form-control-sm";
                searchInput.placeholder = "Поиск...";
                searchInput.setAttribute("autocomplete", "off");
                searchWrap.appendChild(searchInput);
                menu.appendChild(searchWrap);

                var list = document.createElement("div");
                list.className = "d-flex flex-column gap-1";

                Array.from(selectEl.options).forEach(function (opt) {
                    var value = (opt.value != null ? String(opt.value) : "").trim();
                    if (value === "") return;

                    var item = document.createElement("label");
                    item.className = "dropdown-item d-flex align-items-center gap-2";
                    item.style.whiteSpace = "normal";

                    var cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.checked = !!opt.selected;
                    cb.addEventListener("click", function (e) {
                        e.stopPropagation();
                    });
                    cb.addEventListener("change", function (e) {
                        e.stopPropagation();
                        var found = Array.from(selectEl.options).find(function (o) {
                            return String(o.value) === value;
                        });
                        if (found) found.selected = cb.checked;
                        setButtonText();
                        selectEl.dispatchEvent(new Event("change", { bubbles: true }));
                    });

                    var text = document.createElement("span");
                    var optText = (opt.textContent || "").trim();
                    text.textContent = optText;
                    item.setAttribute("data-search-text", optText.toLowerCase());

                    item.appendChild(cb);
                    item.appendChild(text);
                    list.appendChild(item);
                });

                function applyFilter() {
                    var q = (searchInput.value || "").trim().toLowerCase();
                    list.querySelectorAll("[data-search-text]").forEach(function (el) {
                        var match =
                            !q || (el.getAttribute("data-search-text") || "").indexOf(q) !== -1;
                        el.classList.toggle("d-none", !match);
                    });
                }
                searchInput.addEventListener("input", applyFilter);
                searchInput.addEventListener("keyup", applyFilter);
                searchInput.addEventListener("keydown", function (e) {
                    e.stopPropagation();
                });

                menu.appendChild(list);
                setButtonText();
            }

            selectEl._multiDropdownRender = renderMenu;
            renderMenu();
        }

        var hasJQuery = typeof window.$ !== "undefined";
        var hasSelect2 = hasJQuery && window.$ && window.$.fn && window.$.fn.select2;
        if (hasSelect2) {
            document.querySelectorAll("#filtersCollapse select.pd-ds-ms[multiple]").forEach(function (sel) {
                var $el = window.$(sel);
                if (!$el.length || $el.data("select2")) return;
                var ph = (sel.getAttribute("data-pd-placeholder") || "").trim() || "Выберите";
                $el.select2({
                    placeholder: ph,
                    allowClear: true,
                    width: "100%",
                    closeOnSelect: false,
                    minimumResultsForSearch: 0,
                    dropdownParent: window.$(document.body),
                    dropdownCssClass: "pd-summary-filter-select2-dd",
                    language: {
                        noResults: function () {
                            return "Ничего не найдено";
                        },
                        searching: function () {
                            return "Поиск...";
                        }
                    }
                });
            });
            return;
        }
        document.querySelectorAll("#filtersCollapse select.pd-ds-ms[multiple]").forEach(function (sel) {
            ensureDropdownMultiSelectFromEl(sel);
        });
    }

    setTimeout(initPdSummaryFilterDropdowns, 100);

    (function initPowerDemandCoeffYearSegments() {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table) {
            return;
        }
        var route = table.getAttribute("data-summary-route-variant") || "";
        var useEcMax = table.getAttribute("data-ec-max-year-segments") === "1";
        if (route !== "coeff" && !useEcMax) {
            return;
        }

        var bar = document.getElementById("powerDemandCoeffSegToggles");
        if (!bar) {
            return;
        }

        if (useEcMax) {
            if (typeof initEcMaxYearPeriodMode === "function") {
                initEcMaxYearPeriodMode();
            }
            return;
        }

        var longLoaded = table.getAttribute("data-coeff-long-loaded") === "1";
        var mediumLoaded =
            table.getAttribute("data-pd-server-medium-loaded") === "1" ||
            !!table.querySelector(
                'col[data-coeff-year-segment="medium"], th[data-coeff-year-segment="medium"]'
            );
        var yearsApplied = table.getAttribute("data-pd-coeff-years-applied") === "1";
        var STORAGE_KEY = "powerDemandSummaryCoeffYearSegVisibleV2";
        var MANUAL_STORAGE_KEY = "powerDemandSummaryCoeffYearManualV1";
        var defaults = { reporting: true, medium: false, long: false };

        function parseBaseYear() {
            var n = parseInt(table.getAttribute("data-coeff-base-year") || "", 10);
            return n && !isNaN(n) ? n : null;
        }

        function readAppliedYearsFromFormOrUrl() {
            try {
                var u = new URL(window.location.href);
                var sy = parseInt(u.searchParams.get("start_year") || "", 10);
                var ey = parseInt(u.searchParams.get("end_year") || "", 10);
                if (!isNaN(sy) && !isNaN(ey)) {
                    return { sy: Math.min(sy, ey), ey: Math.max(sy, ey) };
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
            return { sy: Math.min(formSy, formEy), ey: Math.max(formSy, formEy) };
        }

        function clearManualYearVisibility() {
            table.querySelectorAll(".pd-coeff-year-col-hidden").forEach(function (el) {
                el.classList.remove("pd-coeff-year-col-hidden");
            });
            table.querySelectorAll("th.power-demand-coeff-period-th[data-coeff-group]").forEach(function (th) {
                th.classList.remove("pd-coeff-year-col-hidden");
                var mw = th.getAttribute("data-pd-coeff-period-cspan-mw");
                if (mw) {
                    th.setAttribute("colspan", mw);
                }
            });
        }

        function applyManualYearVisibility(sy, ey) {
            clearManualYearVisibility();
            ["reporting", "medium", "long"].forEach(function (seg) {
                table.classList.remove("pd-coeff-seg-hide-" + seg);
            });
            table.querySelectorAll("[data-summary-year]").forEach(function (el) {
                var yr = parseInt(el.getAttribute("data-summary-year") || "", 10);
                if (isNaN(yr)) {
                    return;
                }
                el.classList.toggle("pd-coeff-year-col-hidden", yr < sy || yr > ey);
            });
            var n = parseBaseYear();
            table.querySelectorAll("th.power-demand-coeff-period-th[data-coeff-group]").forEach(function (th) {
                var seg = th.getAttribute("data-coeff-group");
                var lo = null;
                var hi = null;
                if (seg === "reporting" && n) {
                    lo = n - 9;
                    hi = n;
                } else if (seg === "medium" && n) {
                    lo = n + 1;
                    hi = n + 6;
                } else if (seg === "long" && n) {
                    lo = n + 7;
                    hi = n + 18;
                }
                if (lo === null) {
                    return;
                }
                var visible = 0;
                var y;
                for (y = Math.max(lo, sy); y <= Math.min(hi, ey); y++) {
                    visible += 1;
                }
                if (visible <= 0) {
                    th.classList.add("pd-coeff-year-col-hidden");
                } else {
                    th.classList.remove("pd-coeff-year-col-hidden");
                    th.setAttribute("colspan", String(visible));
                }
            });
        }

        window.__pdPdSummaryReapplyCoeffYearVisibility = function () {
            if (!yearsApplied) {
                return;
            }
            var appliedYears = readAppliedYearsFromFormOrUrl();
            if (appliedYears) {
                applyManualYearVisibility(appliedYears.sy, appliedYears.ey);
            }
        };

        function syncManualPeriodButtons() {
            bar.querySelectorAll("button[data-coeff-seg]").forEach(function (btn) {
                var seg = btn.getAttribute("data-coeff-seg");
                btn.classList.remove("btn-warning");
                btn.classList.add("btn-outline-warning");
                btn.setAttribute("aria-pressed", "false");
                if (seg === "reporting") {
                    btn.title = "Показать отчётный период (сбросить ручной выбор годов)";
                } else if (seg === "medium") {
                    btn.title = "Показать среднесрочный период (сбросить ручной выбор годов)";
                } else {
                    btn.title = "Показать долгосрочный период (сбросить ручной выбор годов)";
                }
            });
        }

        function read() {
            try {
                var raw = sessionStorage.getItem(STORAGE_KEY);
                if (raw) {
                    var p = JSON.parse(raw);
                    return {
                        reporting: typeof p.reporting === "boolean" ? p.reporting : defaults.reporting,
                        medium: typeof p.medium === "boolean" ? p.medium : defaults.medium,
                        long: typeof p.long === "boolean" ? p.long : defaults.long
                    };
                }
            } catch (e) { /* */ }
            return { reporting: true, medium: false, long: false };
        }

        function write(v) {
            try {
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(v));
            } catch (e2) { /* */ }
        }

        function apply(v) {
            clearManualYearVisibility();
            ["reporting", "medium", "long"].forEach(function (seg) {
                table.classList.remove("pd-coeff-seg-hide-" + seg);
            });
            ["reporting", "medium", "long"].forEach(function (seg) {
                if (v[seg] === false) {
                    table.classList.add("pd-coeff-seg-hide-" + seg);
                }
            });
            var wrap = document.getElementById("powerDemandCoeffSegToggles");
            if (wrap) {
                wrap.querySelectorAll("button[data-coeff-seg]").forEach(function (btn) {
                    var seg = btn.getAttribute("data-coeff-seg");
                    if (!seg) {
                        return;
                    }
                    var on = v[seg] !== false;
                    btn.classList.toggle("btn-warning", on);
                    btn.classList.toggle("btn-outline-warning", !on);
                    btn.setAttribute("aria-pressed", on ? "true" : "false");
                    if (seg === "reporting") {
                        btn.title = "Показать или скрыть отчетный период";
                    } else if (seg === "medium") {
                        btn.title = "Показать или скрыть среднесрочный период";
                    } else {
                        btn.title = "Показать или скрыть долгосрочный период";
                    }
                });
            }
            refreshPowerDemandSummaryLayout();
        }

        function exitManualToSegments(preferred) {
            try {
                sessionStorage.removeItem(MANUAL_STORAGE_KEY);
            } catch (eMan) { /* */ }
            var u = new URL(window.location.href);
            u.searchParams.delete("start_year");
            u.searchParams.delete("end_year");
            if (preferred && preferred.medium && !mediumLoaded) {
                u.searchParams.set("pd_medium", "1");
            }
            if (preferred && preferred.long && !longLoaded) {
                u.searchParams.set("coeff_include_long", "1");
            }
            window.location.href = u.pathname + (u.searchParams.toString() ? "?" + u.searchParams.toString() : "") + u.hash;
        }

        var yearForm = document.getElementById("powerDemandSummaryYearForm");
        if (yearForm) {
            yearForm.addEventListener("submit", function () {
                try {
                    sessionStorage.setItem(MANUAL_STORAGE_KEY, "1");
                } catch (eSub) { /* */ }
            });
        }

        if (yearsApplied) {
            var appliedYears = readAppliedYearsFromFormOrUrl();
            if (appliedYears) {
                applyManualYearVisibility(appliedYears.sy, appliedYears.ey);
                syncManualPeriodButtons();
                refreshPowerDemandSummaryLayout();
            }
            bar.addEventListener("click", function (e) {
                var btn = e.target.closest("button[data-coeff-seg]");
                if (!btn) {
                    return;
                }
                var seg = btn.getAttribute("data-coeff-seg");
                if (!seg) {
                    return;
                }
                var next = { reporting: false, medium: false, long: false };
                next[seg] = true;
                if (seg === "long") {
                    next.medium = true;
                }
                write(next);
                if (seg === "medium" && !mediumLoaded) {
                    exitManualToSegments({ medium: true });
                    return;
                }
                if (seg === "long" && !longLoaded) {
                    exitManualToSegments({ medium: true, long: true });
                    return;
                }
                exitManualToSegments(next);
            });
            return;
        }

        var state = read();
        if (!mediumLoaded) {
            state.medium = false;
        }
        if (!longLoaded) {
            state.long = false;
        }
        apply(state);
        if (longLoaded) {
            try {
                var currentUrl = new URL(window.location.href);
                if (currentUrl.searchParams.has("coeff_include_long")) {
                    currentUrl.searchParams.delete("coeff_include_long");
                    var cleanedSearch = currentUrl.searchParams.toString();
                    var cleanedUrl = currentUrl.pathname + (cleanedSearch ? "?" + cleanedSearch : "") + currentUrl.hash;
                    window.history.replaceState(window.history.state, "", cleanedUrl);
                }
            } catch (e3) { /* */ }
        }

        bar.addEventListener("click", function (e) {
            var btn = e.target.closest("button[data-coeff-seg]");
            if (!btn) {
                return;
            }
            var seg = btn.getAttribute("data-coeff-seg");
            if (!seg || !Object.prototype.hasOwnProperty.call(state, seg)) {
                return;
            }
            if (seg === "medium" && !mediumLoaded) {
                if (state.medium === false) {
                    state.medium = true;
                    write(state);
                    var um = new URL(window.location.href);
                    um.searchParams.set("pd_medium", "1");
                    window.location.href = um.toString();
                }
                return;
            }
            if (seg === "long" && !longLoaded) {
                if (state.long === false) {
                    state.long = true;
                    state.medium = true;
                    write(state);
                    var u = new URL(window.location.href);
                    u.searchParams.set("coeff_include_long", "1");
                    window.location.href = u.toString();
                }
                return;
            }
            state[seg] = !state[seg];
            write(state);
            apply(state);
        });
    })();



    (function initPowerDemandCoeffManualSourceUi() {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.classList.contains("pd-coeff-year-seg-table")) {
            return;
        }
        var STORAGE_KEY = "pdCoeffMixinRowUiV1";

        function readAll() {
            try {
                var raw = sessionStorage.getItem(STORAGE_KEY);
                return raw ? JSON.parse(raw) : {};
            } catch (e1) {
                return {};
            }
        }

        function writeAll(obj) {
            try {
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
            } catch (e2) { /* */ }
        }

        function pageNs() {
            var view = table.getAttribute("data-summary-view") || "";
            return view + "\n" + window.location.pathname;
        }

        function getBranch(all) {
            var ns = pageNs();
            if (!all[ns] || typeof all[ns] !== "object") {
                all[ns] = {};
            }
            return all[ns];
        }

        function persistRow(rowKey, manualVal, sourceVal) {
            var all = readAll();
            var br = getBranch(all);
            br[rowKey] = { manual: manualVal, source: sourceVal };
            writeAll(all);
        }

        function applyRow(tr) {
            var rowKey = tr.getAttribute("data-pd-coeff-ui-key");
            if (!rowKey) {
                return;
            }
            var inp = tr.querySelector("input.pd-coeff-manual-input");
            var sel = tr.querySelector("select.pd-coeff-source-select");
            if (!inp || !sel) {
                return;
            }
            var all = readAll();
            var br = getBranch(all);
            var st = br[rowKey];
            var sourceRestored = false;
            if (st && typeof st === "object") {
                if (typeof st.manual === "string") {
                    inp.value = st.manual;
                }
                var src = st.source;
                if (src === "gs10" || src === "gs10trim") {
                    src = "gs5";
                }
                if (src === "gs5" || src === "sample" || src === "manual") {
                    sel.value = src;
                    sourceRestored = true;
                    if (st.source === "gs10" || st.source === "gs10trim") {
                        persistRow(rowKey, String(inp.value || ""), "gs5");
                    }
                }
            }
            if (!sourceRestored) {
                sel.value = "gs5";
            }
        }

        window.applyPdCoeffMixinRowSession = function () {
            table.querySelectorAll("tr.summary-row-coeff-k[data-pd-coeff-ui-key]").forEach(applyRow);
        };

        table.addEventListener("input", function (e) {
            var t = e.target;
            if (!t || !t.classList || !t.classList.contains("pd-coeff-manual-input")) {
                return;
            }
            var tr = t.closest("tr[data-pd-coeff-ui-key]");
            if (!tr) {
                return;
            }
            var rowKey = tr.getAttribute("data-pd-coeff-ui-key");
            var sel = tr.querySelector("select.pd-coeff-source-select");
            if (!rowKey || !sel) {
                return;
            }
            persistRow(rowKey, String(t.value || ""), sel.value);
        });

        table.addEventListener("change", function (e) {
            var t = e.target;
            if (!t || !t.classList || !t.classList.contains("pd-coeff-source-select")) {
                return;
            }
            var tr = t.closest("tr[data-pd-coeff-ui-key]");
            if (!tr) {
                return;
            }
            var rowKey = tr.getAttribute("data-pd-coeff-ui-key");
            var inp = tr.querySelector("input.pd-coeff-manual-input");
            if (!rowKey || !inp) {
                return;
            }
            tr.querySelectorAll("input.pd-coeff-medium-k-input").forEach(function (kinp) {
                kinp.removeAttribute("data-pd-medium-k-override");
                /* Смена «используемого k» — пересчитать превью, в т.ч. поверх ранее сохранённых. */
                kinp.removeAttribute("data-pd-medium-k-stored");
            });
            persistRow(rowKey, String(inp.value || ""), t.value);
            if (typeof window.refreshPowerDemandCoeffMixins === "function") {
                window.refreshPowerDemandCoeffMixins();
            }
        });
    })();

    (function initPowerDemandCoeffSampleYears() {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.classList.contains("pd-coeff-year-seg-table")) {
            return;
        }

        function getRoundingDigits() {
            var raw = table.getAttribute("data-pd-rounding-digits") || table.getAttribute("data-rounding-digits") || "1";
            var n = parseInt(raw, 10);
            if (n === -1 || n === 0 || n === 1 || n === 2 || n === 3) {
                return n;
            }
            return 1;
        }

        function getRoundingDigitsK() {
            var raw = table.getAttribute("data-pd-rounding-digits-k") || "3";
            var n = parseInt(raw, 10);
            if (n === -1 || n === 0 || n === 1 || n === 2 || n === 3) {
                return n;
            }
            return 3;
        }

        var COEFF_K_CALC_DECIMAL_PLACES = 6;
        var CALCULATED_MAX_ROUNDING_DIGITS = 3;
        var CALCULATED_MAX_PARAMETER_KEYS = {
            calculated_max_power_mw: true,
            calculated_max_fo_mw: true,
            calculated_max_sa_mw: true,
            calculated_combined_on_cz_mw: true,
            calculated_combined_on_ees_mw: true,
            calculated_max_ees_via_oes_mw: true,
            calculated_max_ees_via_es_mw: true,
            calculated_max_ees_via_ez_mw: true
        };

        function getRoundingDigitsForParameter(pk) {
            if (CALCULATED_MAX_PARAMETER_KEYS[pk]) {
                return CALCULATED_MAX_ROUNDING_DIGITS;
            }
            return getRoundingDigits();
        }

        /** Пробел между каждыми тремя цифрами целой части (как max_power / Excel ru-RU). */
        function applyThousandGrouping(s) {
            if (!s) {
                return s;
            }
            var sign = "";
            if (s.charAt(0) === "-") {
                sign = "-";
                s = s.slice(1);
            }
            var comma = s.indexOf(",");
            var intPart = comma === -1 ? s : s.slice(0, comma);
            var frac = comma === -1 ? null : s.slice(comma + 1);
            intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
            return sign + (frac !== null ? intPart + "," + frac : intPart);
        }

        /** Расчётные максимумы: до 3 знаков после запятой, без лишних нулей, с разделением разрядов. */
        function formatCalculatedMaxMw(num) {
            if (!Number.isFinite(num)) {
                return "—";
            }
            var mult = Math.pow(10, CALCULATED_MAX_ROUNDING_DIGITS);
            var rounded = Math.round(num * mult) / mult;
            var s = String(rounded);
            if (s.indexOf("e") !== -1 || s.indexOf("E") !== -1) {
                s = rounded.toFixed(CALCULATED_MAX_ROUNDING_DIGITS);
            }
            var parts = s.split(".");
            var intPart = applyThousandGrouping(parts[0]);
            if (parts.length === 1) {
                return intPart;
            }
            var frac = parts[1].replace(/0+$/, "");
            return frac.length ? intPart + "," + frac : intPart;
        }

        function formatMwForParameter(num, pk) {
            if (CALCULATED_MAX_PARAMETER_KEYS[pk]) {
                return formatCalculatedMaxMw(num);
            }
            return formatAvg(num, getRoundingDigits());
        }

        /** k = МВт / макс. мощность: не более 6 знаков после запятой (без float-хвоста вроде 0,998999999…). */
        function roundCoeffKCalc(n) {
            if (!Number.isFinite(n)) {
                return n;
            }
            return Number(n.toFixed(COEFF_K_CALC_DECIMAL_PLACES));
        }

        /** Строка k для title/value: ≤ 6 знаков, без хвостовых нулей (0,999 → «0,999», не «0,998999999…»). */
        function formatCoeffKExactString(n) {
            if (!Number.isFinite(n)) {
                return "";
            }
            var s = roundCoeffKCalc(n).toFixed(COEFF_K_CALC_DECIMAL_PLACES);
            if (s.indexOf(".") !== -1) {
                s = s.replace(/0+$/, "").replace(/\.$/, "");
            }
            return s.replace(".", ",");
        }

        /** Отображение коэффициента k: не более 6 знаков, затем «Округл (k)». */
        function formatCoeffK(avg, rd) {
            var n = roundCoeffKCalc(avg);
            if (!Number.isFinite(n)) {
                return "—";
            }
            if (rd === 0) {
                // «Не округлять» — до 6 знаков, без хвостовых нулей и без binary float.
                return formatCoeffKExactString(n) || "—";
            }
            return formatAvg(n, rd);
        }

        function setCoeffKCellFullTitle(el, rawValue) {
            if (!el) {
                return;
            }
            if (rawValue === null || rawValue === undefined || !Number.isFinite(rawValue)) {
                el.removeAttribute("title");
                return;
            }
            var t = formatCoeffKExactString(rawValue);
            if (t) {
                el.setAttribute("title", t);
            } else {
                el.removeAttribute("title");
            }
        }

        /** Полное число для title (значащие знаки; без toFixed(20) — иначе 0,999 → 0,998999999…). */
        function formatNumberFullForTooltip(n) {
            if (n === null || n === undefined || !Number.isFinite(n)) {
                return "";
            }
            if (n === 0) {
                return "0";
            }
            var s = n.toFixed(12);
            if (s.indexOf(".") !== -1) {
                s = s.replace(/0+$/, "").replace(/\.$/, "");
            }
            return s.replace(".", ",");
        }

        function setNumericCellFullTitle(el, rawValue) {
            if (!el) {
                return;
            }
            var t = formatNumberFullForTooltip(rawValue);
            if (t) {
                el.setAttribute("title", t);
            } else {
                el.removeAttribute("title");
            }
        }

        /** Годы «произвольной выборки»: отмеченные чекбоксы в выпадающем фильтре; если их нет в разметке — из URL. */
        function selectedSampleYears() {
            var out = [];
            var seen = {};
            var inputs = table.querySelectorAll('input[name="coeff_sample_years"]');
            var useInputs = inputs.length > 0;
            if (useInputs) {
                Array.prototype.forEach.call(inputs, function (inp) {
                    if (!inp.checked) {
                        return;
                    }
                    var y = parseInt(String(inp.value), 10);
                    if (!Number.isFinite(y) || seen[y]) {
                        return;
                    }
                    seen[y] = true;
                    out.push(y);
                });
            } else {
                var params = new URLSearchParams(window.location.search);
                params.getAll("coeff_sample_years").forEach(function (s) {
                    var y2 = parseInt(String(s), 10);
                    if (!Number.isFinite(y2) || seen[y2]) {
                        return;
                    }
                    seen[y2] = true;
                    out.push(y2);
                });
            }
            out.sort(function (a, b) { return a - b; });
            return out;
        }

        function parseCellNumber(td) {
            if (td.classList.contains("summary-plan-empty")) {
                return null;
            }
            var inp = td.querySelector("input, textarea");
            var t = inp ? String(inp.value || "").trim() : String(td.textContent || "").trim();
            if (t === "" || t === "—") {
                return null;
            }
            var n = parseFloat(t.replace(/\s/g, "").replace(",", "."));
            return Number.isFinite(n) ? n : null;
        }

        /** Полное число из title (как у setNumericCellFullTitle / formatNumberFullForTooltip), иначе null. */
        function parseFullNumericFromTitle(el) {
            if (!el) {
                return null;
            }
            var title = el.getAttribute("title");
            if (!title) {
                return null;
            }
            var t = String(title).trim().replace(/\s/g, "");
            if (!t || t === "—") {
                return null;
            }
            if (!/^-?\d+([.,]\d+)?$/.test(t)) {
                return null;
            }
            var n = parseFloat(t.replace(",", "."));
            return Number.isFinite(n) ? n : null;
        }

        function formatAvg(avg, rd) {
            if (!Number.isFinite(avg)) {
                return "—";
            }
            if (rd === -1) {
                return applyThousandGrouping(String(Math.round(avg)));
            }
            if (rd === 0) {
                var s = String(avg);
                if (s.indexOf(".") !== -1) {
                    s = s.replace(".", ",");
                }
                return applyThousandGrouping(s);
            }
            var mult = Math.pow(10, rd);
            var rounded = Math.round(avg * mult) / mult;
            return applyThousandGrouping(rounded.toFixed(rd).replace(".", ","));
        }

        /** Строка k для показателя МВт (может идти после «Проверка …»). */
        function coeffKRowForMwTr(mwTr) {
            if (!mwTr) {
                return null;
            }
            var pk = mwTr.getAttribute("data-parameter-key") || "";
            if (pk === "max_power") {
                return null;
            }
            var nx = mwTr.nextElementSibling;
            while (
                nx &&
                nx.classList.contains("summary-row-param") &&
                nx.classList.contains("pd-pd-verify-for-row")
            ) {
                var aKey = nx.getAttribute("data-pd-pd-verify-a") || "";
                var vPk = nx.getAttribute("data-parameter-key") || "";
                if (aKey === pk || vPk === "verify_for_" + pk) {
                    nx = nx.nextElementSibling;
                    continue;
                }
                break;
            }
            if (nx && nx.classList.contains("summary-row-coeff-k")) {
                if ((nx.getAttribute("data-parameter-key") || "") === pk) {
                    return nx;
                }
            }
            return null;
        }

        /** Строка k с итогами «Расчетный коэффициент совмещения». */
        function coeffMixinTrForMwTr(mwTr) {
            return coeffKRowForMwTr(mwTr);
        }

        /** Строки одного блока «энергосистема + показатели» (только МВт-строки; k — отдельные <tr>). */
        function entityBlockFromRow(tr) {
            var row = tr;
            if (row && row.classList.contains("summary-row-coeff-k")) {
                var kPk = row.getAttribute("data-parameter-key") || "";
                var prevK = row.previousElementSibling;
                while (prevK) {
                    if (
                        prevK.matches("tr.summary-row-param") &&
                        (prevK.getAttribute("data-parameter-key") || "") === kPk
                    ) {
                        row = prevK;
                        break;
                    }
                    if (
                        prevK.classList.contains("summary-row-coeff-k") ||
                        prevK.classList.contains("pd-pd-verify-for-row")
                    ) {
                        prevK = prevK.previousElementSibling;
                        continue;
                    }
                    break;
                }
            }
            while (row && row.matches("tr.summary-row-param")) {
                if (
                    row.getAttribute("data-is-block-start") === "1" &&
                    !row.classList.contains("pd-pd-verify-for-row")
                ) {
                    break;
                }
                var prev = row.previousElementSibling;
                while (prev && prev.classList.contains("summary-row-coeff-k")) {
                    prev = prev.previousElementSibling;
                }
                if (!prev || !prev.matches("tr.summary-row-param")) {
                    break;
                }
                row = prev;
            }
            if (!row || !row.matches("tr.summary-row-param")) {
                return [];
            }
            var block = [];
            var x = row;
            while (x) {
                if (x.matches("tr.summary-row-param")) {
                    if (
                        x.classList.contains("pd-pd-verify-for-row") &&
                        x.getAttribute("data-is-block-start") === "1"
                    ) {
                        x.removeAttribute("data-is-block-start");
                    }
                    block.push(x);
                }
                var nx = x.nextElementSibling;
                if (!nx) {
                    break;
                }
                if (
                    nx.getAttribute("data-is-block-start") === "1" &&
                    !nx.classList.contains("pd-pd-verify-for-row")
                ) {
                    break;
                }
                x = nx;
            }
            return block;
        }

        function findBlockMaxPowerTr(block) {
            for (var i = 0; i < block.length; i++) {
                if (block[i].getAttribute("data-parameter-key") === "max_power") {
                    return block[i];
                }
            }
            return null;
        }

        function parseManualCoeffInput(val) {
            var t = String(val || "").trim();
            if (!t || t === "—") {
                return null;
            }
            var n = parseFloat(t.replace(/\s/g, "").replace(",", "."));
            return Number.isFinite(n) ? roundCoeffKCalc(n) : null;
        }

        /** Как :func:`_coeff_union_res_sum_year` (отчётный N−9…N и среднесрочный N+1…N+6). */
        function coeffUnionResSumYear(y, n) {
            return (y >= n - 9 && y <= n) || (y >= n + 1 && y <= n + 6);
        }

        function isCoeffResSumCalcMaxRow(tr) {
            var dm = tr.getAttribute("data-demand-model-name") || "";
            var pk = tr.getAttribute("data-parameter-key") || "";
            if (dm === "UnionEnergySystemDemandParameter") {
                return pk === "calculated_max_power_mw" || pk === "calculated_combined_on_ees_mw";
            }
            if (dm === "FederalDistrictDemandParameter") {
                return pk === "calculated_max_power_mw" || pk === "calculated_combined_on_cz_mw";
            }
            if (dm === "EnergyZoneDemandParameter") {
                return pk === "calculated_max_power_mw" || pk === "calculated_combined_on_ees_mw";
            }
            return false;
        }

        function trGroupId(tr, dataAttr, parentFk) {
            var v = tr.getAttribute(dataAttr);
            if (v) {
                return v;
            }
            if (parentFk && tr.getAttribute("data-parent-fk-column") === parentFk) {
                return tr.getAttribute("data-parent-id") || "";
            }
            return "";
        }

        /**
         * Расчётные максимумы ОЭС/ФО/ЭЗ = суммы совмещённых показателей по строкам РЭС
         * (после fillAndSync среднесрочные МВт РЭС уже k×max; сервер то же в enrich_summary_rows_coeff_k_columns).
         */
        function refreshCoeffAggregatedMwFromRes() {
            var view = table.getAttribute("data-summary-view") || "";
            if (view !== "oes" && view !== "fo" && view !== "ez") {
                return;
            }
            var nRaw = table.getAttribute("data-coeff-base-year");
            var n = nRaw ? parseInt(String(nRaw), 10) : NaN;
            if (!Number.isFinite(n)) {
                return;
            }
            var sumsOes = {};
            var sumsEesByUes = {};
            var sumsFo = {};
            var sumsCz = {};
            var sumsEz = {};
            var sumsEesByEz = {};
            table
                .querySelectorAll('tr[data-demand-model-name="RegionalEnergySystemDemandParameter"]')
                .forEach(function (rTr) {
                var pk0 = rTr.getAttribute("data-parameter-key") || "";
                var store = null;
                var gid = "";
                if (view === "oes") {
                    if (pk0 === "combined_on_oes") {
                        store = sumsOes;
                        gid = trGroupId(rTr, "data-id-union-energy-system", "id_union_energy_system");
                    } else if (pk0 === "combined_on_ees") {
                        store = sumsEesByUes;
                        gid = trGroupId(rTr, "data-id-union-energy-system", "id_union_energy_system");
                    }
                } else if (view === "fo") {
                    if (pk0 === "combined_on_fo") {
                        store = sumsFo;
                        gid = trGroupId(rTr, "data-id-federal-district", "id_federal_district");
                    } else if (pk0 === "combined_on_cz") {
                        store = sumsCz;
                        gid = trGroupId(rTr, "data-id-federal-district", "id_federal_district");
                    }
                } else if (view === "ez") {
                    if (rTr.getAttribute("data-pd-pd-ez-res-fully-in-zone") === "0") {
                        return;
                    }
                    if (pk0 === "combined_on_ez") {
                        store = sumsEz;
                        gid = trGroupId(rTr, "data-id-energy-zone", "id_energy_zone");
                    } else if (pk0 === "combined_on_ees") {
                        store = sumsEesByEz;
                        gid = trGroupId(rTr, "data-id-energy-zone", "id_energy_zone");
                    }
                }
                if (!store || !gid) {
                    return;
                }
                rTr.querySelectorAll("td.summary-year-mw-cell[data-summary-year]").forEach(function (mwCell) {
                    if (mwCell.classList.contains("summary-plan-empty")) {
                        return;
                    }
                    var y = parseInt(String(mwCell.getAttribute("data-summary-year") || ""), 10);
                    if (!Number.isFinite(y) || !coeffUnionResSumYear(y, n)) {
                        return;
                    }
                    var v = parseCellNumber(mwCell);
                    if (v === null) {
                        return;
                    }
                    var key = gid + "\u0000" + y;
                    if (!store[key]) {
                        store[key] = 0;
                    }
                    store[key] += v;
                });
            });
            function applyAggPk(dm, pk, store, dataAttr, parentFk) {
                table.querySelectorAll('tr[data-demand-model-name="' + dm + '"][data-parameter-key="' + pk + '"]').forEach(function (uTr) {
                    var gid = trGroupId(uTr, dataAttr, parentFk);
                    if (!gid) {
                        return;
                    }
                    uTr.querySelectorAll("td.summary-year-mw-cell[data-summary-year]").forEach(function (mwCell) {
                        if (mwCell.classList.contains("summary-plan-empty")) {
                            return;
                        }
                        var y = parseInt(String(mwCell.getAttribute("data-summary-year") || ""), 10);
                        if (!Number.isFinite(y) || !coeffUnionResSumYear(y, n)) {
                            return;
                        }
                        var total = store[gid + "\u0000" + y];
                        var disp = total === undefined ? "—" : formatMwForParameter(total, pk);
                        var inp = mwCell.querySelector("input.pd-coeff-display-mw");
                        if (inp) {
                            inp.value = disp;
                            if (total === undefined) {
                                inp.removeAttribute("title");
                                mwCell.removeAttribute("title");
                            } else {
                                setNumericCellFullTitle(inp, total);
                                setNumericCellFullTitle(mwCell, total);
                            }
                            return;
                        }
                        mwCell.textContent = disp;
                        if (total === undefined) {
                            mwCell.removeAttribute("title");
                        } else {
                            setNumericCellFullTitle(mwCell, total);
                        }
                    });
                });
            }
            if (view === "oes") {
                applyAggPk(
                    "UnionEnergySystemDemandParameter",
                    "calculated_max_power_mw",
                    sumsOes,
                    "data-id-union-energy-system",
                    "id_union_energy_system"
                );
                applyAggPk(
                    "UnionEnergySystemDemandParameter",
                    "calculated_combined_on_ees_mw",
                    sumsEesByUes,
                    "data-id-union-energy-system",
                    "id_union_energy_system"
                );
            } else if (view === "fo") {
                applyAggPk(
                    "FederalDistrictDemandParameter",
                    "calculated_max_power_mw",
                    sumsFo,
                    "data-id-federal-district",
                    "id_federal_district"
                );
                applyAggPk(
                    "FederalDistrictDemandParameter",
                    "calculated_combined_on_cz_mw",
                    sumsCz,
                    "data-id-federal-district",
                    "id_federal_district"
                );
            } else if (view === "ez") {
                applyAggPk(
                    "EnergyZoneDemandParameter",
                    "calculated_max_power_mw",
                    sumsEz,
                    "data-id-energy-zone",
                    "id_energy_zone"
                );
                applyAggPk(
                    "EnergyZoneDemandParameter",
                    "calculated_combined_on_ees_mw",
                    sumsEesByEz,
                    "data-id-energy-zone",
                    "id_energy_zone"
                );
            }
        }

        function refreshOesUesAggregatedMwFromRes() {
            refreshCoeffAggregatedMwFromRes();
        }

        /** Строки «Проверка …»: a − b по годам, включая плановые (среднесрочные). */
        function refreshCoeffVerifyRows() {
            table.querySelectorAll("tr.pd-pd-verify-for-row").forEach(function (vTr) {
                var aKey = vTr.getAttribute("data-pd-pd-verify-a");
                var bKey = vTr.getAttribute("data-pd-pd-verify-b");
                if (!aKey || !bKey) {
                    return;
                }
                var block = entityBlockFromRow(vTr);
                var aTr = null;
                var bTr = null;
                for (var i = 0; i < block.length; i++) {
                    var pk = block[i].getAttribute("data-parameter-key") || "";
                    if (pk === aKey) {
                        aTr = block[i];
                    }
                    if (pk === bKey) {
                        bTr = block[i];
                    }
                }
                if (!aTr || !bTr) {
                    return;
                }
                vTr.querySelectorAll("td.summary-year-mw-cell[data-summary-year]").forEach(function (vCell) {
                    var y = vCell.getAttribute("data-summary-year");
                    if (!y) {
                        return;
                    }
                    var aCell = aTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                    var bCell = bTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                    if (!aCell || !bCell) {
                        return;
                    }
                    if (
                        aCell.classList.contains("summary-plan-empty") ||
                        bCell.classList.contains("summary-plan-empty")
                    ) {
                        return;
                    }
                    var av = parseCellNumber(aCell);
                    var bv = parseCellNumber(bCell);
                    var inp = vCell.querySelector("input.pd-coeff-display-mw, input.fuel-param-input");
                    if (av === null || bv === null) {
                        if (inp) {
                            inp.value = "—";
                            inp.removeAttribute("title");
                        } else {
                            vCell.textContent = "—";
                        }
                        vCell.removeAttribute("title");
                        return;
                    }
                    var d = av - bv;
                    var disp = formatAvg(d, -1);
                    if (inp) {
                        inp.value = disp;
                        setNumericCellFullTitle(inp, d);
                    } else {
                        vCell.textContent = disp;
                    }
                    setNumericCellFullTitle(vCell, d);
                });
            });
        }

        function getCoeffSourceNumber(mwTr) {
            var mixinTr = coeffMixinTrForMwTr(mwTr);
            if (!mixinTr) {
                return null;
            }
            var sel = mixinTr.querySelector("select.pd-coeff-source-select");
            if (!sel) {
                return null;
            }
            var src = sel.value;
            if (src === "gs10" || src === "gs10trim") {
                src = "gs5";
            }
            var td;
            if (src === "gs5") {
                td = mixinTr.querySelector("td.summary-coeff-gs5-cell");
            } else if (src === "sample") {
                td = mixinTr.querySelector("td.summary-coeff-sample-cell");
            } else if (src === "manual") {
                var minp = mixinTr.querySelector("input.pd-coeff-manual-input");
                return minp ? parseManualCoeffInput(minp.value) : null;
            } else {
                return null;
            }
            if (!td) {
                return null;
            }
            var fromTitle = parseFullNumericFromTitle(td);
            if (fromTitle !== null) {
                return roundCoeffKCalc(fromTitle);
            }
            var fromCell = parseCellNumber(td);
            return fromCell !== null ? roundCoeffKCalc(fromCell) : null;
        }

        function mwTrFromCoeffControl(el) {
            var tr = el && el.closest ? el.closest("tr") : null;
            if (tr && tr.classList.contains("summary-row-coeff-k")) {
                var kPk = tr.getAttribute("data-parameter-key") || "";
                var prev = tr.previousElementSibling;
                while (prev) {
                    if (
                        prev.matches("tr.summary-row-param") &&
                        (prev.getAttribute("data-parameter-key") || "") === kPk
                    ) {
                        return prev;
                    }
                    if (
                        prev.classList.contains("summary-row-coeff-k") ||
                        prev.classList.contains("pd-pd-verify-for-row")
                    ) {
                        prev = prev.previousElementSibling;
                        continue;
                    }
                    break;
                }
            }
            return el && el.closest ? el.closest("tr.summary-row-param") : null;
        }

        function syncMediumMwFromKRow(tr) {
            var pk = tr.getAttribute("data-parameter-key") || "";
            if ((pk || "").indexOf("cz_total_") === 0) {
                return;
            }
            if (pk === "max_power" || pk === "peak_datetime" || pk === "avg_temp") {
                return;
            }
            if (isCoeffResSumCalcMaxRow(tr)) {
                return;
            }
            var block = entityBlockFromRow(tr);
            var maxTr = findBlockMaxPowerTr(block);
            var rd = getRoundingDigits();
            var kTr = coeffKRowForMwTr(tr) || tr;
            kTr.querySelectorAll('.summary-year-k-cell[data-coeff-year-segment="medium"]').forEach(function (kCell) {
                if (kCell.classList.contains("summary-plan-empty")) {
                    return;
                }
                var y = kCell.getAttribute("data-summary-year");
                if (!y) {
                    return;
                }
                var mwCell = tr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                if (!mwCell || mwCell.classList.contains("summary-plan-empty")) {
                    return;
                }
                var mwInp = mwCell.querySelector("input.fuel-param-input, textarea.fuel-param-input");
                var kNum = parseFullNumericFromTitle(kCell);
                if (kNum === null) {
                    var kinp0 = kCell.querySelector("input.pd-coeff-medium-k-input");
                    kNum = kinp0 ? parseFullNumericFromTitle(kinp0) : null;
                }
                if (kNum === null) {
                    kNum = parseCellNumber(kCell);
                }
                if (kNum !== null) {
                    kNum = roundCoeffKCalc(kNum);
                }
                var maxMw = null;
                if (maxTr) {
                    var maxMwCell = maxTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                    if (maxMwCell) {
                        maxMw = parseCellNumber(maxMwCell);
                    }
                }
                if (kNum === null || maxMw === null || maxMw <= 0) {
                    return;
                }
                var mw = kNum * maxMw;
                var mwDisp = formatAvg(mw, rd);
                if (mwInp) {
                    mwInp.value = mwDisp;
                    setNumericCellFullTitle(mwInp, mw);
                } else {
                    mwCell.textContent = mwDisp;
                    setNumericCellFullTitle(mwCell, mw);
                }
            });
        }

        function fillAndSyncMediumFromUsedCoeff() {
            var rd = getRoundingDigitsK();
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                var pk = tr.getAttribute("data-parameter-key") || "";
                if ((pk || "").indexOf("cz_total_") === 0) {
                    return;
                }
                if (pk === "peak_datetime" || pk === "avg_temp") {
                    var kTrEmpty = coeffKRowForMwTr(tr) || tr;
                    kTrEmpty.querySelectorAll('.summary-year-k-cell[data-coeff-year-segment="medium"]').forEach(function (kCell) {
                        var kinp = kCell.querySelector("input.pd-coeff-medium-k-input");
                        if (kinp) {
                            kinp.value = "";
                            kinp.removeAttribute("title");
                        } else {
                            kCell.textContent = "—";
                        }
                        kCell.removeAttribute("title");
                    });
                    return;
                }
                if (pk === "max_power") {
                    return;
                }
                var coeff = getCoeffSourceNumber(tr);
                var kTrFill = coeffKRowForMwTr(tr) || tr;
                kTrFill.querySelectorAll('.summary-year-k-cell[data-coeff-year-segment="medium"]').forEach(function (kCell) {
                    /* Строки «Расчетный …» УЭС: k задаётся МВт/макс (refreshCoeffYearKCells), не из выпадающего «используемого k». */
                    if (kCell.querySelector("input.pd-coeff-display-k") || isCoeffResSumCalcMaxRow(tr)) {
                        return;
                    }
                    /* Плановые годы (пустые МВт): k в среднесрочном периоде всё равно показываем из выбранного коэффициента. */
                    var kinp = kCell.querySelector("input.pd-coeff-medium-k-input");
                    if (kinp) {
                        if (kinp.getAttribute("data-pd-medium-k-override") === "1") {
                            return;
                        }
                        if (document.activeElement === kinp) {
                            return;
                        }
                        /* По умолчанию и при выборе в «используемый k» — значение из источника
                           (СиПР 5 лет / период / ручной ввод), а не «сырой» k из БД. */
                        kinp.removeAttribute("data-pd-medium-k-stored");
                        if (coeff === null) {
                            kinp.value = "";
                            kinp.setAttribute("data-initial", "");
                            kinp.removeAttribute("title");
                            kCell.removeAttribute("title");
                        } else {
                            var coeffR = roundCoeffKCalc(coeff);
                            var coeffDisp = formatCoeffK(coeffR, rd);
                            kinp.value = coeffDisp;
                            kinp.setAttribute("data-initial", coeffDisp);
                            setCoeffKCellFullTitle(kCell, coeffR);
                            setCoeffKCellFullTitle(kinp, coeffR);
                        }
                    } else {
                        if (coeff === null) {
                            kCell.textContent = "—";
                            kCell.removeAttribute("title");
                        } else {
                            var coeffR2 = roundCoeffKCalc(coeff);
                            kCell.textContent = formatCoeffK(coeffR2, rd);
                            setCoeffKCellFullTitle(kCell, coeffR2);
                        }
                    }
                });
                syncMediumMwFromKRow(tr);
            });
        }

        function updateMediumKFromMwInput(mwInp) {
            var mwCell = mwInp.closest("td.summary-year-mw-cell");
            if (!mwCell || mwCell.getAttribute("data-coeff-year-segment") !== "medium") {
                return;
            }
            var tr = mwInp.closest("tr.summary-row-param");
            if (!tr) {
                return;
            }
            var pk = tr.getAttribute("data-parameter-key") || "";
            if ((pk || "").indexOf("cz_total_") === 0) {
                return;
            }
            if (pk === "max_power" || pk === "peak_datetime" || pk === "avg_temp") {
                return;
            }
            var y = mwCell.getAttribute("data-summary-year");
            if (!y) {
                return;
            }
            var block = entityBlockFromRow(tr);
            var maxTr = findBlockMaxPowerTr(block);
            var maxMw = null;
            if (maxTr) {
                var maxMwCell = maxTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                if (maxMwCell) {
                    maxMw = parseCellNumber(maxMwCell);
                }
            }
            var mw = parseCellNumber(mwCell);
            var kTrUpd = coeffKRowForMwTr(tr) || tr;
            var kCell = kTrUpd.querySelector('.summary-year-k-cell[data-summary-year="' + y + '"]');
            var kinp = kCell && kCell.querySelector("input.pd-coeff-medium-k-input");
            if (!kinp) {
                return;
            }
            var rd = getRoundingDigitsK();
            if (mw !== null && maxMw !== null && maxMw > 0) {
                var rat = roundCoeffKCalc(mw / maxMw);
                kinp.value = formatCoeffK(rat, rd);
                setCoeffKCellFullTitle(kCell, rat);
                setCoeffKCellFullTitle(kinp, rat);
            } else {
                kinp.value = "";
                kinp.removeAttribute("title");
                kCell.removeAttribute("title");
            }
            kinp.setAttribute("data-pd-medium-k-override", "1");
        }

        /** Обновить значение k в ячейке (текстовое содержимое или readonly input.pd-coeff-display-k). */
        function setYearKCellDisplay(kCell, displayText, fullTooltipNum) {
            if (!kCell) {
                return;
            }
            var kinp = kCell.querySelector("input.pd-coeff-display-k");
            if (kinp) {
                kinp.value = displayText;
                if (displayText === "—") {
                    kinp.removeAttribute("title");
                    kCell.removeAttribute("title");
                } else if (fullTooltipNum !== undefined && fullTooltipNum !== null && typeof fullTooltipNum === "number" && Number.isFinite(fullTooltipNum)) {
                    setCoeffKCellFullTitle(kinp, fullTooltipNum);
                    setCoeffKCellFullTitle(kCell, fullTooltipNum);
                }
                return;
            }
            kCell.textContent = displayText;
            if (displayText === "—") {
                kCell.removeAttribute("title");
            } else if (fullTooltipNum !== undefined && fullTooltipNum !== null && typeof fullTooltipNum === "number" && Number.isFinite(fullTooltipNum)) {
                setCoeffKCellFullTitle(kCell, fullTooltipNum);
            } else {
                kCell.removeAttribute("title");
            }
        }

        /** Пересчёт k = МВт / макс. мощность года после правок ячеек. */
        function refreshCoeffYearKCells() {
            var rd = getRoundingDigitsK();
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                if (tr.getAttribute("data-is-block-start") !== "1") {
                    return;
                }
                var block = entityBlockFromRow(tr);
                var maxTr = null;
                for (var bi = 0; bi < block.length; bi++) {
                    if (block[bi].getAttribute("data-parameter-key") === "max_power") {
                        maxTr = block[bi];
                        break;
                    }
                }
                for (var bj = 0; bj < block.length; bj++) {
                    var trb = block[bj];
                    var pk = trb.getAttribute("data-parameter-key") || "";
                    if (pk.indexOf("cz_total_") === 0) {
                        var kTrCz = coeffKRowForMwTr(trb) || trb;
                        kTrCz.querySelectorAll(".summary-year-k-cell[data-summary-year]").forEach(function (kCzCell) {
                            setYearKCellDisplay(kCzCell, "—");
                        });
                        continue;
                    }
                    var kTrRef = coeffKRowForMwTr(trb) || trb;
                    trb.querySelectorAll("td.summary-year-mw-cell[data-summary-year]").forEach(function (mwCell) {
                        var y = mwCell.getAttribute("data-summary-year");
                        if (!y) {
                            return;
                        }
                        var kCell = kTrRef.querySelector('.summary-year-k-cell[data-summary-year="' + y + '"]');
                        if (!kCell) {
                            return;
                        }
                        var seg = mwCell.getAttribute("data-coeff-year-segment") || "";
                        if (mwCell.classList.contains("summary-plan-empty")) {
                            /* Плановые годы: в среднесрочном периоде k заполняется из «используемого коэффициента» (fillAndSync), не затирать. */
                            if (seg === "medium" && pk !== "peak_datetime" && pk !== "avg_temp" && pk !== "max_power") {
                                return;
                            }
                            setYearKCellDisplay(kCell, "—");
                            return;
                        }
                        if (pk === "peak_datetime" || pk === "avg_temp") {
                            setYearKCellDisplay(kCell, "—");
                            return;
                        }
                        if (seg === "medium" && pk !== "max_power") {
                            if (!isCoeffResSumCalcMaxRow(trb)) {
                                return;
                            }
                        }
                        var maxMw = null;
                        if (maxTr) {
                            var maxMwCell = maxTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + y + '"]');
                            if (maxMwCell) {
                                maxMw = parseCellNumber(maxMwCell);
                            }
                        }
                        var val = parseCellNumber(mwCell);
                        if (pk === "max_power") {
                            /* k для строки «Максимум потребления мощности» нигде не считается — всегда прочерк. */
                            setYearKCellDisplay(kCell, "—");
                            return;
                        }
                        if (val !== null && maxMw !== null && maxMw > 0) {
                            var rat = roundCoeffKCalc(val / maxMw);
                            setYearKCellDisplay(kCell, formatCoeffK(rat, rd), rat);
                        } else {
                            setYearKCellDisplay(kCell, "—");
                        }
                    });
                }
            });
        }

        /** Среднее коэффициентов k по годам отчётного периода (10 лет) для столбца «для ГС (10 лет)». */
        function refreshGs10ReportingAvg() {
            var rd = getRoundingDigitsK();
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                var mixinTr = coeffMixinTrForMwTr(tr);
                var gsTd = mixinTr
                    ? mixinTr.querySelector("td.summary-coeff-gs10-cell")
                    : tr.querySelector("td.summary-coeff-gs10-cell");
                if (!gsTd) {
                    return;
                }
                var pkey = tr.getAttribute("data-parameter-key") || "";
                if (pkey === "peak_datetime" || pkey === "max_power" || pkey.indexOf("cz_total_") === 0) {
                    gsTd.textContent = "—";
                    gsTd.removeAttribute("title");
                    return;
                }
                var nums = [];
                var kTrGs = coeffKRowForMwTr(tr) || tr;
                kTrGs.querySelectorAll('.summary-year-k-cell[data-coeff-year-segment="reporting"]').forEach(function (cell) {
                    var n = parseFullNumericFromTitle(cell);
                    if (n === null) {
                        n = parseCellNumber(cell);
                    }
                    if (n !== null) {
                        nums.push(roundCoeffKCalc(n));
                    }
                });
                if (nums.length === 0) {
                    gsTd.textContent = "—";
                    gsTd.removeAttribute("title");
                    return;
                }
                var sum = nums.reduce(function (a, b) {
                    return a + b;
                }, 0);
                var gsAvg = roundCoeffKCalc(sum / nums.length);
                gsTd.textContent = formatCoeffK(gsAvg, rd);
                setCoeffKCellFullTitle(gsTd, gsAvg);
            });
        }

        /**
         * Среднее k по отчётному периоду без одного мин. и одного макс. значения
         * (столбец «для ГС (10 лет без мин и макс)»).
         */
        function refreshGs10ReportingTrimmedAvg() {
            var rd = getRoundingDigitsK();
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                var mixinTr = coeffMixinTrForMwTr(tr);
                var trimTd = mixinTr
                    ? mixinTr.querySelector("td.summary-coeff-gs10-minmax-trim-cell")
                    : tr.querySelector("td.summary-coeff-gs10-minmax-trim-cell");
                if (!trimTd) {
                    return;
                }
                var pkey = tr.getAttribute("data-parameter-key") || "";
                if (pkey === "peak_datetime" || pkey === "max_power" || pkey.indexOf("cz_total_") === 0) {
                    trimTd.textContent = "—";
                    trimTd.removeAttribute("title");
                    return;
                }
                var nums = [];
                var kTrTrim = coeffKRowForMwTr(tr) || tr;
                kTrTrim.querySelectorAll('.summary-year-k-cell[data-coeff-year-segment="reporting"]').forEach(function (cell) {
                    var n = parseFullNumericFromTitle(cell);
                    if (n === null) {
                        n = parseCellNumber(cell);
                    }
                    if (n !== null) {
                        nums.push(roundCoeffKCalc(n));
                    }
                });
                if (nums.length < 3) {
                    trimTd.textContent = "—";
                    trimTd.removeAttribute("title");
                    return;
                }
                var sorted = nums.slice().sort(function (a, b) {
                    return a - b;
                });
                var inner = sorted.slice(1, -1);
                var sum = inner.reduce(function (a, b) {
                    return a + b;
                }, 0);
                var trimAvg = roundCoeffKCalc(sum / inner.length);
                trimTd.textContent = formatCoeffK(trimAvg, rd);
                setCoeffKCellFullTitle(trimTd, trimAvg);
            });
        }

        /** Среднее коэффициентов k по годам N−4 … N (5 лет), N — базовый год отчётного периода. */
        function refreshGs5N4toNAvg() {
            var rd = getRoundingDigitsK();
            var nRaw = table.getAttribute("data-coeff-base-year");
            var n = nRaw ? parseInt(String(nRaw), 10) : NaN;
            if (!Number.isFinite(n)) {
                table.querySelectorAll("td.summary-coeff-gs5-cell").forEach(function (td) {
                    td.textContent = "—";
                    td.removeAttribute("title");
                });
                return;
            }
            var y5 = [];
            for (var d = 4; d >= 0; d--) {
                y5.push(n - d);
            }
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                var mixinTr = coeffMixinTrForMwTr(tr);
                var g5Td = mixinTr
                    ? mixinTr.querySelector("td.summary-coeff-gs5-cell")
                    : tr.querySelector("td.summary-coeff-gs5-cell");
                if (!g5Td) {
                    return;
                }
                var pkey = tr.getAttribute("data-parameter-key") || "";
                if (pkey === "peak_datetime" || pkey === "max_power" || pkey.indexOf("cz_total_") === 0) {
                    g5Td.textContent = "—";
                    g5Td.removeAttribute("title");
                    return;
                }
                var nums = [];
                var kTrG5 = coeffKRowForMwTr(tr) || tr;
                y5.forEach(function (y) {
                    var cell = kTrG5.querySelector('.summary-year-k-cell[data-summary-year="' + y + '"]');
                    if (!cell) {
                        return;
                    }
                    var num = parseFullNumericFromTitle(cell);
                    if (num === null) {
                        num = parseCellNumber(cell);
                    }
                    if (num !== null) {
                        nums.push(roundCoeffKCalc(num));
                    }
                });
                if (nums.length === 0) {
                    g5Td.textContent = "—";
                    g5Td.removeAttribute("title");
                    return;
                }
                var sum5 = nums.reduce(function (a, b) {
                    return a + b;
                }, 0);
                var g5Avg = roundCoeffKCalc(sum5 / nums.length);
                g5Td.textContent = formatCoeffK(g5Avg, rd);
                setCoeffKCellFullTitle(g5Td, g5Avg);
            });
        }

        /** Пересчёт трёх итоговых строк под «ЦЗ России» на coeff/ФО (суммы и небаланс по МВт из текущей таблицы). */
        function refreshFoCoeffCzTotals() {
            if (table.getAttribute("data-summary-view") !== "fo") {
                return;
            }
            if (!table.classList.contains("pd-coeff-year-seg-table")) {
                return;
            }
            var czMaxTr = table.querySelector(
                'tr.summary-kind-centralized_zone[data-parameter-key="max_power"]'
            );
            var r1 = table.querySelector('tr[data-parameter-key="cz_total_sum_fo_max_power"]');
            if (!r1 || !czMaxTr) {
                return;
            }
            var years = [];
            r1.querySelectorAll("td.summary-year-mw-cell[data-summary-year]").forEach(function (td) {
                var ys = td.getAttribute("data-summary-year");
                if (ys && years.indexOf(ys) === -1) {
                    years.push(ys);
                }
            });
            var rd = getRoundingDigits();
            var r2 = table.querySelector('tr[data-parameter-key="cz_total_sum_res_combined_cz"]');
            var r3 = table.querySelector('tr[data-parameter-key="cz_total_imbalance_mw"]');
            function sumMw(selector, yStr) {
                var acc = 0;
                var any = false;
                table.querySelectorAll(selector).forEach(function (tr) {
                    if (tr.classList.contains("summary-row-hidden")) {
                        return;
                    }
                    var c = tr.querySelector('td.summary-year-mw-cell[data-summary-year="' + yStr + '"]');
                    if (!c || c.classList.contains("summary-plan-empty")) {
                        return;
                    }
                    var n = parseCellNumber(c);
                    if (n !== null) {
                        acc += n;
                        any = true;
                    }
                });
                return any ? acc : null;
            }
            function writeOneYear(tr, yStr, num) {
                if (!tr) {
                    return;
                }
                var mwC = tr.querySelector('td.summary-year-mw-cell[data-summary-year="' + yStr + '"]');
                if (!mwC) {
                    return;
                }
                var inp = mwC.querySelector("input.pd-fo-cz-total-mw");
                var disp = num === null || !Number.isFinite(num) ? "—" : formatAvg(num, rd);
                if (inp) {
                    inp.value = disp;
                    if (num === null || !Number.isFinite(num)) {
                        inp.removeAttribute("title");
                        mwC.removeAttribute("title");
                    } else {
                        setNumericCellFullTitle(inp, num);
                        setNumericCellFullTitle(mwC, num);
                    }
                } else {
                    mwC.textContent = disp;
                    if (num === null || !Number.isFinite(num)) {
                        mwC.removeAttribute("title");
                    } else {
                        setNumericCellFullTitle(mwC, num);
                    }
                }
            }
            years.forEach(function (yStr) {
                var sFdMp = sumMw(
                    'tr[data-demand-model-name="FederalDistrictDemandParameter"][data-parameter-key="max_power"]',
                    yStr
                );
                var sResMp = sumMw(
                    'tr[data-demand-model-name="RegionalEnergySystemDemandParameter"][data-parameter-key="max_power"]',
                    yStr
                );
                var sMpFoTree = null;
                if (sFdMp !== null || sResMp !== null) {
                    sMpFoTree = (sFdMp !== null ? sFdMp : 0) + (sResMp !== null ? sResMp : 0);
                }
                var sResCz = sumMw(
                    'tr[data-demand-model-name="RegionalEnergySystemDemandParameter"][data-parameter-key="combined_on_cz"]',
                    yStr
                );
                var czCell = czMaxTr.querySelector('td.summary-year-mw-cell[data-summary-year="' + yStr + '"]');
                var czMw =
                    czCell && !czCell.classList.contains("summary-plan-empty") ? parseCellNumber(czCell) : null;
                writeOneYear(r1, yStr, sMpFoTree);
                writeOneYear(r2, yStr, sResCz);
                var imb =
                    czMw !== null && sResCz !== null && Number.isFinite(czMw) && Number.isFinite(sResCz)
                        ? czMw - sResCz
                        : null;
                writeOneYear(r3, yStr, imb);
            });
        }

        function refresh() {
            if (typeof window.applyPdCoeffMixinRowSession === "function") {
                window.applyPdCoeffMixinRowSession();
            }
            refreshOesUesAggregatedMwFromRes();
            refreshCoeffYearKCells();
            refreshGs10ReportingAvg();
            refreshGs10ReportingTrimmedAvg();
            refreshGs5N4toNAvg();
            var yearsSel = selectedSampleYears();
            var rd = getRoundingDigitsK();
            table.querySelectorAll("tr.summary-row-param").forEach(function (tr) {
                var mixinTr = coeffMixinTrForMwTr(tr);
                var sampleTd = mixinTr
                    ? mixinTr.querySelector("td.summary-coeff-sample-cell")
                    : tr.querySelector("td.summary-coeff-sample-cell");
                if (!sampleTd) {
                    return;
                }
                var pkey = tr.getAttribute("data-parameter-key") || "";
                if (pkey === "peak_datetime" || pkey === "max_power" || pkey.indexOf("cz_total_") === 0) {
                    sampleTd.textContent = "—";
                    sampleTd.removeAttribute("title");
                    return;
                }
                if (yearsSel.length === 0) {
                    sampleTd.textContent = "—";
                    sampleTd.removeAttribute("title");
                    return;
                }
                var nums = [];
                var kTrSamp = coeffKRowForMwTr(tr) || tr;
                yearsSel.forEach(function (y) {
                    var cell = kTrSamp.querySelector('.summary-year-k-cell[data-summary-year="' + y + '"]');
                    if (!cell) {
                        return;
                    }
                    var n = parseFullNumericFromTitle(cell);
                    if (n === null) {
                        n = parseCellNumber(cell);
                    }
                    if (n !== null) {
                        nums.push(roundCoeffKCalc(n));
                    }
                });
                if (nums.length === 0) {
                    sampleTd.textContent = "—";
                    sampleTd.removeAttribute("title");
                    return;
                }
                var sum = nums.reduce(function (a, b) { return a + b; }, 0);
                var sampAvg = roundCoeffKCalc(sum / nums.length);
                sampleTd.textContent = formatCoeffK(sampAvg, rd);
                setCoeffKCellFullTitle(sampleTd, sampAvg);
            });
            fillAndSyncMediumFromUsedCoeff();
            refreshCoeffAggregatedMwFromRes();
            refreshCoeffYearKCells();
            refreshFoCoeffCzTotals();
            refreshCoeffVerifyRows();
        }

        table.addEventListener("input", function (e) {
            var t = e.target;
            if (t && t.classList && t.classList.contains("pd-coeff-medium-k-input")) {
                t.setAttribute("data-pd-medium-k-override", "1");
                var kCellEd = t.closest(".summary-year-k-cell");
                var fullK = parseManualCoeffInput(t.value);
                if (fullK !== null && kCellEd) {
                    var rdInp = getRoundingDigitsK();
                    t.value = formatCoeffK(fullK, rdInp);
                    setCoeffKCellFullTitle(kCellEd, fullK);
                    setCoeffKCellFullTitle(t, fullK);
                } else if (kCellEd) {
                    kCellEd.removeAttribute("title");
                    t.removeAttribute("title");
                }
                var trK = mwTrFromCoeffControl(t);
                if (trK) {
                    syncMediumMwFromKRow(trK);
                }
                refreshCoeffAggregatedMwFromRes();
                refreshCoeffYearKCells();
                refreshFoCoeffCzTotals();
                refreshCoeffVerifyRows();
                return;
            }
            if (t && t.classList && t.classList.contains("pd-coeff-manual-input")) {
                refresh();
                return;
            }
            if (e.target.closest && e.target.closest(".fuel-param-input")) {
                var finp = e.target.closest(".fuel-param-input");
                var mwc = finp.closest("td.summary-year-mw-cell");
                if (mwc && mwc.getAttribute("data-coeff-year-segment") === "medium") {
                    updateMediumKFromMwInput(finp);
                }
                refresh();
            }
        });
        table.addEventListener("change", function (e) {
            var t = e.target;
            if (t && t.classList && t.classList.contains("pd-coeff-medium-k-input")) {
                var fullKCh = parseManualCoeffInput(t.value);
                if (fullKCh !== null) {
                    var rdCh = getRoundingDigitsK();
                    t.value = formatCoeffK(fullKCh, rdCh);
                    var kCellCh = t.closest(".summary-year-k-cell");
                    if (kCellCh) {
                        setCoeffKCellFullTitle(kCellCh, fullKCh);
                        setCoeffKCellFullTitle(t, fullKCh);
                    }
                }
                var trCh = mwTrFromCoeffControl(t);
                if (trCh) {
                    syncMediumMwFromKRow(trCh);
                }
                refreshCoeffAggregatedMwFromRes();
                refreshCoeffYearKCells();
                refreshFoCoeffCzTotals();
                refreshCoeffVerifyRows();
                return;
            }
            if (t && t.classList && t.classList.contains("pd-coeff-manual-input")) {
                var vMan = parseManualCoeffInput(t.value);
                if (vMan !== null) {
                    t.value = formatCoeffK(vMan, getRoundingDigitsK());
                }
                refresh();
                return;
            }
            if (e.target.closest && e.target.closest(".fuel-param-input")) {
                var finp2 = e.target.closest(".fuel-param-input");
                var mwc2 = finp2.closest("td.summary-year-mw-cell");
                if (mwc2 && mwc2.getAttribute("data-coeff-year-segment") === "medium") {
                    updateMediumKFromMwInput(finp2);
                }
                refresh();
            }
        });

        function syncCoeffSampleYearsFilterUi() {
            var label = table.querySelector(".power-demand-coeff-sample-filter-label");
            var clearBtn = table.querySelector('.filter-clear-btn[data-filter-name="coeff_sample_years"]');
            var years = selectedSampleYears();
            var active = years.length > 0;
            if (label) {
                var icon = label.querySelector(".bi-funnel-fill");
                if (active && !icon) {
                    icon = document.createElement("i");
                    icon.className = "bi bi-funnel-fill text-warning";
                    icon.setAttribute("aria-hidden", "true");
                    label.appendChild(icon);
                } else if (!active && icon) {
                    icon.remove();
                }
            }
            if (clearBtn) {
                clearBtn.classList.toggle("d-none", !active);
            }
        }

        table.querySelectorAll('input[name="coeff_sample_years"]').forEach(function (cb) {
            cb.addEventListener("change", function () {
                syncCoeffSampleYearsFilterUi();
                refresh();
            });
        });

        table.querySelectorAll('.filter-clear-btn[data-filter-name="coeff_sample_years"]').forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                table.querySelectorAll('input[name="coeff_sample_years"]').forEach(function (cb) {
                    cb.checked = false;
                });
                syncCoeffSampleYearsFilterUi();
                refresh();
            });
        });

        syncCoeffSampleYearsFilterUi();

        window.refreshPowerDemandCoeffMixins = refresh;
        refresh();
    })();

    (function initPowerDemandCoeffMixinColumnsToggle() {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.classList.contains("pd-coeff-year-seg-table")) {
            return;
        }
        var STORAGE_KEY = "powerDemandCoeffMixinColumnsVisibleV1";
        var btnToggle = document.getElementById("pdCoeffMixinColsToggle");

        function refreshLayoutAfterMixinVisibility() {
            if (typeof window.__pdPdSummaryRepositionEntityCells === "function") {
                window.__pdPdSummaryRepositionEntityCells();
            }
            if (typeof window.armGsApplyStickyTheadOffsets === "function") {
                window.requestAnimationFrame(function () {
                    window.armGsApplyStickyTheadOffsets();
                });
            }
            if (typeof window.armGsUpdatePdSummaryControlsStickyHeight === "function") {
                window.requestAnimationFrame(function () {
                    window.armGsUpdatePdSummaryControlsStickyHeight();
                });
            }
            window.requestAnimationFrame(function () {
                window.dispatchEvent(new Event("resize"));
            });
        }

        function syncCoeffMixinToggleButton() {
            if (!btnToggle) {
                return;
            }
            var visible = !table.classList.contains("pd-coeff-hide-mixin-columns");
            btnToggle.setAttribute("aria-pressed", visible ? "true" : "false");
            btnToggle.classList.toggle("btn-secondary", visible);
            btnToggle.classList.toggle("btn-outline-secondary", !visible);
        }

        function applyCoeffMixinColumnsVisible(show) {
            if (show) {
                table.classList.remove("pd-coeff-hide-mixin-columns");
            } else {
                table.classList.add("pd-coeff-hide-mixin-columns");
            }
            try {
                sessionStorage.setItem(STORAGE_KEY, show ? "1" : "0");
            } catch (e) { /* */ }
            syncCoeffMixinToggleButton();
            refreshLayoutAfterMixinVisibility();
            if (show && typeof window.refreshPowerDemandCoeffMixins === "function") {
                window.refreshPowerDemandCoeffMixins();
            }
        }

        function readStoredShowMixin() {
            try {
                var v = sessionStorage.getItem(STORAGE_KEY);
                if (v === "1") {
                    return true;
                }
                if (v === "0") {
                    return false;
                }
            } catch (e2) { /* */ }
            /* по умолчанию группа «Расчетный коэффициент совмещения» скрыта */
            return false;
        }

        applyCoeffMixinColumnsVisible(readStoredShowMixin());

        if (btnToggle) {
            btnToggle.addEventListener("click", function () {
                var hidden = table.classList.contains("pd-coeff-hide-mixin-columns");
                applyCoeffMixinColumnsVisible(hidden);
            });
        }
    })();

    (function initPowerDemandCoeffKColumnsToggle() {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.classList.contains("pd-coeff-year-seg-table")) {
            return;
        }
        var STORAGE_KEY = "powerDemandCoeffKColumnsVisibleV2";
        var btnToggle = document.getElementById("pdCoeffKColsToggle");
        var kRoundingWrap = document.getElementById("pdCoeffKRoundingWrap");

        function syncCoeffKToggleButton() {
            if (!btnToggle) {
                return;
            }
            var visible = !table.classList.contains("pd-coeff-hide-k-columns");
            btnToggle.textContent = visible ? "Коэффициенты" : "Коэффициенты";
            btnToggle.setAttribute("aria-pressed", visible ? "true" : "false");
            btnToggle.classList.toggle("btn-warning", visible);
            btnToggle.classList.toggle("btn-outline-secondary", !visible);
            if (kRoundingWrap) {
                kRoundingWrap.classList.toggle("d-none", !visible);
                kRoundingWrap.classList.toggle("d-flex", visible);
                kRoundingWrap.setAttribute("aria-hidden", visible ? "false" : "true");
            }
            if (typeof window.armGsUpdatePdSummaryControlsStickyHeight === "function") {
                window.requestAnimationFrame(function () {
                    window.armGsUpdatePdSummaryControlsStickyHeight();
                });
            }
        }

        function tbodyHasCoeffKRows() {
            var tbody =
                document.getElementById("powerDemandSummaryTbody") ||
                table.querySelector("tbody");
            return !!(tbody && tbody.querySelector("tr.summary-row-coeff-k"));
        }

        function afterCoeffKVisibilityChange(show) {
            syncCoeffKToggleButton();
            if (typeof window.__pdPdSummaryRepositionEntityCells === "function") {
                window.__pdPdSummaryRepositionEntityCells();
            }
            if (typeof window.armGsApplyStickyTheadOffsets === "function") {
                window.requestAnimationFrame(function () {
                    window.armGsApplyStickyTheadOffsets();
                });
            }
            window.requestAnimationFrame(function () {
                window.dispatchEvent(new Event("resize"));
            });
            if (show && typeof window.refreshPowerDemandCoeffMixins === "function") {
                window.refreshPowerDemandCoeffMixins();
            }
        }

        function applyCoeffKColumnsVisible(show) {
            if (show) {
                table.classList.remove("pd-coeff-hide-k-columns");
            } else {
                table.classList.add("pd-coeff-hide-k-columns");
            }
            try {
                sessionStorage.setItem(STORAGE_KEY, show ? "1" : "0");
            } catch (e) { /* */ }
            /* Строки k при скрытии не строились — дорисовать при включении «Коэффициенты». */
            if (
                show &&
                !tbodyHasCoeffKRows() &&
                typeof window.__pdPdSummaryRerenderTableBody === "function"
            ) {
                var rerender = window.__pdPdSummaryRerenderTableBody();
                if (rerender && typeof rerender.then === "function") {
                    rerender.then(
                        function () {
                            afterCoeffKVisibilityChange(true);
                        },
                        function () {
                            afterCoeffKVisibilityChange(true);
                        }
                    );
                    return;
                }
            }
            afterCoeffKVisibilityChange(show);
        }

        function readStoredShowK() {
            try {
                var v = sessionStorage.getItem(STORAGE_KEY);
                if (v === "1") {
                    return true;
                }
                if (v === "0") {
                    return false;
                }
            } catch (e2) { /* */ }
            /* pd_page_size=0 (все секции): по умолчанию без строк k — быстрее первый показ */
            try {
                var ps = new URLSearchParams(window.location.search || "").get(
                    "pd_page_size"
                );
                if (ps === "0") {
                    return false;
                }
            } catch (e3) { /* */ }
            return true;
        }

        var wantShowK = readStoredShowK();
        if (wantShowK) {
            applyCoeffKColumnsVisible(true);
        } else {
            applyCoeffKColumnsVisible(false);
        }

        if (btnToggle) {
            btnToggle.addEventListener("click", function () {
                var hidden = table.classList.contains("pd-coeff-hide-k-columns");
                applyCoeffKColumnsVisible(hidden);
            });
        }
    })();

    document.getElementById("rounding_digits")?.addEventListener("change", function () {
        const url = new URL(window.location.href);
        url.searchParams.set("rounding_digits", this.value);
        window.location.href = url.toString();
    });

    document.getElementById("rounding_digits_k")?.addEventListener("change", function () {
        const url = new URL(window.location.href);
        url.searchParams.set("rounding_digits_k", this.value);
        window.location.href = url.toString();
    });

    /* Экспорт как на stations_equipment_group_fuel_params и energy_consumption: fetch + blob, только кнопка disabled. */
    (function () {
        var form = document.getElementById("powerDemandSummaryExportForm");
        var exportBtn = document.getElementById("powerDemandSummaryExportBtn");
        if (!form || !exportBtn) {
            return;
        }

        function parseFilenameFromContentDisposition(cd) {
            if (!cd) {
                return "export.xlsx";
            }
            var mUtf = /filename\*=UTF-8''([^;\n]+)/i.exec(cd);
            if (mUtf && mUtf[1]) {
                try {
                    return decodeURIComponent(mUtf[1].trim());
                } catch (e1) {
                    return mUtf[1].trim();
                }
            }
            var mQuot = /filename="([^"]+)"/i.exec(cd);
            if (mQuot && mQuot[1]) {
                return mQuot[1].trim();
            }
            var mBare = /filename=([^;\n]+)/i.exec(cd);
            if (mBare && mBare[1]) {
                return mBare[1].trim().replace(/^["']|["']$/g, "");
            }
            return "export.xlsx";
        }

        var newBtn = exportBtn.cloneNode(true);
        exportBtn.parentNode.replaceChild(newBtn, exportBtn);

        newBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            var button = this;
            if (button.disabled) {
                return;
            }

            var params = new URLSearchParams(window.location.search);
            var rdSel = document.getElementById("rounding_digits");
            if (rdSel) {
                params.set("rounding_digits", rdSel.value);
            }
            var rdKSel = document.getElementById("rounding_digits_k");
            if (rdKSel) {
                params.set("rounding_digits_k", rdKSel.value);
            }
            var tableEl = document.getElementById("powerDemandSummaryTable");
            if (tableEl) {
                var evYears = [];
                var yearSeen = {};
                tableEl.querySelectorAll("thead th.summary-year-col").forEach(function (th) {
                    if (th.classList.contains("pd-ec-year-col-hidden")) {
                        return;
                    }
                    var seg = th.getAttribute("data-coeff-year-segment");
                    if (
                        seg &&
                        tableEl.classList.contains("pd-coeff-seg-hide-" + seg)
                    ) {
                        return;
                    }
                    var yyRaw =
                        th.getAttribute("data-ec-summary-col-year") ||
                        th.getAttribute("data-summary-year") ||
                        "";
                    var yy = parseInt(yyRaw, 10);
                    if (isNaN(yy) || yearSeen[yy]) {
                        return;
                    }
                    yearSeen[yy] = true;
                    evYears.push(yy);
                });
                if (evYears.length) {
                    params.set("export_years", evYears.join(","));
                }
            }
            /* Строки как на экране: видимые parameter_key (кнопки ЭЭ/ЧЧИ/Проверка/макс., пикер, пустые). */
            var domVisibleKeys = [];
            var domKeySeen = {};
            if (tableEl) {
                tableEl.querySelectorAll("tbody tr.summary-row-param").forEach(function (tr) {
                    if (
                        tr.classList.contains("summary-row-hidden") ||
                        tr.classList.contains("summary-row-empty-block-hidden")
                    ) {
                        return;
                    }
                    if (tr.getAttribute("data-pd-pd-aggregation-level") === "1") {
                        return;
                    }
                    var pk = tr.getAttribute("data-parameter-key") || "";
                    if (!pk || domKeySeen[pk]) {
                        return;
                    }
                    domKeySeen[pk] = true;
                    domVisibleKeys.push(pk);
                });
            }
            if (domVisibleKeys.length) {
                params.set("visible_rows", domVisibleKeys.join(","));
            } else {
                var storageKey = button.getAttribute("data-pd-visible-rows-key") || "";
                if (storageKey) {
                    try {
                        var raw = sessionStorage.getItem(storageKey);
                        if (raw) {
                            var arr = JSON.parse(raw);
                            if (Array.isArray(arr) && arr.length > 0) {
                                params.set("visible_rows", arr.join(","));
                            }
                        }
                    } catch (err) { /* */ }
                }
            }
            var ntBtn = document.getElementById("pdPdSummaryNtDetailToggle");
            if (ntBtn && window.__pdPdSummaryNtDetailMode === true) {
                params.set("export_nt_detail", "1");
            }
            var compactBtn = document.getElementById("pdPdSummaryTerritoryCompactToggle");
            if (compactBtn && window.__pdPdSummaryTerritoryCompactMode === true) {
                params.set("export_territory_compact", "1");
            }
            if (window.__pdPdSummaryHistMode === true) {
                params.set("export_hist", "1");
            }
            /* По умолчанию на экране пустые блоки скрыты — то же в Excel. */
            if (window.__pdPdSummaryShowEmptyMode !== true) {
                params.set("export_hide_empty", "1");
            }

            var entityLabels = {};
            if (tableEl) {
                tableEl
                    .querySelectorAll(
                        'tbody tr.summary-row-param[data-is-block-start="1"]'
                    )
                    .forEach(function (tr) {
                        if (
                            tr.classList.contains("summary-row-hidden") ||
                            tr.classList.contains("summary-row-empty-block-hidden")
                        ) {
                            return;
                        }
                        var cell = tr.querySelector("td.summary-entity-cell");
                        if (!cell) {
                            return;
                        }
                        var clone = cell.cloneNode(true);
                        clone.querySelectorAll(".pd-pd-dz-mark").forEach(function (el) {
                            el.remove();
                        });
                        var text = String(clone.textContent || "")
                            .replace(/\s+/g, " ")
                            .trim();
                        if (!text) {
                            return;
                        }
                        var key = [
                            tr.getAttribute("data-demand-model-name") || "",
                            tr.getAttribute("data-parent-fk-column") || "",
                            tr.getAttribute("data-parent-id") || "",
                            tr.getAttribute("data-id-union-energy-system") || "",
                            tr.getAttribute("data-id-regional-energy-system") || "",
                            tr.getAttribute("data-id-regional-district") || "",
                            tr.getAttribute("data-id-energy-unit") || "",
                            tr.getAttribute("data-id-synchronous-area") || "",
                            tr.getAttribute("data-id-energy-zone") || "",
                            tr.getAttribute("data-perimeter-variant-code") || "",
                            tr.getAttribute("data-pd-pd-nt-extra") || "0",
                            tr.getAttribute("data-pd-pd-aggregation-level") || "0",
                        ].join("\x1f");
                        entityLabels[key] = text;
                    });
            }

            var exportUrl = form.action + (params.toString() ? "?" + params.toString() : "");
            var originalHtml = button.innerHTML;

            button.innerHTML =
                '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Экспорт…';
            button.disabled = true;

            var fetchOpts = {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream, */*",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ export_entity_labels: entityLabels }),
            };

            fetch(exportUrl, fetchOpts)
                .then(function (response) {
                    if (!response.ok) {
                        return response.text().then(function (text) {
                            throw new Error(
                                "Ошибка сервера (" +
                                    response.status +
                                    "): " +
                                    (text ? text.substring(0, 200) : "")
                            );
                        });
                    }
                    var contentType = response.headers.get("content-type") || "";
                    var ctLow = contentType.toLowerCase();
                    if (
                        ctLow.indexOf("application/vnd.openxmlformats") !== -1 ||
                        ctLow.indexOf("application/octet-stream") !== -1
                    ) {
                        var fn = parseFilenameFromContentDisposition(response.headers.get("Content-Disposition"));
                        return response.blob().then(function (blob) {
                            var url = window.URL.createObjectURL(blob);
                            var a = document.createElement("a");
                            a.href = url;
                            a.download = fn || "export.xlsx";
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                            document.body.removeChild(a);
                        });
                    }
                    return response.text().then(function () {
                        throw new Error("Получен неожиданный тип ответа от сервера");
                    });
                })
                .catch(function (error) {
                    console.error("[EXPORT power_demand summary]", error);
                    alert(
                        "Ошибка при экспорте: " +
                            (error && error.message ? error.message : String(error)) +
                            "\n\nПроверьте консоль браузера (F12) для подробностей."
                    );
                })
                .finally(function () {
                    button.innerHTML = originalHtml;
                    button.disabled = false;
                });
        });
    })();

    document.querySelectorAll('#powerDemandSummaryTable [data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    window.__pdPdSummaryInitTableTooltips = function () {
        document.querySelectorAll('#powerDemandSummaryTable [data-bs-toggle="tooltip"]').forEach(function (el) {
            var existing = bootstrap.Tooltip.getInstance(el);
            if (existing) {
                existing.dispose();
            }
            new bootstrap.Tooltip(el);
        });
    };
    document.addEventListener("pd-summary-rows-rendered", function () {
        if (typeof window.__pdPdSummarySyncPerimeterVariantLabels === "function") {
            window.__pdPdSummarySyncPerimeterVariantLabels();
        }
        if (typeof window.__pdPdSummaryInitTableTooltips === "function") {
            window.__pdPdSummaryInitTableTooltips();
        }
        if (typeof window.__pdPdSummaryApplyBlockRowBackgrounds === "function") {
            window.__pdPdSummaryApplyBlockRowBackgrounds();
        }
        if (typeof window.__pdPdSummaryApplyEntityLevelBorders === "function") {
            window.__pdPdSummaryApplyEntityLevelBorders();
        }
    });

    const table = document.querySelector(".power-demand-summary-table[data-save-cell-url]");
    const saveBtn = document.getElementById("demandSummarySaveBtn");
    if (!table || !saveBtn) {
        return;
    }
    const saveUrl = table.dataset.saveCellUrl;
    const roundingDigits = parseInt(
        table.dataset.pdRoundingDigits || table.dataset.roundingDigits || "1",
        10
    );
    const roundingDigitsK = parseInt(
        table.dataset.pdRoundingDigitsK || "3",
        10
    );

    function normForCompare(s) {
        return String(s ?? "").trim().replace(/\s+/g, "").replace(",", ".");
    }

    var __pdSummaryPageCfg = {};
    try {
        var __pdSummaryPageCfgEl = document.getElementById("pd-summary-page-config");
        if (__pdSummaryPageCfgEl && __pdSummaryPageCfgEl.textContent) {
            __pdSummaryPageCfg = JSON.parse(__pdSummaryPageCfgEl.textContent) || {};
        }
    } catch (__pdSummaryPageCfgErr) {
        __pdSummaryPageCfg = {};
    }
    const PD_SUMMARY_HIST_EDITABLE_KEYS = new Set(__pdSummaryPageCfg.hist_editable_keys || []);
    const PD_SUMMARY_HIST_RESTRICTED = !!__pdSummaryPageCfg.hist_restricted;

    function isPdSummaryHistInputAllowed(inp) {
        if (!inp) {
            return false;
        }
        const pk = inp.getAttribute("data-parameter-key") || "";
        // Примечание хранится на hist-строке, но не относится к ограничению
        // редактирования столбца «Исторический максимум».
        if (pk === "entity_note" || inp.classList.contains("power-demand-summary-note-field")) {
            return true;
        }
        const slice = inp.getAttribute("data-slice") || "";
        if (slice !== "hist") {
            return true;
        }
        if (inp.closest("td.summary-hist-cell-disabled")) {
            return false;
        }
        if (!PD_SUMMARY_HIST_RESTRICTED) {
            return true;
        }
        return PD_SUMMARY_HIST_EDITABLE_KEYS.has(pk);
    }

    const headers = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": (__pdSummaryPageCfg.csrf_token || "")
    };

    function expandTwoDigitYear(yy) {
        return yy <= 68 ? 2000 + yy : 1900 + yy;
    }

    function normalizePeakDatetimeText(val) {
        var text = String(val == null ? "" : val)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ");
        var lines = text.split(/\r?\n/);
        var parts = [];
        for (var li = 0; li < lines.length; li++) {
            var t = lines[li].trim();
            if (t) {
                parts.push(t);
            }
        }
        var s = parts.length ? parts.join(" ") : text.trim();
        s = s.replace(/\s+/g, " ").trim();
        var qmarks = "\"'«»“”";
        while (
            s.length >= 2 &&
            s.charAt(0) === s.charAt(s.length - 1) &&
            qmarks.indexOf(s.charAt(0)) >= 0
        ) {
            s = s.slice(1, -1).trim();
        }
        s = s.replace(/^["'«»“”]+|["'«»“”]+$/g, "").trim();
        // «10.01.23 18-00» → время через двоеточие
        s = s.replace(
            /((?:\d{1,2}\.){2}\d{2,4})\s+(\d{1,2})-(\d{2})(?::(\d{2}))?/,
            function (_m, datePart, hh, mm, ss) {
                var out =
                    datePart +
                    " " +
                    String(parseInt(hh, 10)).padStart(2, "0") +
                    ":" +
                    mm;
                if (ss) {
                    out += ":" + ss;
                }
                return out;
            }
        );
        // Двузначный год и выравнивание ДД.ММ
        s = s.replace(/\b(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})\b/, function (_m, d, mo, yRaw) {
            var y = parseInt(yRaw, 10);
            if (yRaw.length === 2) {
                y = expandTwoDigitYear(y);
            }
            return (
                String(parseInt(d, 10)).padStart(2, "0") +
                "." +
                String(parseInt(mo, 10)).padStart(2, "0") +
                "." +
                String(y).padStart(4, "0")
            );
        });
        s = s.replace(
            /((?:\d{2}\.){2}\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/,
            function (_m, datePart, hh, mm, ss) {
                var out =
                    datePart +
                    " " +
                    String(parseInt(hh, 10)).padStart(2, "0") +
                    ":" +
                    mm;
                if (ss) {
                    out += ":" + ss;
                }
                return out;
            }
        );
        return s;
    }

    function parsePeakDatetimeParts(s) {
        if (!s) return null;
        if (/^\d{4}$/.test(s)) {
            var yy = parseInt(s, 10);
            if (yy >= 1000 && yy <= 9999) {
                return new Date(yy, 0, 1, 0, 0, 0, 0);
            }
            return null;
        }
        var m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})(?::(\d{2}))?$/.exec(s);
        if (!m) {
            m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(s);
            if (!m) {
                var dateM = /(\d{2}\.\d{2}\.\d{4})/.exec(s);
                if (!dateM) return null;
                var timeM = /(\d{1,2}:\d{2}(?::\d{2})?)/.exec(s);
                if (timeM) {
                    var timePart = timeM[1];
                    if (/^\d:\d{2}(?::\d{2})?$/.test(timePart)) {
                        timePart = "0" + timePart;
                    }
                    s = dateM[1] + " " + timePart;
                    m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})(?::(\d{2}))?$/.exec(s);
                } else {
                    m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(dateM[1]);
                    if (!m) return null;
                    m = [m[0], m[1], m[2], m[3], "0", "0", "0"];
                }
            } else {
                m = [m[0], m[1], m[2], m[3], "0", "0", "0"];
            }
        }
        if (!m) return null;
        var d = parseInt(m[1], 10);
        var mo = parseInt(m[2], 10) - 1;
        var y = parseInt(m[3], 10);
        var h = parseInt(m[4], 10);
        var mi = parseInt(m[5], 10);
        var dt = new Date(y, mo, d, h, mi, 0, 0);
        if (
            dt.getFullYear() !== y ||
            dt.getMonth() !== mo ||
            dt.getDate() !== d ||
            dt.getHours() !== h ||
            dt.getMinutes() !== mi
        ) {
            return null;
        }
        return dt;
    }

    function formatPeakDatetimeSummaryInput(inp) {
        if (!inp || inp.dataset.parameterKey !== "peak_datetime") {
            return;
        }
        var raw = String(inp.value || "").trim();
        if (!raw) {
            return;
        }
        var sl = String(inp.dataset.slice || "").trim();
        if (sl === "hist" && /^\d{4}$/.test(normalizePeakDatetimeText(raw))) {
            return;
        }
        var pdt = parsePeakDatetimeSummary(raw);
        if (!pdt) {
            return;
        }
        var dd = String(pdt.getDate()).padStart(2, "0");
        var mm = String(pdt.getMonth() + 1).padStart(2, "0");
        var yyyy = String(pdt.getFullYear());
        var hh = String(pdt.getHours()).padStart(2, "0");
        var mi = String(pdt.getMinutes()).padStart(2, "0");
        inp.value = dd + "." + mm + "." + yyyy + " " + hh + ":" + mi;
    }

    function parsePeakDatetimeSummary(val) {
        return parsePeakDatetimeParts(normalizePeakDatetimeText(val));
    }

    function validateDemandSummaryPeak(inp) {
        if (inp.dataset.parameterKey !== "peak_datetime") {
            return true;
        }
        var raw = String(inp.value || "").trim();
        if (!raw) {
            return true;
        }
        var sl = String(inp.dataset.slice || "").trim();
        if (sl === "hist") {
            return true;
        }
        var pdt = parsePeakDatetimeSummary(inp.value);
        if (!pdt) {
            alert("«Дата и время»: укажите дату в формате ДД.ММ.ГГГГ ЧЧ:ММ или только год (ГГГГ).");
            return false;
        }
        var colY = parseInt(sl, 10);
        if (!Number.isNaN(colY) && pdt.getFullYear() !== colY) {
            alert(
                "Год в «Дата и время» (" +
                    pdt.getFullYear() +
                    ") должен совпадать с годом столбца (" +
                    colY +
                    ")."
            );
            return false;
        }
        return true;
    }

    function syncPdEcPerimeterVariantSelectLabels(root) {
        var scope = root || table;
        if (!scope) {
            return;
        }
        scope.querySelectorAll(".pd-ec-perimeter-variant-select-wrap").forEach(function (wrap) {
            var sel = wrap.querySelector("select.pd-ec-perimeter-variant-select");
            var label = wrap.querySelector(".pd-ec-perimeter-variant-select-label");
            if (!sel || !label) {
                return;
            }
            var opt = sel.options[sel.selectedIndex];
            label.textContent = opt ? String(opt.textContent || "").trim() : "";
            sel.style.height = "auto";
            sel.style.minHeight = Math.max(label.scrollHeight + 8, 32) + "px";
        });
    }
    window.__pdPdSummarySyncPerimeterVariantLabels = function (root) {
        syncPdEcPerimeterVariantSelectLabels(root || table);
    };

    function pdEcPerimeterVariantOptionValues(sel) {
        var values = [];
        for (var i = 0; i < sel.options.length; i++) {
            values.push(String(sel.options[i].value || "").trim());
        }
        return values;
    }

    function syncPdEcPerimeterVariantSelectInitial(sel) {
        if (!sel) {
            return;
        }
        var initial = String(sel.getAttribute("data-initial") || "").trim();
        var current = String(sel.value || "").trim();
        if (initial && pdEcPerimeterVariantOptionValues(sel).indexOf(initial) < 0) {
            sel.setAttribute("data-initial", current);
        }
    }

    function syncAllPdEcPerimeterVariantSelectInitials(root) {
        var scope = root || table;
        if (!scope) {
            return;
        }
        scope.querySelectorAll("select.pd-ec-perimeter-variant-select").forEach(function (sel) {
            syncPdEcPerimeterVariantSelectInitial(sel);
        });
    }

    function perimeterVariantFromCode(sel) {
        return String(sel.getAttribute("data-initial") || "").trim();
    }

    function isPdEcPerimeterVariantSelectChanged(sel) {
        syncPdEcPerimeterVariantSelectInitial(sel);
        var initial = String(sel.getAttribute("data-initial") || "").trim();
        var current = String(sel.value || "").trim();
        return normForCompare(initial) !== normForCompare(current);
    }

    function summaryBlockHasPersistedDemandRows(startTr) {
        if (!startTr) {
            return false;
        }
        var blockRows = collectSummaryBlockRows(startTr);
        for (var i = 0; i < blockRows.length; i++) {
            var inps = blockRows[i].querySelectorAll(
                ".fuel-param-input[data-row-id], input.pd-coeff-medium-k-input[data-row-id]"
            );
            for (var j = 0; j < inps.length; j++) {
                var rid = inps[j].getAttribute("data-row-id");
                if (rid !== null && rid !== "") {
                    return true;
                }
            }
        }
        return false;
    }

    function summaryBlockPersistKey(startTr) {
        if (!startTr) {
            return "";
        }
        return [
            startTr.getAttribute("data-demand-model-name") || "",
            startTr.getAttribute("data-parent-fk-column") ||
                startTr.getAttribute("data-parent-fk") ||
                "",
            startTr.getAttribute("data-parent-id") || "",
            startTr.getAttribute("data-perimeter-variant-code") || "",
            startTr.getAttribute("data-id-union-energy-system") || "",
            startTr.getAttribute("data-id-regional-energy-system") || "",
            startTr.getAttribute("data-id-regional-district") || "",
            startTr.getAttribute("data-id-synchronous-area") || "",
            startTr.getAttribute("data-id-energy-unit") || "",
        ].join("|");
    }

    function variantSelectNeedsSave(sel) {
        if (isPdEcPerimeterVariantSelectChanged(sel)) {
            return true;
        }
        var startTr = findSummaryBlockStartTr(sel.closest("tr"));
        return !!startTr && !summaryBlockHasPersistedDemandRows(startTr);
    }

    function findSummaryBlockStartTr(fromTr) {
        var tr = fromTr;
        while (tr) {
            if (
                tr.classList.contains("summary-row-param") &&
                tr.hasAttribute("data-is-block-start") &&
                !tr.classList.contains("pd-pd-verify-for-row")
            ) {
                return tr;
            }
            tr = tr.previousElementSibling;
        }
        return fromTr;
    }

    function collectSummaryBlockRows(startTr) {
        var blockSize = parseInt(startTr.getAttribute("data-entity-block-size") || "1", 10);
        if (blockSize < 1) {
            blockSize = 1;
        }
        var blockRows = [];
        var tr = startTr;
        for (var j = 0; j < blockSize && tr; j++) {
            if (tr.classList.contains("summary-row-param")) {
                blockRows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        return blockRows;
    }

    function findBlockVariantSelect(fromTr) {
        var start = findSummaryBlockStartTr(fromTr);
        var blockRows = collectSummaryBlockRows(start);
        for (var i = 0; i < blockRows.length; i++) {
            var sel = blockRows[i].querySelector(".pd-ec-perimeter-variant-select");
            if (sel) {
                return sel;
            }
        }
        return null;
    }

    function perimeterVariantPayloadValue(fromTr) {
        var sel = findBlockVariantSelect(fromTr);
        if (sel) {
            var selected = String(sel.value || "").trim();
            if (selected) {
                return selected;
            }
        }
        var tr = fromTr.closest("tr");
        var startTr = findSummaryBlockStartTr(tr);
        if (startTr) {
            var fromStart = startTr.getAttribute("data-perimeter-variant-code");
            if (fromStart) {
                return fromStart;
            }
        }
        if (tr) {
            return tr.getAttribute("data-perimeter-variant-code");
        }
        return null;
    }

    function buildPerimeterVariantSaveRequest(sel) {
        const variantUrl = table.dataset.savePerimeterVariantUrl || "";
        const blockVariantUrl = table.dataset.saveBlockVariantUrl || "";
        const saveVariantUrl = blockVariantUrl || variantUrl;
        if (!saveVariantUrl) {
            return { error: "Не настроен URL сохранения варианта периметра." };
        }
        const toVariant = String(sel.value || "").trim();
        const vPayload = {
            demand_model_name: sel.getAttribute("data-demand-model-name") || "",
            block_kind: sel.getAttribute("data-block-kind") || "base"
        };
        if (blockVariantUrl) {
            vPayload.perimeter_variant_code = toVariant || null;
            vPayload.from_variant_code = perimeterVariantFromCode(sel) || null;
        } else {
            vPayload.from_variant_code = perimeterVariantFromCode(sel) || null;
            vPayload.to_variant_code = toVariant || null;
        }
        const vPfk = sel.getAttribute("data-parent-fk");
        if (vPfk) {
            vPayload.parent_fk_column = vPfk;
        }
        const vPid = sel.getAttribute("data-parent-id");
        if (vPid !== null && vPid !== "") {
            vPayload.parent_id = parseInt(vPid, 10);
        }
        const logScope = table.getAttribute("data-summary-log-scope");
        if (logScope) {
            vPayload.summary_log_scope = logScope;
        }
        if (!vPayload.demand_model_name) {
            return { skip: true };
        }
        return { url: saveVariantUrl, payload: vPayload };
    }

    async function savePerimeterVariantSelect(sel) {
        const req = buildPerimeterVariantSaveRequest(sel);
        if (req.skip) {
            return true;
        }
        if (req.error) {
            alert(req.error);
            return false;
        }
        const vResp = await fetch(req.url, {
            method: "POST",
            credentials: "same-origin",
            headers: headers,
            body: JSON.stringify(req.payload)
        });
        const vData = await vResp.json().catch(function () { return null; });
        if (!vResp.ok || !vData || !vData.ok) {
            const vMsg = (vData && vData.error) ? vData.error : "Не удалось сохранить вариант периметра.";
            alert(vMsg);
            return false;
        }
        sel.setAttribute("data-initial", sel.value || "");
        const startTr = findSummaryBlockStartTr(sel.closest("tr"));
        if (startTr) {
            collectSummaryBlockRows(startTr).forEach(function (tr) {
                if (sel.value) {
                    tr.setAttribute("data-perimeter-variant-code", sel.value);
                } else {
                    tr.removeAttribute("data-perimeter-variant-code");
                }
            });
        }
        return true;
    }

    syncAllPdEcPerimeterVariantSelectInitials(table);
    syncPdEcPerimeterVariantSelectLabels(table);

    table.addEventListener("change", function (ev) {
        if (
            ev.target &&
            ev.target.matches &&
            ev.target.matches("select.pd-ec-perimeter-variant-select")
        ) {
            syncPdEcPerimeterVariantSelectLabels(table);
        }
    });

    async function runDemandSummarySave() {
        if (saveBtn.disabled) {
            return;
        }
        syncAllPdEcPerimeterVariantSelectInitials(table);
        const variantSelects = table.querySelectorAll(".pd-ec-perimeter-variant-select");
        const changedVariants = [];
        const seenVariantBlocks = {};
        variantSelects.forEach(function (sel) {
            if (!variantSelectNeedsSave(sel)) {
                return;
            }
            var startTr = findSummaryBlockStartTr(sel.closest("tr"));
            var blockKey = summaryBlockPersistKey(startTr);
            if (blockKey && seenVariantBlocks[blockKey]) {
                return;
            }
            if (blockKey) {
                seenVariantBlocks[blockKey] = true;
            }
            changedVariants.push(sel);
        });
        const inputs = table.querySelectorAll(
            ".fuel-param-input[data-model][data-slice], input.pd-coeff-medium-k-input[data-model][data-slice][data-parameter-key^=\"coeff_k_\"]"
        );
        const changed = [];
        inputs.forEach(function (inp) {
            if (!isPdSummaryHistInputAllowed(inp)) {
                return;
            }
            const initial = inp.getAttribute("data-initial") || "";
            if (normForCompare(initial) !== normForCompare(inp.value)) {
                changed.push(inp);
            }
        });
        changed.sort(function (a, b) {
            const pa = (a.dataset.parameterKey || a.getAttribute("data-parameter-key") || "");
            const pb = (b.dataset.parameterKey || b.getAttribute("data-parameter-key") || "");
            const ac = pa.indexOf("coeff_k_") === 0 ? 0 : 1;
            const bc = pb.indexOf("coeff_k_") === 0 ? 0 : 1;
            if (ac !== bc) {
                return ac - bc;
            }
            return 0;
        });
        if (changed.length === 0 && changedVariants.length === 0) {
            alert("Нет изменений для сохранения.");
            return;
        }

        const originalHtml = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Сохранение...';

        try {
            for (let vi = 0; vi < changedVariants.length; vi++) {
                const sel = changedVariants[vi];
                if (!(await savePerimeterVariantSelect(sel))) {
                    saveBtn.innerHTML = originalHtml;
                    saveBtn.disabled = false;
                    return;
                }
            }
            for (let i = 0; i < changed.length; i++) {
                const inp = changed[i];
                formatPeakDatetimeSummaryInput(inp);
                if (!validateDemandSummaryPeak(inp)) {
                    saveBtn.innerHTML = originalHtml;
                    saveBtn.disabled = false;
                    return;
                }
                const sliceRaw = inp.dataset.slice || inp.getAttribute("data-slice");
                const pk =
                    inp.dataset.parameterKey || inp.getAttribute("data-parameter-key") || "";
                const payload = {
                    demand_model_name: inp.dataset.model || inp.getAttribute("data-model"),
                    parameter_key: pk,
                    value: inp.value,
                    rounding_digits: pk.indexOf("coeff_k_") === 0 ? roundingDigitsK : roundingDigits,
                    rounding_digits_k: roundingDigitsK,
                    slice_key: sliceRaw === "hist" ? "hist" : (sliceRaw ? parseInt(sliceRaw, 10) : null)
                };
                const ridAttr = inp.getAttribute("data-row-id");
                if (ridAttr !== null && ridAttr !== "") {
                    const rid = parseInt(ridAttr, 10);
                    if (!Number.isNaN(rid)) {
                        payload.row_id = rid;
                    }
                }
                const blockStartTr = findSummaryBlockStartTr(inp.closest("tr"));
                const pfk =
                    inp.getAttribute("data-parent-fk") ||
                    (blockStartTr
                        ? blockStartTr.getAttribute("data-parent-fk-column")
                        : null);
                if (pfk) {
                    payload.parent_fk_column = pfk;
                }
                const pidi =
                    inp.getAttribute("data-parent-id") ||
                    (blockStartTr ? blockStartTr.getAttribute("data-parent-id") : null);
                if (pidi !== null && pidi !== "") {
                    payload.parent_id = parseInt(pidi, 10);
                }
                if (!payload.demand_model_name && blockStartTr) {
                    payload.demand_model_name =
                        blockStartTr.getAttribute("data-demand-model-name") || "";
                }
                const pvcTr = inp.closest("tr");
                const pvcFromSelect = perimeterVariantPayloadValue(inp);
                if (pvcFromSelect !== null && pvcFromSelect !== undefined) {
                    payload.perimeter_variant_code = pvcFromSelect;
                } else {
                    const pvcAttr = pvcTr ? pvcTr.getAttribute("data-perimeter-variant-code") : null;
                    if (pvcAttr) {
                        payload.perimeter_variant_code = pvcAttr;
                    }
                }
                if (!payload.demand_model_name || !payload.parameter_key) {
                    alert(
                        "Не удалось сохранить ячейку: нет модели или параметра. Обновите страницу и попробуйте снова."
                    );
                    saveBtn.innerHTML = originalHtml;
                    saveBtn.disabled = false;
                    return;
                }
                const logScope = table.getAttribute("data-summary-log-scope");
                if (logScope) {
                    payload.summary_log_scope = logScope;
                }
                const response = await fetch(saveUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: headers,
                    body: JSON.stringify(payload)
                });
                const data = await response.json().catch(function () { return null; });
                if (!response.ok || !data || !data.ok) {
                    const msg = (data && data.error) ? data.error : "Не удалось сохранить.";
                    alert(msg);
                    saveBtn.innerHTML = originalHtml;
                    saveBtn.disabled = false;
                    return;
                }
                if (typeof data.display_value === "string") {
                    inp.value = data.display_value === "—" ? "" : data.display_value;
                }
                inp.setAttribute("data-initial", inp.value || "");
            }
            if (changed.length > 0) {
                window.armGsPageScrollRestore.reload({ table: table, changedInputs: changed });
            } else if (changedVariants.length > 0) {
                window.armGsPageScrollRestore.reload({
                    table: table,
                    changedInputs: changedVariants
                });
            }
            syncPdEcPerimeterVariantSelectLabels(table);
            saveBtn.innerHTML = originalHtml;
            saveBtn.disabled = false;
        } catch (e) {
            alert("Ошибка сети при сохранении.");
            saveBtn.innerHTML = originalHtml;
            saveBtn.disabled = false;
        }
    }

    saveBtn.addEventListener("click", function () {
        runDemandSummarySave();
    });

    table.addEventListener("blur", function (e) {
        if (
            e.target &&
            e.target.matches(
                'input.fuel-param-input[data-parameter-key="peak_datetime"], textarea.fuel-param-input[data-parameter-key="peak_datetime"]'
            )
        ) {
            formatPeakDatetimeSummaryInput(e.target);
        }
    }, true);

    if (typeof window.initPowerDemandSummaryRowPaste === "function") {
        window.initPowerDemandSummaryRowPaste(table, {
            formatPeakDatetime: formatPeakDatetimeSummaryInput
        });
    }

    table.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" || e.repeat) {
            return;
        }
        if (!e.target || !e.target.matches("input.fuel-param-input, textarea.fuel-param-input")) {
            return;
        }
        e.preventDefault();
        runDemandSummarySave();
    });
});

window.addEventListener("load", function () {
    var done = function () {
        if (typeof window.__pdPdSummaryFinishInitialRender === "function") {
            window.__pdPdSummaryFinishInitialRender();
        }
    };
    if (window.__pdSummaryRowsReady && typeof window.__pdSummaryRowsReady.then === "function") {
        window.__pdSummaryRowsReady.then(done, done);
    } else {
        done();
    }
});
