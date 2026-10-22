/**
 * Живой пересчёт план-годов, ЧЧИУМ и агрегатов на странице СЭС/ВЭС.
 * ЧЧИУМ – по сырым значениям (data-raw), не по округлённому отображению.
 */
(function () {
    "use strict";

    function parseNum(raw) {
        if (raw == null) {
            return null;
        }
        var s = String(raw)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ")
            .replace(/\s/g, "")
            .replace(",", ".")
            .trim();
        if (!s || s === "–" || s === "-" || s === "–") {
            return null;
        }
        var n = Number(s);
        return isFinite(n) ? n : null;
    }

    function positive(n) {
        return n != null && n > 0 ? n : null;
    }

    function formatNum(n, digits, showZero) {
        if (n == null || !isFinite(n)) {
            return "–";
        }
        var value = n;
        var text;
        if (digits === -1) {
            value = Math.round(value);
            if (value === 0 && !showZero) {
                return "–";
            }
            text = String(value);
        } else if (digits === 0) {
            if (value === 0 && !showZero) {
                return "–";
            }
            if (Math.abs(value) >= 1e12 || (Math.abs(value) > 0 && Math.abs(value) < 1e-9)) {
                text = value.toPrecision(12);
            } else {
                text = value.toFixed(12);
            }
            if (text.indexOf("e") >= 0 || text.indexOf("E") >= 0) {
                text = value.toFixed(12);
            }
            text = text.replace(/\.?0+$/, "");
        } else {
            var factor = Math.pow(10, digits);
            value = Math.round(value * factor) / factor;
            if (value === 0 && !showZero) {
                return "–";
            }
            text = value.toFixed(digits);
        }
        text = text.replace(".", ",");
        var parts = text.split(",");
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        return parts.join(",");
    }

    function formatRawTitle(n) {
        if (n == null || !isFinite(n)) {
            return "";
        }
        var text = formatNum(n, 0);
        return text === "–" ? "" : text;
    }

    function attrId(el, name) {
        var raw = el && el.getAttribute(name);
        return raw == null || raw === "" ? "" : String(raw);
    }

    function cellRawNumber(el) {
        if (!el) {
            return null;
        }
        var fromAttr = parseNum(el.getAttribute("data-raw"));
        if (fromAttr != null) {
            return fromAttr;
        }
        if (el.tagName === "INPUT") {
            return parseNum(el.value);
        }
        return parseNum(el.textContent);
    }

    function yearMapFromJson(raw) {
        var map = {};
        if (!raw) {
            return map;
        }
        try {
            var parsed = JSON.parse(raw);
            Object.keys(parsed || {}).forEach(function (key) {
                var year = Number(key);
                if (!isFinite(year)) {
                    return;
                }
                map[year] = parseNum(parsed[key]);
            });
        } catch (err) {
            return {};
        }
        return map;
    }

    function mapByYear(root, selector) {
        var map = {};
        if (!root) {
            return map;
        }
        root.querySelectorAll(selector).forEach(function (el) {
            var year = Number(el.getAttribute("data-year"));
            if (isFinite(year)) {
                map[year] = el;
            }
        });
        return map;
    }

    function controlInTd(td, kind) {
        if (!td) {
            return null;
        }
        return (
            td.querySelector("input[data-kind='" + kind + "']") ||
            td.querySelector("[data-ves-deferred='1'][data-kind='" + kind + "']")
        );
    }

    function mapControlsByYear(root, kind) {
        var map = {};
        if (!root) {
            return map;
        }
        root.querySelectorAll("td[data-ves-col='" + kind + "']").forEach(function (td) {
            var year = Number(td.getAttribute("data-year"));
            if (!isFinite(year)) {
                return;
            }
            map[year] = controlInTd(td, kind);
        });
        return map;
    }

    function isInputEl(el) {
        return !!(el && el.tagName === "INPUT");
    }

    function readControlNumber(el) {
        if (!el) {
            return null;
        }
        if (isInputEl(el)) {
            if (el.getAttribute("data-dirty") === "1") {
                return parseNum(el.value);
            }
            return cellRawNumber(el);
        }
        return cellRawNumber(el);
    }

    function setControlDisplay(el, value, digits, rule) {
        if (!el) {
            return;
        }
        if (isInputEl(el)) {
            setInputDisplay(el, value, digits, rule);
            return;
        }
        var formatted = value == null ? "" : formatNum(value, digits);
        if (formatted === "–") {
            formatted = "";
        }
        el.textContent = formatted;
        setPlanRuleTitle(el, rule || "", formatRawTitle(value));
        if (rule) {
            el.classList.add("ves-ses-plan-calc-input");
        }
    }

    var PLAN_RULE_OWNER_IN_PLAN =
        "Расчёт: выработка от собственника (ввод мощности в плановом периоде)";
    var PLAN_RULE_CAPACITY_SES =
        "Расчёт: установленная мощность × 1,5 (СЭС, нет данных от собственника)";
    var PLAN_RULE_CAPACITY_VES =
        "Расчёт: установленная мощность × 2,5 (ВЭС, нет данных от собственника)";
    var PLAN_RULE_CAPACITY_SES_PARTIAL =
        "Расчёт: установленная мощность × 1,5 × доля года работы по ожидаемой дате ввода (СЭС, нет данных от собственника)";
    var PLAN_RULE_CAPACITY_VES_PARTIAL =
        "Расчёт: установленная мощность × 2,5 × доля года работы по ожидаемой дате ввода (ВЭС, нет данных от собственника)";
    var PLAN_RULE_OWNER_POSITIVE = "Расчёт: выработка от собственника (> 0)";
    var PLAN_RULE_SEVEN_YEAR_MIN =
        "Расчёт: минимум положительной выработки за последние 7 лет факта";
    var PLAN_RULE_SEVEN_YEAR_MIN_RAMP =
        "Расчёт: минимум положительной выработки за последние 7 лет факта (без учёта лет разгона после ввода)";
    var PLAN_RULE_MIN_OWNER_SAMPLE_OWNER =
        "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта (взята выработка от собственника)";
    var PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE =
        "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта (взято значение за 7 лет факта)";
    var PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE_RAMP =
        "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта (взято значение за 7 лет факта, без учёта лет разгона после ввода)";
    var PLAN_RULE_MIN_OWNER_SAMPLE_EQUAL =
        "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта (значения совпадают)";

    function minSampleResult(energyByYear, cfg) {
        var empty = { value: null, rampExcluded: false };
        if (cfg.currentYear == null || cfg.sampleStart == null || cfg.sampleEnd == null) {
            return empty;
        }
        var pairs = [];
        for (var year = cfg.sampleStart; year <= cfg.sampleEnd; year++) {
            var value = positive(energyByYear[year]);
            if (value != null) {
                pairs.push([year, value]);
            }
        }
        if (!pairs.length) {
            return empty;
        }
        var commission = cfg.commissionYear;
        var rampExcluded = false;
        if (commission != null && commission >= cfg.sampleStart && commission <= cfg.sampleEnd) {
            var excluded = {};
            excluded[pairs[0][0]] = true;
            if (pairs.length >= 3 && pairs[2][1] > 0 && pairs[1][1] < pairs[2][1] * 0.5) {
                excluded[pairs[1][0]] = true;
            }
            var filtered = pairs.filter(function (pair) {
                return !excluded[pair[0]];
            });
            rampExcluded = filtered.length < pairs.length;
            pairs = filtered;
        }
        if (!pairs.length) {
            return { value: null, rampExcluded: rampExcluded };
        }
        var min = pairs[0][1];
        for (var i = 1; i < pairs.length; i++) {
            if (pairs[i][1] < min) {
                min = pairs[i][1];
            }
        }
        return { value: min, rampExcluded: rampExcluded };
    }

    function firstPositiveCapacityYear(capacityByYear) {
        var first = null;
        Object.keys(capacityByYear || {}).forEach(function (key) {
            var year = Number(key);
            if (!positive(capacityByYear[year])) {
                return;
            }
            if (first == null || year < first) {
                first = year;
            }
        });
        return first;
    }

    function parseExploitationDate(raw) {
        if (raw == null) {
            return null;
        }
        var text = String(raw).trim();
        if (!text || text === "–" || text === "-" || text === "–") {
            return null;
        }
        var m = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
        if (m) {
            return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
        }
        m = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (m) {
            return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
        }
        m = text.match(/^(\d{4})$/);
        if (m) {
            return new Date(Number(m[1]), 0, 1);
        }
        return null;
    }

    function isLeapYear(year) {
        return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
    }

    function yearOperationFraction(startDate, year) {
        if (!startDate) {
            return 1;
        }
        var y = Number(year);
        var daysInYear = isLeapYear(y) ? 366 : 365;
        var yearStart = new Date(y, 0, 1);
        var yearEnd = new Date(y, 11, 31);
        if (startDate > yearEnd) {
            return 0;
        }
        if (startDate <= yearStart) {
            return 1;
        }
        var msPerDay = 24 * 60 * 60 * 1000;
        var days = Math.round((yearEnd - startDate) / msPerDay) + 1;
        return days / daysInYear;
    }

    function usesPlanCapacityFallback(cfg, emptySample) {
        if (cfg.commissionYear != null && cfg.planYears.indexOf(cfg.commissionYear) >= 0) {
            return true;
        }
        var first = firstPositiveCapacityYear(cfg.capacityByYear);
        if (first != null && cfg.planYears.indexOf(first) >= 0) {
            return true;
        }
        if (cfg.currentYear != null) {
            if (cfg.commissionYear != null && cfg.commissionYear >= cfg.currentYear) {
                return true;
            }
            if (first != null && first >= cfg.currentYear) {
                return true;
            }
            if (
                emptySample &&
                cfg.sampleStart != null &&
                cfg.sampleEnd != null
            ) {
                if (
                    cfg.commissionYear != null &&
                    cfg.commissionYear >= cfg.sampleStart &&
                    cfg.commissionYear <= cfg.sampleEnd
                ) {
                    return true;
                }
                if (first != null && first >= cfg.sampleStart && first <= cfg.sampleEnd) {
                    return true;
                }
            }
        }
        return false;
    }

    function planExplained(year, ownerByYear, minValue, cfg, rampExcluded) {
        var ownerPos = positive(ownerByYear[year]);
        if (usesPlanCapacityFallback(cfg, minValue == null)) {
            if (ownerPos != null) {
                return { value: ownerPos, rule: PLAN_RULE_OWNER_IN_PLAN };
            }
            var cap = positive(cfg.capacityByYear && cfg.capacityByYear[year]);
            var factor = cfg.typeKey === "ses" ? 1.5 : cfg.typeKey === "ves" ? 2.5 : null;
            var fraction = yearOperationFraction(cfg.exploitationDate, year);
            if (cap != null && factor != null && fraction > 0) {
                var partial = fraction !== 1;
                return {
                    value: cap * factor * fraction,
                    rule:
                        cfg.typeKey === "ses"
                            ? partial
                                ? PLAN_RULE_CAPACITY_SES_PARTIAL
                                : PLAN_RULE_CAPACITY_SES
                            : partial
                              ? PLAN_RULE_CAPACITY_VES_PARTIAL
                              : PLAN_RULE_CAPACITY_VES
                };
            }
            return { value: null, rule: "" };
        }
        var yearCap = positive(cfg.capacityByYear && cfg.capacityByYear[year]);
        if (cfg.capacityByYear && yearCap == null) {
            return { value: null, rule: "" };
        }
        if (ownerPos != null && minValue != null) {
            var chosen = Math.min(ownerPos, minValue);
            var rule;
            if (ownerPos === minValue) {
                rule = PLAN_RULE_MIN_OWNER_SAMPLE_EQUAL;
            } else if (chosen === minValue) {
                rule = rampExcluded
                    ? PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE_RAMP
                    : PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE;
            } else {
                rule = PLAN_RULE_MIN_OWNER_SAMPLE_OWNER;
            }
            return { value: chosen, rule: rule };
        }
        if (minValue != null) {
            return {
                value: minValue,
                rule: rampExcluded ? PLAN_RULE_SEVEN_YEAR_MIN_RAMP : PLAN_RULE_SEVEN_YEAR_MIN
            };
        }
        if (ownerPos != null) {
            return { value: ownerPos, rule: PLAN_RULE_OWNER_POSITIVE };
        }
        return { value: null, rule: "" };
    }

    function chiimHours(energy, capacity, scale) {
        if (energy == null || capacity == null || capacity === 0) {
            return null;
        }
        return (energy * scale) / capacity;
    }

    function aesOwnNeedsPercent(ownNeeds, energy) {
        if (ownNeeds == null || energy == null || energy === 0) return null;
        return (ownNeeds / energy) * 100;
    }

    function aesDeliveryEnergy(ownNeedsEnergy, energy, percent) {
        var ownNeeds = ownNeedsEnergy != null ? aesOwnNeedsPercent(ownNeedsEnergy, energy) : percent;
        if (ownNeeds == null || energy == null) return null;
        return energy - (ownNeeds / 100) * energy;
    }

    function hydroOwnNeeds(coefficient, energy) {
        if (coefficient == null || energy == null) return null;
        return coefficient * energy;
    }

    function hydroDelivery(coefficient, energy) {
        var ownNeeds = hydroOwnNeeds(coefficient, energy);
        return ownNeeds == null ? null : energy - ownNeeds;
    }

    function setCellText(td, value, digits) {
        if (!td) {
            return;
        }
        td.textContent = value == null ? "–" : formatNum(value, digits);
        var rawTitle = formatRawTitle(value);
        if (rawTitle) {
            td.setAttribute("title", rawTitle);
            td.setAttribute("data-raw", rawTitle);
        } else {
            td.removeAttribute("title");
            td.removeAttribute("data-raw");
        }
    }

    function setPlanRuleTitle(el, rule, rawTitle) {
        if (!el) {
            return;
        }
        var isControl =
            el.tagName === "INPUT" || el.getAttribute("data-ves-deferred") === "1";
        if (rule) {
            el.setAttribute("title", rule);
            if (isControl) {
                el.setAttribute("data-plan-rule", rule);
            }
        } else if (rawTitle) {
            el.setAttribute("title", rawTitle);
            if (isControl) {
                el.removeAttribute("data-plan-rule");
            }
        } else {
            el.removeAttribute("title");
            if (isControl) {
                el.removeAttribute("data-plan-rule");
            }
        }
        if (rawTitle) {
            el.setAttribute("data-raw", rawTitle);
        } else {
            el.removeAttribute("data-raw");
        }
    }

    function setInputDisplay(inp, value, digits, rule) {
        if (!inp) {
            return;
        }
        var formatted = value == null ? "" : formatNum(value, digits);
        if (formatted === "–") {
            formatted = "";
        }
        inp.value = formatted;
        setPlanRuleTitle(inp, rule || "", formatRawTitle(value));
    }

    function energyRawForChiim(inp, td) {
        if (inp) {
            return readControlNumber(inp);
        }
        return cellRawNumber(td);
    }

    function stationMatches(st, agg) {
        if (agg.kind === "russia_total") {
            return true;
        }
        if (agg.kind === "est_total") {
            return st.estId === agg.estId;
        }
        if (agg.kind === "ues_total") {
            return st.uesId === agg.uesId;
        }
        if (agg.kind === "res_total") {
            return st.resId === agg.resId;
        }
        if (agg.kind === "rd_total") {
            return st.rdId === agg.rdId;
        }
        if (agg.kind === "type_total") {
            if (st.typeKey !== agg.typeKey) {
                return false;
            }
            return !agg.uesId || st.uesId === agg.uesId;
        }
        return false;
    }

    function initVesSesLiveTotals(table, cfg) {
        if (!table || table.__vesSesLiveBound) {
            return;
        }
        cfg = cfg || {};
        cfg.planYears = (cfg.planYears || []).map(Number);
        cfg.years = (cfg.years || []).map(Number);
        cfg.ownerYears = (cfg.ownerYears || cfg.planYears || []).map(Number);
        cfg.digits = cfg.digits == null ? 1 : Number(cfg.digits);
        cfg.chiimScale = cfg.chiimScale == null ? 1000 : Number(cfg.chiimScale);
        cfg.chiimDigits = cfg.chiimDigits == null ? -1 : Number(cfg.chiimDigits);
        cfg.coefficientMode = !!cfg.coefficientMode;

        var energyById = {};
        var chiimById = {};
        table.querySelectorAll("tr[data-station-id][data-ves-metric='energy']").forEach(function (tr) {
            energyById[attrId(tr, "data-station-id")] = tr;
        });
        table.querySelectorAll("tr[data-station-id][data-ves-metric='chiim']").forEach(function (tr) {
            chiimById[attrId(tr, "data-station-id")] = tr;
        });

        var stations = [];
        var stationById = {};
        table.querySelectorAll("tr[data-ves-station='1']").forEach(function (tr) {
            var id = attrId(tr, "data-station-id");
            var energyTr = energyById[id];
            var chiimTr = chiimById[id];
            var rec = {
                id: id,
                tr: tr,
                energyTr: energyTr,
                chiimTr: chiimTr,
                typeKey: attrId(tr, "data-type-key"),
                estId: attrId(tr, "data-est-id"),
                uesId: attrId(tr, "data-ues-id"),
                resId: attrId(tr, "data-res-id"),
                rdId: attrId(tr, "data-rd-id"),
                commissionYear: parseNum(tr.getAttribute("data-commission-year")),
                exploitationDateRaw: tr.getAttribute("data-exploitation-date") || "",
                dateInput: energyTr
                    ? energyTr.querySelector(
                          "input[data-kind='exploitation_date'], [data-ves-deferred='1'][data-kind='exploitation_date']"
                      )
                    : null,
                sampleEnergy: yearMapFromJson(tr.getAttribute("data-sample-energy")),
                ownerEnergy: yearMapFromJson(tr.getAttribute("data-owner-energy")),
                capacityTds: mapByYear(tr, "td[data-ves-col='capacity']"),
                energyInputs: mapControlsByYear(energyTr, "energy"),
                ownerInputs: mapControlsByYear(energyTr, "owner"),
                energyTds: mapByYear(energyTr, "td[data-ves-col='energy']"),
                ownerTds: mapByYear(energyTr, "td[data-ves-col='owner']"),
                chiimTds: mapByYear(chiimTr, "td[data-ves-col='chiim']"),
                ownNeedsEnergyInputs: mapByYear(table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='own_needs_energy']"), "input[data-kind='own_needs'], [data-ves-deferred='1'][data-kind='own_needs']"),
                ownNeedsEnergyTds: mapByYear(table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='own_needs_energy']"), "td[data-ves-col='own-needs-energy']"),
                ownNeedsPercentInputs: mapByYear(table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='own_needs']"), "input[data-kind='own_needs_percent'], [data-ves-deferred='1'][data-kind='own_needs_percent']"),
                ownNeedsTds: mapByYear(table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='own_needs']"), "td[data-ves-col='own-needs']"),
                deliveryTds: mapByYear(table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='delivery']"), "td[data-ves-col='delivery']"),
                coefficientInput: table.querySelector("tr[data-station-id='" + id + "'][data-ves-metric='own_needs'] input[data-kind='coefficient']"),
                minTd: energyTr ? energyTr.querySelector("td[data-ves-col='min']") : null
            };
            stations.push(rec);
            stationById[id] = rec;
        });

        var energyAggByKey = {};
        var chiimAggByKey = {};
        table.querySelectorAll("tr[data-ves-agg][data-ves-metric='energy']").forEach(function (tr) {
            energyAggByKey[attrId(tr, "data-ves-agg-key")] = tr;
        });
        table.querySelectorAll("tr[data-ves-agg][data-ves-metric='chiim']").forEach(function (tr) {
            chiimAggByKey[attrId(tr, "data-ves-agg-key")] = tr;
        });
        var aggs = [];
        table.querySelectorAll("tr[data-ves-agg][data-ves-metric='capacity']").forEach(function (tr) {
            if (tr.getAttribute("data-ves-live-locked") === "1") {
                return;
            }
            var key = attrId(tr, "data-ves-agg-key");
            var energyRow = energyAggByKey[key];
            var chiimRow = chiimAggByKey[key];
            var agg = {
                kind: attrId(tr, "data-ves-agg"),
                key: key,
                typeKey: attrId(tr, "data-type-key"),
                estId: attrId(tr, "data-est-id"),
                uesId: attrId(tr, "data-ues-id"),
                resId: attrId(tr, "data-res-id"),
                rdId: attrId(tr, "data-rd-id"),
                capacityTds: mapByYear(tr, "td[data-ves-col='capacity']"),
                energyTds: mapByYear(energyRow, "td[data-ves-col='energy']"),
                ownerTds: mapByYear(energyRow, "td[data-ves-col='owner']"),
                chiimTds: mapByYear(chiimRow, "td[data-ves-col='chiim']"),
                ownNeedsEnergyTds: mapByYear(table.querySelector("tr[data-ves-agg-key='" + key + "'][data-ves-metric='own_needs_energy']"), "td[data-ves-col='own-needs-energy']"),
                ownNeedsTds: mapByYear(table.querySelector("tr[data-ves-agg-key='" + key + "'][data-ves-metric='own_needs']"), "td[data-ves-col='own-needs']"),
                deliveryTds: mapByYear(table.querySelector("tr[data-ves-agg-key='" + key + "'][data-ves-metric='delivery']"), "td[data-ves-col='delivery']"),
                minTd: energyRow ? energyRow.querySelector("td[data-ves-col='min']") : null
            };
            agg.stations = stations.filter(function (st) {
                return stationMatches(st, agg);
            });
            aggs.push(agg);
        });

        function readOwnNeeds(st, year) {
            return energyRawForChiim(st.ownNeedsEnergyInputs[year], st.ownNeedsEnergyTds[year]);
        }

        function updateAesOwnNeedsPercent(st, year, energy) {
            var control = st.ownNeedsPercentInputs[year];
            var ownNeeds = readOwnNeeds(st, year);
            var calculated = ownNeeds != null;
            var percent = calculated ? aesOwnNeedsPercent(ownNeeds, energy) : readControlNumber(control);
            if (!control) {
                setCellText(st.ownNeedsTds[year], percent, cfg.digits);
                return percent;
            }
            if (calculated) {
                var display = percent == null ? "" : formatNum(percent, cfg.digits, true);
                if (isInputEl(control)) control.value = display;
                else control.textContent = display;
                control.setAttribute("data-raw", percent === 0 ? "0" : formatRawTitle(percent));
                control.setAttribute("data-orig", display);
                control.removeAttribute("data-dirty");
                control.setAttribute("data-readonly", "1");
            } else {
                control.removeAttribute("data-readonly");
            }
            control.setAttribute("aria-readonly", calculated ? "true" : "false");
            if (isInputEl(control)) control.readOnly = calculated;
            else control.setAttribute("tabindex", calculated ? "-1" : "0");
            return percent;
        }

        function readEnergy(st, year) {
            return energyRawForChiim(st.energyInputs[year], st.energyTds[year]);
        }

        function readOwner(st, year) {
            var inp = st.ownerInputs[year];
            if (inp) {
                return readControlNumber(inp);
            }
            return cellRawNumber(st.ownerTds[year]);
        }

        function updateStationDerived(st) {
            if (!st) {
                return;
            }
            var energyMap = {};
            Object.keys(st.sampleEnergy).forEach(function (key) {
                energyMap[key] = st.sampleEnergy[key];
            });
            var ownerMap = {};
            Object.keys(st.ownerEnergy).forEach(function (key) {
                ownerMap[key] = st.ownerEnergy[key];
            });
            var energyRaw = {};
            var capacityRaw = {};
            var coefficient = readControlNumber(st.coefficientInput);
            cfg.years.forEach(function (year) {
                var energyVal = readEnergy(st, year);
                energyRaw[year] = energyVal;
                if (cfg.sampleStart != null && year >= cfg.sampleStart && year <= cfg.sampleEnd) {
                    energyMap[year] = energyVal;
                }
                capacityRaw[year] = cellRawNumber(st.capacityTds[year]);
            });
            cfg.ownerYears.forEach(function (year) {
                var ownerVal = readOwner(st, year);
                if (ownerVal != null || st.ownerInputs[year]) {
                    ownerMap[year] = ownerVal;
                }
            });
            var stationCfg = {
                currentYear: cfg.currentYear,
                sampleStart: cfg.sampleStart,
                sampleEnd: cfg.sampleEnd,
                planYears: cfg.planYears,
                commissionYear: st.commissionYear,
                typeKey: st.typeKey,
                capacityByYear: capacityRaw,
                exploitationDate: parseExploitationDate(
                    (st.dateInput &&
                        (isInputEl(st.dateInput) ? st.dateInput.value : st.dateInput.textContent)) ||
                        st.exploitationDateRaw ||
                        ""
                )
            };
            var sample = minSampleResult(energyMap, stationCfg);
            var minValue = sample.value;
            setCellText(st.minTd, minValue, cfg.digits);
            var yearsToFill = cfg.planYears.slice();
            if (
                usesPlanCapacityFallback(stationCfg) &&
                cfg.currentYear != null &&
                yearsToFill.indexOf(cfg.currentYear) < 0
            ) {
                yearsToFill = [cfg.currentYear].concat(yearsToFill);
            }
            yearsToFill.forEach(function (year) {
                var inp = st.energyInputs[year];
                if (!inp || !inp.classList.contains("ves-ses-plan-calc-input")) {
                    return;
                }
                if ((inp.getAttribute("data-orig") || "") !== "") {
                    return;
                }
                if (inp.getAttribute("data-dirty") === "1") {
                    return;
                }
                if (document.activeElement === inp) {
                    return;
                }
                var explained = planExplained(
                    year,
                    ownerMap,
                    minValue,
                    stationCfg,
                    sample.rampExcluded
                );
                setControlDisplay(inp, explained.value, cfg.digits, explained.rule);
                setPlanRuleTitle(
                    st.energyTds[year],
                    explained.rule,
                    formatRawTitle(explained.value)
                );
                energyRaw[year] = explained.value;
            });
            cfg.years.forEach(function (year) {
                setCellText(
                    st.chiimTds[year],
                    chiimHours(energyRaw[year], capacityRaw[year], cfg.chiimScale),
                    cfg.chiimDigits
                );
                var percent = null;
                if (cfg.coefficientMode) {
                    setCellText(st.ownNeedsTds[year], hydroOwnNeeds(coefficient, energyRaw[year]), cfg.digits);
                } else {
                    percent = updateAesOwnNeedsPercent(st, year, energyRaw[year]);
                }
                setCellText(
                    st.deliveryTds[year],
                    cfg.coefficientMode
                        ? hydroDelivery(coefficient, energyRaw[year])
                        : aesDeliveryEnergy(readOwnNeeds(st, year), energyRaw[year], percent),
                    cfg.digits
                );
            });
        }

        function snapshotStation(st) {
            var energy = {};
            var capacity = {};
            var owner = {};
            var ownNeeds = {};
            var delivery = {};
            var coefficient = readControlNumber(st.coefficientInput);
            cfg.years.forEach(function (year) {
                energy[year] = readEnergy(st, year);
                capacity[year] = cellRawNumber(st.capacityTds[year]);
                ownNeeds[year] = cfg.coefficientMode
                    ? hydroOwnNeeds(coefficient, energy[year])
                    : readOwnNeeds(st, year);
                delivery[year] = cfg.coefficientMode
                    ? hydroDelivery(coefficient, energy[year])
                    : null;
            });
            cfg.ownerYears.forEach(function (year) {
                owner[year] = readOwner(st, year);
            });
            return {
                energy: energy,
                capacity: capacity,
                owner: owner,
                ownNeeds: ownNeeds,
                delivery: delivery,
                min: cellRawNumber(st.minTd)
            };
        }

        function recalcAggregates() {
            var snaps = {};
            stations.forEach(function (st) {
                snaps[st.id] = snapshotStation(st);
            });
            aggs.forEach(function (agg) {
                var energy = {};
                var capacity = {};
                var owner = {};
                var minSum = null;
                var ownNeeds = {};
                var delivery = {};
                cfg.years.forEach(function (year) {
                    energy[year] = null;
                    capacity[year] = null;
                    ownNeeds[year] = null;
                    delivery[year] = null;
                });
                cfg.ownerYears.forEach(function (year) {
                    owner[year] = null;
                });
                agg.stations.forEach(function (st) {
                    var snap = snaps[st.id];
                    if (!snap) {
                        return;
                    }
                    cfg.years.forEach(function (year) {
                        var eVal = snap.energy[year];
                        if (eVal != null) {
                            energy[year] = energy[year] == null ? eVal : energy[year] + eVal;
                        }
                        var cVal = snap.capacity[year];
                        if (cVal != null) {
                            capacity[year] = capacity[year] == null ? cVal : capacity[year] + cVal;
                        }
                        var ownNeedsVal = snap.ownNeeds[year];
                        if (ownNeedsVal != null) {
                            ownNeeds[year] = ownNeeds[year] == null ? ownNeedsVal : ownNeeds[year] + ownNeedsVal;
                        }
                        var deliveryVal = snap.delivery[year];
                        if (deliveryVal != null) {
                            delivery[year] = delivery[year] == null ? deliveryVal : delivery[year] + deliveryVal;
                        }
                    });
                    cfg.ownerYears.forEach(function (year) {
                        var oVal = snap.owner[year];
                        if (oVal != null) {
                            owner[year] = owner[year] == null ? oVal : owner[year] + oVal;
                        }
                    });
                    if (snap.min != null) {
                        minSum = minSum == null ? snap.min : minSum + snap.min;
                    }
                });
                cfg.years.forEach(function (year) {
                    setCellText(agg.ownNeedsEnergyTds[year], ownNeeds[year], cfg.digits);
                    setCellText(agg.capacityTds[year], capacity[year], cfg.digits);
                    setCellText(agg.energyTds[year], energy[year], cfg.digits);
                    setCellText(
                        agg.chiimTds[year],
                        chiimHours(energy[year], capacity[year], cfg.chiimScale),
                        cfg.chiimDigits
                    );
                    setCellText(
                        agg.ownNeedsTds[year],
                        cfg.coefficientMode
                            ? ownNeeds[year]
                            : aesOwnNeedsPercent(ownNeeds[year], energy[year]),
                        cfg.digits
                    );
                    setCellText(
                        agg.deliveryTds[year],
                        cfg.coefficientMode
                            ? delivery[year]
                            : aesDeliveryEnergy(ownNeeds[year], energy[year]),
                        cfg.digits
                    );
                });
                cfg.ownerYears.forEach(function (year) {
                    setCellText(agg.ownerTds[year], owner[year], cfg.digits);
                });
                setCellText(agg.minTd, minSum, cfg.digits);
            });
        }

        function stationFromInput(inp) {
            var row = inp && inp.closest("tr");
            return stationById[attrId(row, "data-station-id")] || null;
        }

        var aggTimer = 0;
        function scheduleAggregates() {
            if (aggTimer) {
                return;
            }
            aggTimer = window.setTimeout(function () {
                aggTimer = 0;
                recalcAggregates();
            }, 180);
        }

        function flushAggregates() {
            if (aggTimer) {
                window.clearTimeout(aggTimer);
                aggTimer = 0;
            }
            recalcAggregates();
        }

        table.addEventListener("input", function (event) {
            var inp = event.target;
            if (!inp || !inp.matches || !inp.matches("input.ves-ses-value, input.ves-ses-date-value")) {
                return;
            }
            if (inp.matches("input.ves-ses-value")) {
                inp.setAttribute("data-dirty", "1");
                if (inp.getAttribute("data-kind") === "energy") {
                    inp.classList.remove("ves-ses-plan-calc-input");
                    inp.removeAttribute("data-plan-rule");
                }
            }
            updateStationDerived(stationFromInput(inp));
            scheduleAggregates();
        });

        table.__vesSesLiveBound = true;
        window.armGsRefreshVesSesStationControl = function (el) {
            if (!el) {
                return null;
            }
            var row = el.closest("tr");
            var st = stationById[attrId(row, "data-station-id")];
            if (!st) {
                return null;
            }
            var kind = el.getAttribute("data-kind");
            var year = Number(el.getAttribute("data-year"));
            if (kind === "energy" && isFinite(year)) {
                st.energyInputs[year] = el;
            } else if (kind === "own_needs" && isFinite(year)) {
                st.ownNeedsEnergyInputs[year] = el;
            } else if (kind === "own_needs_percent" && isFinite(year)) {
                st.ownNeedsPercentInputs[year] = el;
            } else if (kind === "owner" && isFinite(year)) {
                st.ownerInputs[year] = el;
            } else if (kind === "exploitation_date") {
                st.dateInput = el;
            }
            return st;
        };
        window.armGsRecalcVesSesLive = function (stationId) {
            var st = stationId != null ? stationById[String(stationId)] : null;
            if (st) {
                updateStationDerived(st);
                flushAggregates();
                return;
            }
            stations.forEach(updateStationDerived);
            flushAggregates();
        };
    }

    window.initVesSesLiveTotals = initVesSesLiveTotals;
})();
