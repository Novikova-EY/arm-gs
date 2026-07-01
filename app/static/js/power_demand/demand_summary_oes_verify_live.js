/**
 * Сводка «Максимумы» по ОЭС (/power_demand/summary/oes/): пересчёт строк «Проверка для …»
 * при правке ячеек, участвующих в формуле (a − b по годам).
 */
(function () {
    var table = document.getElementById("powerDemandSummaryTable");
    if (!table) {
        return;
    }
    if (table.getAttribute("data-summary-view") !== "oes") {
        return;
    }
    if ((table.getAttribute("data-summary-route-variant") || "max") !== "max") {
        return;
    }

    var VERIFY_DECIMALS = 3;

    function parseCellNumber(td) {
        if (!td || td.classList.contains("summary-plan-empty")) {
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

    /** Расчётные максимумы (зелёные строки): до 3 знаков после запятой, группировка разрядов пробелом. */
    function formatVerifyMw(num) {
        if (!Number.isFinite(num)) {
            return "—";
        }
        var mult = Math.pow(10, VERIFY_DECIMALS);
        var rounded = Math.round(num * mult) / mult;
        var s = String(rounded);
        if (s.indexOf("e") !== -1 || s.indexOf("E") !== -1) {
            s = rounded.toFixed(VERIFY_DECIMALS);
        }
        var parts = s.split(".");
        var intPart = applyThousandGrouping(parts[0]);
        if (parts.length === 1) {
            return intPart;
        }
        var frac = parts[1].replace(/0+$/, "");
        return frac.length ? intPart + "," + frac : intPart;
    }

    /** Строки «Проверка …» (синие): целое в ячейке; в title — до VERIFY_DECIMALS знаков после запятой. */
    function applyThousandGrouping(s) {
        if (!s) {
            return s;
        }
        var sign = "";
        if (s.charAt(0) === "-") {
            sign = "-";
            s = s.slice(1);
        }
        return sign + s.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    }

    function formatVerifyRowInteger(num) {
        if (!Number.isFinite(num)) {
            return "—";
        }
        return applyThousandGrouping(String(Math.round(num)));
    }

    function setYearCellDisplay(td, text, fullNum) {
        if (!td) {
            return;
        }
        var tooltip = "";
        if (fullNum !== null && Number.isFinite(fullNum)) {
            tooltip = formatVerifyMw(fullNum);
            if (tooltip === "—") {
                tooltip = "";
            }
        }
        var inp = td.querySelector("input.pd-coeff-display-mw, input.fuel-param-input, textarea.fuel-param-input");
        if (inp) {
            inp.value = text;
            if (tooltip) {
                inp.setAttribute("title", tooltip);
            } else {
                inp.removeAttribute("title");
            }
            return;
        }
        td.textContent = text;
        if (tooltip) {
            td.setAttribute("title", tooltip);
        } else {
            td.removeAttribute("title");
        }
    }

    var cachedYears = null;
    var liveCalcMeta = null;

    function readLiveCalcMeta() {
        if (liveCalcMeta) {
            return liveCalcMeta;
        }
        var el = document.getElementById("pd-oes-live-calc-data");
        if (!el || !el.textContent) {
            liveCalcMeta = {
                ees_russia_ues_ids: [],
                default_perimeter_variant: "",
                res_to_sa_ids: {},
                tites_ues_ids: [],
            };
            return liveCalcMeta;
        }
        try {
            liveCalcMeta = JSON.parse(el.textContent);
        } catch (eMeta) {
            liveCalcMeta = {
                ees_russia_ues_ids: [],
                default_perimeter_variant: "",
                res_to_sa_ids: {},
                tites_ues_ids: [],
            };
        }
        if (!liveCalcMeta || typeof liveCalcMeta !== "object") {
            liveCalcMeta = {
                ees_russia_ues_ids: [],
                default_perimeter_variant: "",
                res_to_sa_ids: {},
                tites_ues_ids: [],
            };
        }
        if (!Array.isArray(liveCalcMeta.ees_russia_ues_ids)) {
            liveCalcMeta.ees_russia_ues_ids = [];
        }
        if (!Array.isArray(liveCalcMeta.tites_ues_ids)) {
            liveCalcMeta.tites_ues_ids = [];
        }
        if (!liveCalcMeta.res_to_sa_ids || typeof liveCalcMeta.res_to_sa_ids !== "object") {
            liveCalcMeta.res_to_sa_ids = {};
        }
        if (
            liveCalcMeta.new_territories_from_year === undefined ||
            liveCalcMeta.new_territories_from_year === null
        ) {
            liveCalcMeta.new_territories_from_year = 2023;
        }
        return liveCalcMeta;
    }

    function synchronousAreaIdsForRes(resId) {
        if (!resId) {
            return [];
        }
        var map = readLiveCalcMeta().res_to_sa_ids || {};
        var ids = map[String(resId)];
        return Array.isArray(ids) ? ids : [];
    }

    /** В агрегаты входят только строки RegionalEnergySystemDemandParameter (не энергорайоны). */
    function isResLevelAggregationContributorRow(tr) {
        return (
            (tr.getAttribute("data-demand-model-name") || "") ===
                "RegionalEnergySystemDemandParameter" &&
            !!tr.getAttribute("data-id-regional-energy-system")
        );
    }

    /** Сумма показателя по субъектам РФ для РЭС с несколькими субъектами (res_id → year → sum). */
    function subjectParameterSumsByResYear(parameterKey) {
        var out = {};
        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalDistrictDemandParameter"][data-parameter-key="' +
                    parameterKey +
                    '"]'
            )
            .forEach(function (rdTr) {
                var resId = rdTr.getAttribute("data-id-regional-energy-system");
                if (!resId) {
                    return;
                }
                rdTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (!out[resId]) {
                        out[resId] = {};
                    }
                    if (out[resId][y] === undefined) {
                        out[resId][y] = 0;
                    }
                    out[resId][y] += v;
                });
            });
        return out;
    }

    /** Значение РЭС для агрегата; при пустой строке РЭС — сумма по субъектам этой РЭС. */
    function resLevelAggregationCellValue(resTr, td, subjectFallback) {
        var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
        var v = parseCellNumber(td);
        if (v !== null) {
            return { year: y, value: v };
        }
        var resId = resTr.getAttribute("data-id-regional-energy-system");
        if (!resId || !subjectFallback[resId]) {
            return { year: y, value: null };
        }
        var fb = subjectFallback[resId][y];
        return { year: y, value: fb === undefined ? null : fb };
    }

    function uesRowMatchesEesRussiaVariant(uTr, targetVariant) {
        var code = uTr.getAttribute("data-perimeter-variant-code");
        if (!code) {
            return true;
        }
        var meta = readLiveCalcMeta();
        var target = targetVariant || meta.default_perimeter_variant || "";
        return String(code) === String(target);
    }

    function refreshEesRussiaCalculatedFromUes() {
        var meta = readLiveCalcMeta();
        var allowed = {};
        meta.ees_russia_ues_ids.forEach(function (id) {
            allowed[String(id)] = true;
        });
        if (!meta.ees_russia_ues_ids.length) {
            return;
        }
        var southUesId = meta.south_ues_id;
        var ntRdIds = Array.isArray(meta.nt_regional_district_ids)
            ? meta.nt_regional_district_ids
            : [];
        var ntCombinedOnEesByYear =
            southUesId !== null && southUesId !== undefined
                ? ntSubjectsCombinedOnEesSumByYear(southUesId, ntRdIds)
                : {};

        table.querySelectorAll('tr[data-is-block-start="1"]').forEach(function (startTr) {
            var dm = startTr.getAttribute("data-demand-model-name") || "";
            if (
                dm !== "EnergySystemTypeDemandParameter" &&
                dm !== "EesRussiaWithNtDemandParameter"
            ) {
                return;
            }
            var variant = startTr.getAttribute("data-perimeter-variant-code") || "";
            var block = collectBlockRows(startTr);
            var calcTr = findRowInBlock(block, "calculated_max_ees_russia_mw");
            if (!calcTr) {
                return;
            }
            getYearsFromTable().forEach(function (y) {
                var sum = 0;
                var has = false;
                table
                    .querySelectorAll(
                        'tr[data-demand-model-name="UnionEnergySystemDemandParameter"][data-parameter-key="combined_on_ees"]'
                    )
                    .forEach(function (uTr) {
                        var uid = uTr.getAttribute("data-id-union-energy-system");
                        if (!uid || !allowed[String(uid)]) {
                            return;
                        }
                        if (!uesRowMatchesEesRussiaVariant(uTr, variant)) {
                            return;
                        }
                        var cell = findYearCell(uTr, y);
                        var v = cell ? parseCellNumber(cell) : null;
                        if (v === null) {
                            return;
                        }
                        sum += v;
                        has = true;
                    });
                if (variant === "with_nt") {
                    var ntAdd = ntCombinedOnEesByYear[y];
                    if (ntAdd !== undefined) {
                        sum += ntAdd;
                        has = true;
                    }
                }
                var calcCell = findYearCell(calcTr, y);
                if (!calcCell) {
                    return;
                }
                if (!has) {
                    setYearCellDisplay(calcCell, "—", null);
                } else {
                    setYearCellDisplay(calcCell, formatVerifyMw(sum), sum);
                }
            });
        });
    }

    /** «Расчетный максимум …» (ЭЭС России) = первая СЗ − ветка ТИТЭС + энергорайоны формулы. */
    function sumAllTitesBranchMaxPowerByYear() {
        var meta = readLiveCalcMeta();
        var titesIds = {};
        (meta.tites_ues_ids || []).forEach(function (id) {
            titesIds[String(id)] = true;
        });
        var out = {};
        if (!Object.keys(titesIds).length) {
            return out;
        }
        table
            .querySelectorAll('tr[data-parameter-key="max_power"]')
            .forEach(function (tr) {
                var uid = tr.getAttribute("data-id-union-energy-system");
                if (!uid || !titesIds[String(uid)]) {
                    return;
                }
                tr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (out[y] === undefined) {
                        out[y] = 0;
                    }
                    out[y] += v;
                });
            });
        return out;
    }

    function sumEesAggregateFormulaTitesEuMaxPowerByYear(legacyAdjustments) {
        var meta = readLiveCalcMeta();
        var euIds = {};
        (meta.ees_aggregate_tites_eu_ids || []).forEach(function (id) {
            euIds[String(id)] = true;
        });
        var subtractMap = legacyAdjustments
            ? meta.ees_aggregate_tites_eu_subtract_mw || {}
            : meta.ees_aggregate_tites_eu_base_subtract_mw || {};
        var chaunThreshold =
            parseFloat(meta.ees_aggregate_tites_eu_chaun_unadjusted_max_power_mw || "62") || 62;
        var chaunSubtract = 6.6;
        var out = {};
        table
            .querySelectorAll(
                'tr[data-demand-model-name="EnergyUnitDemandParameter"][data-parameter-key="max_power"]'
            )
            .forEach(function (tr) {
                var euId = tr.getAttribute("data-id-energy-unit");
                if (!euId && tr.getAttribute("data-parent-fk-column") === "id_energy_unit") {
                    euId = tr.getAttribute("data-parent-id");
                }
                if (!euId || !euIds[String(euId)]) {
                    return;
                }
                tr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    var subtract = parseFloat(subtractMap[String(euId)] || "0") || 0;
                    if (
                        !legacyAdjustments &&
                        Math.abs(subtract - chaunSubtract) < 0.001 &&
                        v <= chaunThreshold
                    ) {
                        subtract = 0;
                    }
                    if (out[y] === undefined) {
                        out[y] = 0;
                    }
                    out[y] += v - subtract;
                });
            });
        return out;
    }

    function eesRussiaMaxPowerWithoutNtByYear() {
        var out = {};
        table.querySelectorAll('tr[data-is-block-start="1"]').forEach(function (startTr) {
            if (startTr.getAttribute("data-demand-model-name") !== "EnergySystemTypeDemandParameter") {
                return;
            }
            if (startTr.getAttribute("data-perimeter-variant-code") !== "without_nt") {
                return;
            }
            var block = collectBlockRows(startTr);
            var maxTr = findRowInBlock(block, "max_power");
            if (!maxTr) {
                return;
            }
            maxTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                var v = parseCellNumber(td);
                if (!Number.isFinite(y) || v === null) {
                    return;
                }
                out[y] = v;
            });
        });
        return out;
    }

    function firstSyncCalculatedMaxPowerByYear(variant) {
        var meta = readLiveCalcMeta();
        var firstSaId =
            meta.first_sync_area_id !== null && meta.first_sync_area_id !== undefined
                ? String(meta.first_sync_area_id)
                : null;
        var out = {};
        if (!firstSaId) {
            return out;
        }
        table
            .querySelectorAll(
                'tr[data-demand-model-name="SynchronousAreaDemandParameter"][data-parameter-key="calculated_max_power_mw"]'
            )
            .forEach(function (tr) {
                if (String(tr.getAttribute("data-id-synchronous-area") || "") !== firstSaId) {
                    return;
                }
                if ((tr.getAttribute("data-perimeter-variant-code") || "") !== (variant || "")) {
                    return;
                }
                tr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    out[y] = v;
                });
            });
        return out;
    }

    function firstSyncMinusTitesFormulaEesPartByYear() {
        var titesSumByYear = sumAllTitesBranchMaxPowerByYear();
        var firstSaByYear = firstSyncCalculatedMaxPowerByYear("without_nt");
        var meta = readLiveCalcMeta();
        var titesCorrection =
            parseFloat(meta.ees_formula_tites_branch_subtract_correction_mw || "21.6") || 0;
        var out = {};
        getYearsFromTable().forEach(function (y) {
            var fs = firstSaByYear[y];
            var tb = titesSumByYear[y];
            if (fs === undefined && tb === undefined) {
                return;
            }
            out[y] = (fs || 0) - ((tb || 0) - titesCorrection);
        });
        return out;
    }

    /** «Расчетный максимум …» (ЭЭС России без НТ) по годам. */
    function eesCalculatedMaxPowerConsumptionBaseByYear() {
        var meta = readLiveCalcMeta();
        var threshold =
            parseFloat(meta.ees_formula_use_legacy_first_sa_threshold_mw || "1500") || 1500;
        var formulaEes = firstSyncMinusTitesFormulaEesPartByYear();
        var eesRow = eesRussiaMaxPowerWithoutNtByYear();
        var euLegacy = sumEesAggregateFormulaTitesEuMaxPowerByYear(true);
        var euBase = sumEesAggregateFormulaTitesEuMaxPowerByYear(false);
        var out = {};
        getYearsFromTable().forEach(function (y) {
            var fe = formulaEes[y];
            var er = eesRow[y];
            if (fe === undefined && er === undefined) {
                return;
            }
            var useLegacy =
                fe !== undefined &&
                er !== undefined &&
                er > fe + threshold;
            var eesPart;
            var euPart;
            if (useLegacy) {
                eesPart = fe;
                euPart = euLegacy[y] || 0;
            } else if (er !== undefined) {
                eesPart = er;
                euPart = euBase[y] || 0;
            } else {
                eesPart = fe || 0;
                euPart = euLegacy[y] || 0;
            }
            out[y] = eesPart + euPart;
        });
        return out;
    }

    function refreshEesCalculatedMaxPowerConsumption() {
        var baseByYear = eesCalculatedMaxPowerConsumptionBaseByYear();
        var meta = readLiveCalcMeta();
        var southUesId = meta.south_ues_id;
        var ntRdIds = Array.isArray(meta.nt_regional_district_ids)
            ? meta.nt_regional_district_ids
            : [];
        var ntCombinedOnEsByYear =
            southUesId !== null && southUesId !== undefined
                ? ntSubjectsCombinedOnEsSumByYear(southUesId, ntRdIds)
                : {};
        table.querySelectorAll('tr[data-is-block-start="1"]').forEach(function (startTr) {
            if (startTr.getAttribute("data-demand-model-name") !== "EesRussiaDemandParameter") {
                return;
            }
            var variant = startTr.getAttribute("data-perimeter-variant-code") || "";
            var block = collectBlockRows(startTr);
            var calcTr = findRowInBlock(block, "calculated_max_power_consumption_mw");
            if (!calcTr) {
                return;
            }
            getYearsFromTable().forEach(function (y) {
                var base = baseByYear[y];
                var calcCell = findYearCell(calcTr, y);
                if (!calcCell) {
                    return;
                }
                if (base === undefined) {
                    setYearCellDisplay(calcCell, "—", null);
                    return;
                }
                var total = base;
                if (variant === "with_nt") {
                    var ntAdd = ntCombinedOnEsByYear[y];
                    if (ntAdd !== undefined) {
                        total += ntAdd;
                    }
                }
                setYearCellDisplay(calcCell, formatVerifyMw(total), total);
            });
        });
    }

    function getYearsFromTable() {
        if (cachedYears) {
            return cachedYears;
        }
        var years = [];
        var seen = {};
        table.querySelectorAll("thead th.summary-year-col[data-ec-summary-col-year]").forEach(function (th) {
            var y = parseInt(String(th.getAttribute("data-ec-summary-col-year") || ""), 10);
            if (!Number.isFinite(y) || seen[y]) {
                return;
            }
            seen[y] = true;
            years.push(y);
        });
        years.sort(function (a, b) {
            return a - b;
        });
        cachedYears = years;
        return years;
    }

    function collectBlockRows(startTr) {
        var blockSize = parseInt(startTr.getAttribute("data-entity-block-size") || "1", 10);
        if (blockSize < 1) {
            blockSize = 1;
        }
        var blockRows = [];
        var tr = startTr;
        while (blockRows.length < blockSize && tr) {
            if (tr.classList.contains("summary-row-param")) {
                blockRows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        return blockRows;
    }

    function findRowInBlock(block, pk) {
        for (var i = 0; i < block.length; i++) {
            if ((block[i].getAttribute("data-parameter-key") || "") === pk) {
                return block[i];
            }
        }
        return null;
    }

    function findYearCell(tr, year) {
        return tr.querySelector('td[data-ec-summary-col-year="' + year + '"]');
    }

    function refreshVerifyInBlock(block) {
        block.forEach(function (tr) {
            if (!tr.classList.contains("pd-pd-verify-for-row")) {
                return;
            }
            var aKey = tr.getAttribute("data-pd-pd-verify-a");
            var bKey = tr.getAttribute("data-pd-pd-verify-b");
            if (!aKey || !bKey) {
                return;
            }
            var aTr = findRowInBlock(block, aKey);
            var bTr = findRowInBlock(block, bKey);
            if (!aTr || !bTr) {
                return;
            }
            getYearsFromTable().forEach(function (y) {
                var aCell = findYearCell(aTr, y);
                var bCell = findYearCell(bTr, y);
                var vCell = findYearCell(tr, y);
                if (!vCell) {
                    return;
                }
                var av = aCell ? parseCellNumber(aCell) : null;
                var bv = bCell ? parseCellNumber(bCell) : null;
                if (av === null || bv === null) {
                    setYearCellDisplay(vCell, "—", null);
                } else {
                    var d = av - bv;
                    setYearCellDisplay(vCell, formatVerifyRowInteger(d), d);
                }
            });
        });
    }

    function perimeterVariantIsWithNt(code) {
        return String(code || "").indexOf("with_nt") === 0;
    }

    function southUesWithNtFormulaYear(y, meta) {
        var fromYear = parseInt(String((meta || {}).new_territories_from_year || "2023"), 10);
        return Number.isFinite(fromYear) && Number(y) >= fromYear;
    }

    function ntSubjectsCombinedOnEsSumByYear(southUesId, ntRdIds) {
        var out = {};
        if (!southUesId || !ntRdIds || !ntRdIds.length) {
            return out;
        }
        var allowed = {};
        ntRdIds.forEach(function (id) {
            allowed[String(id)] = true;
        });
        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalDistrictDemandParameter"][data-parameter-key="combined_on_es"]'
            )
            .forEach(function (rdTr) {
                if (
                    String(rdTr.getAttribute("data-id-union-energy-system") || "") !==
                    String(southUesId)
                ) {
                    return;
                }
                var rdId = rdTr.getAttribute("data-id-regional-district");
                if (!rdId || !allowed[String(rdId)]) {
                    return;
                }
                rdTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (out[y] === undefined) {
                        out[y] = 0;
                    }
                    out[y] += v;
                });
            });
        return out;
    }

    function ntSubjectsCombinedOnEesSumByYear(southUesId, ntRdIds) {
        var out = {};
        if (!southUesId || !ntRdIds || !ntRdIds.length) {
            return out;
        }
        var allowed = {};
        ntRdIds.forEach(function (id) {
            allowed[String(id)] = true;
        });
        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalDistrictDemandParameter"][data-parameter-key="combined_on_ees"]'
            )
            .forEach(function (rdTr) {
                if (
                    String(rdTr.getAttribute("data-id-union-energy-system") || "") !==
                    String(southUesId)
                ) {
                    return;
                }
                var rdId = rdTr.getAttribute("data-id-regional-district");
                if (!rdId || !allowed[String(rdId)]) {
                    return;
                }
                rdTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (out[y] === undefined) {
                        out[y] = 0;
                    }
                    out[y] += v;
                });
            });
        return out;
    }

    /** Расчётные строки УЭС = сумма по РЭС того же ОЭС (как enrich_oes_summary_calculated_*). */
    function refreshUesCalculatedFromRes() {
        var meta = readLiveCalcMeta();
        var southUesId = meta.south_ues_id;
        var ntRdIds = Array.isArray(meta.nt_regional_district_ids)
            ? meta.nt_regional_district_ids
            : [];
        var ntCombinedOnEsByYear =
            southUesId !== null && southUesId !== undefined
                ? ntSubjectsCombinedOnEsSumByYear(southUesId, ntRdIds)
                : {};
        var ntCombinedOnEesByYear =
            southUesId !== null && southUesId !== undefined
                ? ntSubjectsCombinedOnEesSumByYear(southUesId, ntRdIds)
                : {};
        var sumsOes = {};
        var sumsEes = {};
        var subjectOes = subjectParameterSumsByResYear("combined_on_oes");
        var subjectEes = subjectParameterSumsByResYear("combined_on_ees");

        function addSum(store, uid, year, val) {
            if (!store[uid]) {
                store[uid] = {};
            }
            if (store[uid][year] === undefined) {
                store[uid][year] = 0;
            }
            store[uid][year] += val;
        }

        table
            .querySelectorAll('tr[data-demand-model-name="RegionalEnergySystemDemandParameter"]')
            .forEach(function (rTr) {
                if (!isResLevelAggregationContributorRow(rTr)) {
                    return;
                }
                var pk = rTr.getAttribute("data-parameter-key") || "";
                var store = null;
                if (pk === "combined_on_oes") {
                    store = sumsOes;
                } else if (pk === "combined_on_ees") {
                    store = sumsEes;
                } else {
                    return;
                }
                var uid = rTr.getAttribute("data-id-union-energy-system");
                if (!uid) {
                    return;
                }
                var subjectFallback = pk === "combined_on_oes" ? subjectOes : subjectEes;
                rTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var parsed = resLevelAggregationCellValue(rTr, td, subjectFallback);
                    var y = parsed.year;
                    var v = parsed.value;
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    addSum(store, uid, y, v);
                });
            });

        function applyUes(pk, store, ntAddonByYear) {
            table
                .querySelectorAll(
                    'tr[data-demand-model-name="UnionEnergySystemDemandParameter"][data-parameter-key="' +
                        pk +
                        '"]'
                )
                .forEach(function (uTr) {
                    var uid = uTr.getAttribute("data-id-union-energy-system");
                    if (!uid) {
                        return;
                    }
                    var variantCode = uTr.getAttribute("data-perimeter-variant-code") || "";
                    var isSouthWithNt =
                        southUesId !== null &&
                        southUesId !== undefined &&
                        String(uid) === String(southUesId) &&
                        perimeterVariantIsWithNt(variantCode);
                    getYearsFromTable().forEach(function (y) {
                        var cell = findYearCell(uTr, y);
                        if (!cell) {
                            return;
                        }
                        if (isSouthWithNt && !southUesWithNtFormulaYear(y, meta)) {
                            setYearCellDisplay(cell, "—", null);
                            return;
                        }
                        var byYear = store[uid];
                        var total = byYear ? byYear[y] : undefined;
                        if (isSouthWithNt && ntAddonByYear) {
                            var ntAdd = ntAddonByYear[y];
                            if (ntAdd !== undefined) {
                                total =
                                    total === undefined
                                        ? ntAdd
                                        : total + ntAdd;
                            }
                        }
                        if (total === undefined) {
                            setYearCellDisplay(cell, "—", null);
                        } else {
                            setYearCellDisplay(cell, formatVerifyMw(total), total);
                        }
                    });
                });
        }

        applyUes("calculated_max_power_mw", sumsOes, ntCombinedOnEsByYear);
        applyUes("calculated_combined_on_ees_mw", sumsEes, ntCombinedOnEesByYear);
    }

    /** Вторая синхронная зона = показатели ОЭС Востока (расчётная строка, только отображение). */
    function findUesEastRow(parameterKey) {
        var meta = readLiveCalcMeta();
        var uesEastId =
            meta.ues_east_id !== null && meta.ues_east_id !== undefined
                ? String(meta.ues_east_id)
                : null;
        if (!uesEastId) {
            return null;
        }
        return table.querySelector(
            'tr[data-demand-model-name="UnionEnergySystemDemandParameter"][data-parameter-key="' +
                parameterKey +
                '"][data-id-union-energy-system="' +
                uesEastId +
                '"]'
        );
    }

    function copyYearCellsFromReference(sourceTr, targetTr, formatNumeric) {
        if (!sourceTr || !targetTr) {
            return;
        }
        getYearsFromTable().forEach(function (y) {
            var sourceCell = findYearCell(sourceTr, y);
            var targetCell = findYearCell(targetTr, y);
            if (!targetCell) {
                return;
            }
            if (!sourceCell) {
                setYearCellDisplay(targetCell, "—", null);
                return;
            }
            if (formatNumeric) {
                var v = parseCellNumber(sourceCell);
                if (v === null) {
                    setYearCellDisplay(targetCell, "—", null);
                } else {
                    setYearCellDisplay(targetCell, formatVerifyMw(v), v);
                }
            } else {
                var inp = sourceCell.querySelector("input, textarea");
                var text = inp
                    ? String(inp.value || "").trim()
                    : String(sourceCell.textContent || "").trim();
                setYearCellDisplay(targetCell, text || "—", null);
            }
        });
        var sourceHist = sourceTr.querySelector("td.summary-hist-cell");
        var targetHist = targetTr.querySelector("td.summary-hist-cell");
        if (sourceHist && targetHist && !targetHist.classList.contains("summary-hist-cell-disabled")) {
            var histInp = sourceHist.querySelector("input, textarea");
            var histText = histInp
                ? String(histInp.value || "").trim()
                : String(sourceHist.textContent || "").trim();
            var targetHistInp = targetHist.querySelector("input, textarea");
            if (targetHistInp) {
                targetHistInp.value = histText;
            } else {
                targetHist.textContent = histText;
            }
        }
    }

    function refreshSecondSaFromUesEast() {
        var meta = readLiveCalcMeta();
        var secondSaId =
            meta.second_sync_area_id !== null && meta.second_sync_area_id !== undefined
                ? String(meta.second_sync_area_id)
                : null;
        if (!secondSaId) {
            return;
        }
        var mappings = {
            max_power: { source: "max_power", numeric: true },
            calculated_max_power_mw: { source: "calculated_max_power_mw", numeric: true },
            peak_datetime: { source: "peak_datetime", numeric: false },
            avg_temp: { source: "avg_temp", numeric: true },
            combined_on_ees: { source: "combined_on_ees", numeric: true },
            calculated_max_sa_mw: { source: "calculated_combined_on_ees_mw", numeric: true },
        };
        Object.keys(mappings).forEach(function (targetPk) {
            var spec = mappings[targetPk];
            var sourceTr = findUesEastRow(spec.source);
            var targetTr = table.querySelector(
                'tr[data-demand-model-name="SynchronousAreaDemandParameter"][data-parameter-key="' +
                    targetPk +
                    '"][data-id-synchronous-area="' +
                    secondSaId +
                    '"]'
            );
            copyYearCellsFromReference(sourceTr, targetTr, spec.numeric);
        });
    }

    /** Расчётный максимум синхронной зоны: для 2-й СЗ — ОЭС Востока; для Калининграда — ЭС Калининградской области; иначе — сумма «Максимум …». */
    function refreshSaCalculatedMaxPowerFromRes() {
        var meta = readLiveCalcMeta();
        var secondSaId =
            meta.second_sync_area_id !== null && meta.second_sync_area_id !== undefined
                ? String(meta.second_sync_area_id)
                : null;
        var kaliningradSaId =
            meta.kaliningrad_sync_area_id !== null && meta.kaliningrad_sync_area_id !== undefined
                ? String(meta.kaliningrad_sync_area_id)
                : null;
        var kaliningradEsId =
            meta.kaliningrad_es_id !== null && meta.kaliningrad_es_id !== undefined
                ? String(meta.kaliningrad_es_id)
                : null;
        var sumsMax = {};
        var sumsOes = {};
        var kaliningradMax = {};
        var subjectOes = subjectParameterSumsByResYear("combined_on_oes");

        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalEnergySystemDemandParameter"][data-parameter-key="max_power"]'
            )
            .forEach(function (rTr) {
                if (!isResLevelAggregationContributorRow(rTr)) {
                    return;
                }
                var resId = rTr.getAttribute("data-id-regional-energy-system");
                var saIds = synchronousAreaIdsForRes(resId);
                if (!resId) {
                    return;
                }
                rTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var y = parseInt(String(td.getAttribute("data-ec-summary-col-year") || ""), 10);
                    var v = parseCellNumber(td);
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (kaliningradEsId && resId === kaliningradEsId) {
                        kaliningradMax[y] = v;
                    }
                    if (!saIds.length) {
                        return;
                    }
                    saIds.forEach(function (said) {
                        if (!sumsMax[said]) {
                            sumsMax[said] = {};
                        }
                        if (sumsMax[said][y] === undefined) {
                            sumsMax[said][y] = 0;
                        }
                        sumsMax[said][y] += v;
                    });
                });
            });

        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalEnergySystemDemandParameter"][data-parameter-key="combined_on_oes"]'
            )
            .forEach(function (rTr) {
                if (!isResLevelAggregationContributorRow(rTr)) {
                    return;
                }
                var resId = rTr.getAttribute("data-id-regional-energy-system");
                var saIds = synchronousAreaIdsForRes(resId);
                if (!saIds.length) {
                    return;
                }
                rTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var parsed = resLevelAggregationCellValue(rTr, td, subjectOes);
                    var y = parsed.year;
                    var v = parsed.value;
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    saIds.forEach(function (said) {
                        if (!sumsOes[said]) {
                            sumsOes[said] = {};
                        }
                        if (sumsOes[said][y] === undefined) {
                            sumsOes[said][y] = 0;
                        }
                        sumsOes[said][y] += v;
                    });
                });
            });

        table
            .querySelectorAll(
                'tr[data-demand-model-name="SynchronousAreaDemandParameter"][data-parameter-key="calculated_max_power_mw"]'
            )
            .forEach(function (saTr) {
                var said = saTr.getAttribute("data-id-synchronous-area");
                if (!said) {
                    return;
                }
                var store;
                if (kaliningradSaId && said === kaliningradSaId && kaliningradEsId) {
                    store = { [kaliningradSaId]: kaliningradMax };
                } else if (secondSaId && said === secondSaId) {
                    return;
                } else {
                    store = sumsMax;
                }
                getYearsFromTable().forEach(function (y) {
                    var cell = findYearCell(saTr, y);
                    if (!cell) {
                        return;
                    }
                    var byYear = store[said];
                    var total = byYear ? byYear[y] : undefined;
                    if (total === undefined) {
                        setYearCellDisplay(cell, "—", null);
                    } else {
                        setYearCellDisplay(cell, formatVerifyMw(total), total);
                    }
                });
            });
    }

    /** Расчётный совмещённый максимум СЗ на ЕЭС: для 2-й СЗ — ОЭС Востока; для Калининграда — ЭС Калининградской области; иначе — сумма по РЭС зоны. */
    function refreshSaCalculatedFromRes() {
        var meta = readLiveCalcMeta();
        var secondSaId =
            meta.second_sync_area_id !== null && meta.second_sync_area_id !== undefined
                ? String(meta.second_sync_area_id)
                : null;
        var kaliningradSaId =
            meta.kaliningrad_sync_area_id !== null && meta.kaliningrad_sync_area_id !== undefined
                ? String(meta.kaliningrad_sync_area_id)
                : null;
        var kaliningradEsId =
            meta.kaliningrad_es_id !== null && meta.kaliningrad_es_id !== undefined
                ? String(meta.kaliningrad_es_id)
                : null;
        var sums = {};
        var kaliningradEes = {};
        var subjectEes = subjectParameterSumsByResYear("combined_on_ees");

        table
            .querySelectorAll(
                'tr[data-demand-model-name="RegionalEnergySystemDemandParameter"][data-parameter-key="combined_on_ees"]'
            )
            .forEach(function (rTr) {
                if (!isResLevelAggregationContributorRow(rTr)) {
                    return;
                }
                var resId = rTr.getAttribute("data-id-regional-energy-system");
                var saIds = synchronousAreaIdsForRes(resId);
                if (!resId) {
                    return;
                }
                rTr.querySelectorAll("td[data-ec-summary-col-year]").forEach(function (td) {
                    var parsed = resLevelAggregationCellValue(rTr, td, subjectEes);
                    var y = parsed.year;
                    var v = parsed.value;
                    if (!Number.isFinite(y) || v === null) {
                        return;
                    }
                    if (kaliningradEsId && resId === kaliningradEsId) {
                        kaliningradEes[y] = v;
                    }
                    if (!saIds.length) {
                        return;
                    }
                    saIds.forEach(function (said) {
                        if (!sums[said]) {
                            sums[said] = {};
                        }
                        if (sums[said][y] === undefined) {
                            sums[said][y] = 0;
                        }
                        sums[said][y] += v;
                    });
                });
            });

        table
            .querySelectorAll(
                'tr[data-demand-model-name="SynchronousAreaDemandParameter"][data-parameter-key="calculated_max_sa_mw"]'
            )
            .forEach(function (saTr) {
                var said = saTr.getAttribute("data-id-synchronous-area");
                if (!said) {
                    return;
                }
                var byYearStore;
                if (kaliningradSaId && said === kaliningradSaId && kaliningradEsId) {
                    byYearStore = { [kaliningradSaId]: kaliningradEes };
                } else if (secondSaId && said === secondSaId) {
                    return;
                } else {
                    byYearStore = sums;
                }
                getYearsFromTable().forEach(function (y) {
                    var cell = findYearCell(saTr, y);
                    if (!cell) {
                        return;
                    }
                    var byYear = byYearStore[said];
                    var total = byYear ? byYear[y] : undefined;
                    if (total === undefined) {
                        setYearCellDisplay(cell, "—", null);
                    } else {
                        setYearCellDisplay(cell, formatVerifyMw(total), total);
                    }
                });
            });
    }

    function refreshAllVerification() {
        refreshUesCalculatedFromRes();
        refreshSaCalculatedMaxPowerFromRes();
        refreshSaCalculatedFromRes();
        refreshSecondSaFromUesEast();
        refreshEesRussiaCalculatedFromUes();
        refreshEesCalculatedMaxPowerConsumption();
        table.querySelectorAll('tr[data-is-block-start="1"]').forEach(function (startTr) {
            refreshVerifyInBlock(collectBlockRows(startTr));
        });
    }

    function onEditableInput(e) {
        var t = e.target;
        if (!t || !t.classList || !t.classList.contains("fuel-param-input")) {
            return;
        }
        refreshAllVerification();
    }

    table.addEventListener("input", onEditableInput);
    table.addEventListener("change", onEditableInput);

    window.__pdPdOesMaxRefreshVerification = refreshAllVerification;

    function startVerifyLive() {
        refreshAllVerification();
    }

    if (window.__pdSummaryRowsReady && typeof window.__pdSummaryRowsReady.then === "function") {
        window.__pdSummaryRowsReady.then(startVerifyLive, function () { /* */ });
    } else {
        startVerifyLive();
    }

    document.addEventListener("pd-summary-rows-rendered", function () {
        if (window.__pdPdSummaryVerificationMode === true) {
            refreshAllVerification();
        }
    });
})();
