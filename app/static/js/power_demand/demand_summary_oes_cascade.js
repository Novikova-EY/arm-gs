/**
 * Каскадные фильтры сводки нагрузок по ОЭС (ОЭС → РЭС → субъект → энергорайон),
 * логика как на generation/stations/station_list (station_filters_first_row.js).
 *
 * Сервер объединяет выборы по уровням с «ослаблением» внутри каждой ветки родителя (как на
 * сводках по ФО и энергозонам): например, субъекты из одной ОЭС не отрезают РЭС/субъектов/ЭУ
 * под другой выбранной ОЭС; то же для РЭС ↔ субъектов и субъектов ↔ энергорайонов.
 */
(function () {
    const dataEl = document.getElementById("pd-oes-filters-data");
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

    const allUes = filtersData.union_energy_system_list || [];
    const allRes = filtersData.regional_energy_system_list || [];
    const allRd = filtersData.regional_district_list || [];
    const allEu = filtersData.energy_unit_list || [];

    const uesToRes = filtersData.ues_to_res_mapping || {};
    const uesToRd = filtersData.ues_to_rd_mapping || {};
    const resToRd = filtersData.res_to_rd_mapping || {};
    const resToUesOne = filtersData.res_to_ues_mapping_one || {};
    const rdToRes = filtersData.rd_to_res_mapping || {};
    const rdToUes = filtersData.rd_to_ues_mapping || {};
    const uesToEu = filtersData.ues_to_eu_ids || {};
    const resToEu = filtersData.res_to_eu_ids || {};
    const rdToEu = filtersData.rd_to_eu_ids || {};
    const euToRes = filtersData.eu_to_res_id || {};
    const euToRd = filtersData.eu_to_rd_id || {};
    const euToUes = filtersData.eu_to_ues_id || {};

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

    /**
     * null = ограничение по этому измерению не задано (ничего не выбрано в multiselect).
     * Пустой Set = выбрано, но по справочнику нет ни одного id — список опций должен стать пустым,
     * а не «все» (иначе энергорайоны и др. выглядят «не привязанными», как до правки).
     */
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

    function getAllowedIdsFromOneToOne(selectedIds, mapping) {
        if (!selectedIds || selectedIds.length === 0) return null;
        const allowed = new Set();
        selectedIds.forEach(function (id) {
            const mappedId = mapping[String(id)] || mapping[Number(id)];
            if (mappedId !== null && mappedId !== undefined) {
                allowed.add(Number(mappedId));
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

    /**
     * На сводке по ОЭС выборы с разных уровней объединяются на сервере (OR), а не пересекаются.
     * Иначе обратная связь (например РЭС → одна ОЭС) сужает список ОЭС до одной строки, выпадает
     * вторая выбранная ОЭС и все её РЭС из соседнего multiselect.
     */
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

    function updatePdOesCascadeFilters() {
        if (isUpdating) return;
        isUpdating = true;
        const form = document.querySelector("#filtersCollapse form.pd-summary-filters-form");
        try {
            const currentUes = getSelectValues("#ds_ues");
            const currentRes = getSelectValues("#ds_res");
            const currentRd = getSelectValues("#ds_rd_oes");
            const currentEu = getSelectValues("#ds_eu");

            const uesAllowedFromRes = getAllowedIdsFromOneToOne(currentRes, resToUesOne);
            const uesAllowedFromRd = getAllowedIds(currentRd, rdToUes);
            const uesAllowedFromEu = getAllowedIdsFromOneToOne(currentEu, euToUes);
            let uesAllowed = combineAllowedIds(uesAllowedFromRes, uesAllowedFromRd, uesAllowedFromEu);
            uesAllowed = unionAllowedWithCurrentSelection(uesAllowed, currentUes);

            const resAllowedFromUes = getAllowedIds(currentUes, uesToRes);
            const resAllowedFromRd = getAllowedIds(currentRd, rdToRes);
            const resAllowedFromEu = getAllowedIdsFromOneToOne(currentEu, euToRes);
            let resAllowed = combineAllowedIds(resAllowedFromUes, resAllowedFromRd, resAllowedFromEu);
            resAllowed = unionAllowedWithCurrentSelection(resAllowed, currentRes);

            const rdAllowedFromUes = getAllowedIds(currentUes, uesToRd);
            const rdAllowedFromRes = getAllowedIds(currentRes, resToRd);
            const rdAllowedFromEu = getAllowedIdsFromOneToOne(currentEu, euToRd);
            let rdAllowed = combineAllowedIds(rdAllowedFromUes, rdAllowedFromRes, rdAllowedFromEu);
            rdAllowed = unionAllowedWithCurrentSelection(rdAllowed, currentRd);

            const euAllowedFromUes = getAllowedIds(currentUes, uesToEu);
            const euAllowedFromRes = getAllowedIds(currentRes, resToEu);
            const euAllowedFromRd = getAllowedIds(currentRd, rdToEu);
            let euAllowed = combineAllowedIds(euAllowedFromUes, euAllowedFromRes, euAllowedFromRd);
            euAllowed = unionAllowedWithCurrentSelection(euAllowed, currentEu);

            if (form) {
                form.setAttribute("data-pd-cascade-silent", "1");
            }
            updateSelectOptions("#ds_ues", allUes, uesAllowed, currentUes, true);
            updateSelectOptions("#ds_res", allRes, resAllowed, currentRes, true);
            updateSelectOptions("#ds_rd_oes", allRd, rdAllowed, currentRd, true);
            updateSelectOptions("#ds_eu", allEu, euAllowed, currentEu, true);
            if (form) {
                form.removeAttribute("data-pd-cascade-silent");
            }

            refreshPdDropdown("#ds_ues");
            refreshPdDropdown("#ds_res");
            refreshPdDropdown("#ds_rd_oes");
            refreshPdDropdown("#ds_eu");
        } finally {
            isUpdating = false;
        }
    }

    window.updatePdOesCascadeFilters = updatePdOesCascadeFilters;

    document.getElementById("ds_ues")?.addEventListener("change", function () {
        updatePdOesCascadeFilters();
    });
    document.getElementById("ds_res")?.addEventListener("change", function () {
        updatePdOesCascadeFilters();
    });
    document.getElementById("ds_rd_oes")?.addEventListener("change", function () {
        updatePdOesCascadeFilters();
    });
    document.getElementById("ds_eu")?.addEventListener("change", function () {
        updatePdOesCascadeFilters();
    });

    setTimeout(function () {
        updatePdOesCascadeFilters();
    }, 400);
})();
