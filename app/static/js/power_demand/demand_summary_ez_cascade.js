/**
 * Каскадные фильтры сводки по энергозонам: энергозона ↔ РЭС,
 * логика как при построении дерева сводки (РЭС попадает в зону, если есть субъект зоны в составе РЭС).
 *
 * Таблица (сервер по ds_ez / ds_res): только зоны — все РЭС в них; зоны + РЭС — в зоне, откуда
 * отмечены РЭС, только они; в остальных выбранных зонах — все РЭС зоны; только ds_res — плоский
 * список по РЭС без строки энергозоны.
 */
(function () {
    const dataEl = document.getElementById("pd-ez-filters-data");
    if (!dataEl || !dataEl.textContent) {
        return;
    }

    let filtersData = null;
    try {
        filtersData = JSON.parse(dataEl.textContent);
    } catch (e) {
        filtersData = null;
    }
    if (!filtersData || filtersData.skip_territory_filter_cascade === true) {
        return;
    }

    const allEz = filtersData.energy_zone_list || [];
    const allRes = filtersData.regional_energy_system_list || [];
    const ezToRes = filtersData.ez_to_res_mapping || {};
    const resToEz = filtersData.res_to_ez_mapping || {};

    let isUpdating = false;

    function getSelectValues(selector) {
        const el = document.querySelector(selector);
        if (!el) return [];
        return Array.from(el.selectedOptions || [])
            .map(function (o) {
                return Number(o.value);
            })
            .filter(function (v) {
                return Number.isFinite(v);
            });
    }

    function getAllowedIds(selectedIds, mapping) {
        if (!selectedIds || selectedIds.length === 0) return null;
        const allowed = new Set();
        selectedIds.forEach(function (id) {
            const ids = mapping[String(id)] || mapping[Number(id)] || [];
            if (Array.isArray(ids)) {
                ids.forEach(function (allowedId) {
                    allowed.add(Number(allowedId));
                });
            } else if (ids !== null && ids !== undefined) {
                allowed.add(Number(ids));
            }
        });
        return allowed;
    }

    function combineAllowedIds() {
        const sets = Array.prototype.slice.call(arguments).filter(function (s) {
            return s !== null && s !== undefined;
        });
        if (sets.length === 0) return null;
        if (sets.length === 1) return sets[0];
        let result = new Set(sets[0]);
        for (let i = 1; i < sets.length; i++) {
            result = new Set(
                Array.from(result).filter(function (x) {
                    return sets[i].has(x);
                })
            );
        }
        return result;
    }

    /** См. demand_summary_oes_cascade.js — не терять уже выбранные id при обратных связях. */
    function unionAllowedWithCurrentSelection(allowedIds, currentSelectedIds) {
        if (!currentSelectedIds || currentSelectedIds.length === 0) {
            return allowedIds;
        }
        if (allowedIds == null) {
            return null;
        }
        const s = new Set(allowedIds);
        currentSelectedIds.forEach(function (id) {
            const n = Number(id);
            if (Number.isFinite(n)) {
                s.add(n);
            }
        });
        return s;
    }

    /** Все РЭС тех же энергозон, что и у выбранных РЭС (кластер по зонам). */
    function expandResClusterForSelectedRes(currentRes, ezToResMap, resToEzMap) {
        if (!currentRes || currentRes.length === 0) return null;
        const ezSet = new Set();
        currentRes.forEach(function (resId) {
            const ezs = resToEzMap[String(resId)] || resToEzMap[Number(resId)] || [];
            if (Array.isArray(ezs)) {
                ezs.forEach(function (eid) {
                    if (eid !== null && eid !== undefined) {
                        ezSet.add(Number(eid));
                    }
                });
            }
        });
        if (ezSet.size === 0) return new Set();
        const out = new Set();
        ezSet.forEach(function (ezid) {
            const ress = ezToResMap[String(ezid)] || ezToResMap[Number(ezid)] || [];
            if (Array.isArray(ress)) {
                ress.forEach(function (x) {
                    out.add(Number(x));
                });
            }
        });
        return out;
    }

    function refreshPdDropdown(selector) {
        const el = document.querySelector(selector);
        if (el && typeof el._multiDropdownRender === "function") {
            el._multiDropdownRender();
        }
    }

    function setSelectValues(selector, values, silent) {
        const el = document.querySelector(selector);
        if (!el) return;
        const set = new Set((values || []).map(String));
        Array.from(el.options).forEach(function (opt) {
            opt.selected = set.has(String(opt.value));
        });
        if (typeof window.$ !== "undefined" && window.$(el).data("select2")) {
            const arr = Array.from(set).filter(function (v) {
                return v !== "";
            });
            window.$(el).val(arr);
            if (!silent) {
                window.$(el).trigger("change");
            }
        } else {
            refreshPdDropdown(selector);
        }
    }

    function updateSelectOptions(selector, allItems, allowedIds, prevSelected, skipTrigger) {
        const el = document.querySelector(selector);
        if (!el) return;

        const prevSelectedSet = new Set((prevSelected || []).map(String));
        const newSelected = [];

        const frag = document.createDocumentFragment();
        const items = (allItems || []).slice();
        const naItems = [];
        const otherItems = [];
        items.forEach(function (item) {
            const name = String(item && item.name ? item.name : "")
                .trim()
                .toLowerCase();
            if (name === "не указано") {
                naItems.push(item);
            } else {
                otherItems.push(item);
            }
        });
        const sortedItems = naItems.concat(otherItems);

        sortedItems.forEach(function (item) {
            const itemId = Number(item.id);
            const isAllowed = allowedIds == null || allowedIds.has(itemId);
            const wasSelected = prevSelectedSet.has(String(itemId));
            if (!isAllowed) return;

            const opt = document.createElement("option");
            opt.value = String(itemId);
            opt.textContent = item.name;
            opt.selected = wasSelected;
            frag.appendChild(opt);
            if (wasSelected) newSelected.push(String(itemId));
        });

        el.innerHTML = "";
        el.appendChild(frag);
        setSelectValues(selector, newSelected, !!skipTrigger);

        if (!skipTrigger) {
            if (!(typeof window.$ !== "undefined" && window.$(el).data("select2"))) {
                el.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }
    }

    function updatePdEzCascadeFilters() {
        if (isUpdating) return;
        isUpdating = true;
        const form = document.querySelector("#filtersCollapse form.pd-summary-filters-form");
        try {
            const currentEz = getSelectValues("#ds_ez");
            const currentRes = getSelectValues("#ds_res_ez");

            const resFromEz = getAllowedIds(currentEz, ezToRes);
            const resCluster = expandResClusterForSelectedRes(currentRes, ezToRes, resToEz);
            /** При выбранных зонах список РЭС = все РЭС этих зон; сужение таблицы — отметкой РЭС и отправкой формы. */
            let resAllowed =
                currentEz && currentEz.length > 0
                    ? resFromEz
                    : combineAllowedIds(resFromEz, resCluster);
            resAllowed = unionAllowedWithCurrentSelection(resAllowed, currentRes);

            const ezFromRes = getAllowedIds(currentRes, resToEz);
            let ezAllowed = combineAllowedIds(ezFromRes);
            ezAllowed = unionAllowedWithCurrentSelection(ezAllowed, currentEz);

            if (form) {
                form.setAttribute("data-pd-cascade-silent", "1");
            }
            updateSelectOptions("#ds_ez", allEz, ezAllowed, currentEz, true);
            updateSelectOptions("#ds_res_ez", allRes, resAllowed, currentRes, true);
            if (form) {
                form.removeAttribute("data-pd-cascade-silent");
            }

            refreshPdDropdown("#ds_ez");
            refreshPdDropdown("#ds_res_ez");
        } finally {
            isUpdating = false;
        }
    }

    window.updatePdEzCascadeFilters = updatePdEzCascadeFilters;

    document.getElementById("ds_ez")?.addEventListener("change", function () {
        updatePdEzCascadeFilters();
    });
    document.getElementById("ds_res_ez")?.addEventListener("change", function () {
        updatePdEzCascadeFilters();
    });

    setTimeout(function () {
        updatePdEzCascadeFilters();
    }, 400);
})();
