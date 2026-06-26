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
    const cascade = window.PowerDemandSummaryCascade;
    if (!cascade) {
        return;
    }
    const {
        getSelectValues,
        getAllowedIds,
        getAllowedIdsFromOneToOne,
        combineAllowedIds,
        unionAllowedWithCurrentSelection,
        refreshPdDropdown,
        updateSelectOptions,
    } = cascade;

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
