(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        const table = document.querySelector(".power-demand-summary-table[data-save-cell-url]");
        const saveBtn = document.getElementById("demandSummarySaveBtn");
        if (!table || !saveBtn) return;
        const saveUrl = table.dataset.saveCellUrl;
        const selector = '.fuel-param-input[data-model][data-slice], input.pd-coeff-medium-k-input[data-model][data-slice][data-parameter-key^="coeff_k_"], .pd-ec-perimeter-variant-select';
        const headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": table.dataset.csrfToken
        };

        async function post(url, payload) {
            const response = await fetch(url, {
                method: "POST", credentials: "same-origin", headers: headers,
                body: JSON.stringify(payload)
            });
            const data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || !data.ok) {
                throw new Error(data && data.error || "Не удалось сохранить данные.");
            }
            const before = response.headers.get("X-Consumption-Revision-Before");
            const revision = response.headers.get("X-Consumption-Revision");
            if (before && revision) {
                document.dispatchEvent(new CustomEvent("energy-consumption:saved", {
                    detail: {before: before, revision: revision}
                }));
            }
            return data;
        }

        function parsePeakDatetimeSummary(val) {
            var lines = String(val || "").split(/\r?\n/);
            var s = "";
            for (var li = 0; li < lines.length; li++) {
                var t = lines[li].trim();
                if (t) {
                    s = t;
                    break;
                }
            }
            if (!s) {
                s = String(val || "").trim();
            }
            if (!s) return null;
            if (/^\d{4}$/.test(s)) {
                var yy = parseInt(s, 10);
                if (yy >= 1000 && yy <= 9999) {
                    return new Date(yy, 0, 1, 0, 0, 0, 0);
                }
                return null;
            }
            var m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/.exec(s);
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

        function perimeterVariantYearOutOfRange(tr, yearNum) {
            if (!tr || Number.isNaN(yearNum)) {
                return false;
            }
            var fromRaw = tr.getAttribute("data-perimeter-variant-from-year");
            if (fromRaw !== null && fromRaw !== "") {
                var fromY = parseInt(fromRaw, 10);
                if (!Number.isNaN(fromY) && yearNum < fromY) {
                    return true;
                }
            }
            var toRaw = tr.getAttribute("data-perimeter-variant-to-year");
            if (toRaw !== null && toRaw !== "") {
                var toY = parseInt(toRaw, 10);
                if (!Number.isNaN(toY) && yearNum > toY) {
                    return true;
                }
            }
            return false;
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
                throw new Error("Укажите дату в формате ДД.ММ.ГГГГ ЧЧ:ММ или год (ГГГГ).");
            }
            var colY = parseInt(sl, 10);
            if (!Number.isNaN(colY) && pdt.getFullYear() !== colY) {
                throw new Error("Год даты должен совпадать с годом столбца.");
            }
            return true;
        }

        function collectSummaryBlockRows(startTr) {
            var blockSize = parseInt(startTr.getAttribute("data-entity-block-size") || "1", 10);
            if (blockSize < 1) {
                blockSize = 1;
            }
            var blockRows = [];
            var tr = startTr;
            for (var j = 0; j < blockSize && tr; j++) {
                if (!tr.classList.contains("summary-row-param")) {
                    break;
                }
                blockRows.push(tr);
                tr = tr.nextElementSibling;
            }
            return blockRows;
        }

        function findSummaryBlockStartTr(fromTr) {
            if (fromTr.hasAttribute("data-is-block-start")) {
                return fromTr;
            }
            var t = fromTr.previousElementSibling;
            while (t) {
                if (t.classList.contains("summary-row-param") && t.hasAttribute("data-is-block-start")) {
                    return t;
                }
                t = t.previousElementSibling;
            }
            return fromTr;
        }

        function findBlockVariantSelect(fromTr) {
            var start = findSummaryBlockStartTr(fromTr);
            var blockRows = collectSummaryBlockRows(start);
            for (var i = 0; i < blockRows.length; i++) {
                var sel = blockRows[i].querySelector(
                    ".pd-ec-perimeter-variant-select:not(.pd-ec-formula-variant-select)"
                );
                if (sel) {
                    return sel;
                }
            }
            for (var j = 0; j < blockRows.length; j++) {
                var sel2 = blockRows[j].querySelector(".pd-ec-formula-variant-select");
                if (sel2) {
                    return sel2;
                }
            }
            return null;
        }

        function perimeterVariantPayloadValue(fromTr) {
            var tr = fromTr.closest("tr");
            var sel = findBlockVariantSelect(tr);
            if (sel) {
                return sel.value || null;
            }
            if (tr && tr.hasAttribute("data-demand-model-name")) {
                return tr.getAttribute("data-perimeter-variant-code");
            }
            return null;
        }


        const live = window.bindConsumptionLiveSave(table, selector, async function (field) {
            const value = field.value;
            if (value === (field.dataset.initial || "")) return;
            if (field.matches(".pd-ec-perimeter-variant-select")) {
                const sel = field;
                const blockKind = sel.getAttribute("data-block-kind") || "base";
                const variantUrl = table.dataset.savePerimeterVariantUrl || "";
                const blockVariantUrl = table.dataset.saveBlockVariantUrl || "";
                const url = blockVariantUrl || variantUrl;
                if (!url) throw new Error("Не настроен URL сохранения варианта периметра.");
                const vPayload = {
                    demand_model_name: sel.getAttribute("data-demand-model-name") || "",
                    perimeter_variant_code: value || null,
                    block_kind: blockKind
                };
                if (blockVariantUrl) {
                    vPayload.block_kind = blockKind;
                    vPayload.from_variant_code = sel.getAttribute("data-initial") || null;
                } else {
                    vPayload.from_variant_code = sel.getAttribute("data-initial") || null;
                    vPayload.to_variant_code = value || null;
                    delete vPayload.perimeter_variant_code;
                    delete vPayload.block_kind;
                }
                const vPfk = sel.getAttribute("data-parent-fk");
                if (vPfk) {
                    vPayload.parent_fk_column = vPfk;
                }
                const vPid = sel.getAttribute("data-parent-id");
                if (vPid !== null && vPid !== "") {
                    vPayload.parent_id = parseInt(vPid, 10);
                }
                const vScope = sel.getAttribute("data-block-scope");
                if (vScope) {
                    vPayload.block_scope = vScope;
                }
                if (table.dataset.summaryLogScope) {
                    vPayload.summary_log_scope = table.dataset.summaryLogScope;
                }
                if (!vPayload.demand_model_name) {
                    throw new Error("Не указана модель параметров.");
                }

                await post(url, vPayload);
            } else {
                const inp = field;
                validateDemandSummaryPeak(inp);
                const sliceRaw = inp.dataset.slice || inp.getAttribute("data-slice");
                const sliceYearNum = sliceRaw ? parseInt(String(sliceRaw), 10) : NaN;
                const inpTr = inp.closest("tr.summary-row-param");
                if (
                    inpTr &&
                    !Number.isNaN(sliceYearNum) &&
                    perimeterVariantYearOutOfRange(inpTr, sliceYearNum)
                ) {
                    throw new Error("Год вне периода действия варианта периметра.");
                }
                const pk =
                    inp.dataset.parameterKey || inp.getAttribute("data-parameter-key") || "";
                const siprOn =
                    typeof window.__pdEcSummarySiprMode !== "undefined" &&
                    window.__pdEcSummarySiprMode === true;
                const payload = {
                    demand_model_name: inp.dataset.model || inp.getAttribute("data-model"),
                    parameter_key: pk,
                    value: value,
                    rounding_digits: parseInt(table.dataset.roundingDigits || "1", 10),
                    slice_key: sliceRaw ? parseInt(String(sliceRaw), 10) : null,
                    sipr_summary_mode: siprOn
                };
                const logScope = table.getAttribute("data-summary-log-scope");
                if (logScope) {
                    payload.summary_log_scope = logScope;
                }
                const ridAttr = inp.getAttribute("data-row-id");
                if (ridAttr !== null && ridAttr !== "") {
                    const rid = parseInt(ridAttr, 10);
                    if (!Number.isNaN(rid)) {
                        payload.row_id = rid;
                    }
                }
                const pfk = inp.getAttribute("data-parent-fk");
                if (pfk) {
                    payload.parent_fk_column = pfk;
                }
                const pidi = inp.getAttribute("data-parent-id");
                if (pidi !== null && pidi !== "") {
                    payload.parent_id = parseInt(pidi, 10);
                }
                if (payload.demand_model_name) {
                    payload.perimeter_variant_code = perimeterVariantPayloadValue(inp);
                }
                const gsid = inp.getAttribute("data-gaes-station-id");
                if (gsid !== null && gsid !== "") {
                    const gid = parseInt(gsid, 10);
                    if (!Number.isNaN(gid)) {
                        payload.gaes_station_id = gid;
                    }
                }
                if (!payload.demand_model_name || !payload.parameter_key) {
                    throw new Error("Не указаны модель или параметр.");
                }

                await post(saveUrl, payload);
            }
            field.dataset.initial = value;
        });

        saveBtn.addEventListener("click", async function () {
            table.querySelectorAll(selector).forEach(function (field) {
                if (field.value !== (field.dataset.initial || "")) live.enqueue(field);
            });
            saveBtn.disabled = true;
            try {
                await live.whenIdle();
                const unsaved = Array.from(table.querySelectorAll(selector)).some(function (field) {
                    return !field.disabled && !field.readOnly && field.value !== (field.dataset.initial || "");
                });
                if (!unsaved && table.dataset.persistComputedUrl) {
                    await post(table.dataset.persistComputedUrl, {
                        rounding_digits: parseInt(table.dataset.roundingDigits || "1", 10)
                    });
                    window.armGsPageScrollRestore.reload({ table: table, changedInputs: [] });
                }
            } catch (error) {
                window.alert(error.message);
            } finally {
                saveBtn.disabled = false;
            }
        });
    });
})();
