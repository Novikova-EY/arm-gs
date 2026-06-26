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
    const cascade = window.PowerDemandSummaryCascade;
    if (!cascade) {
        return;
    }
    const {
        getSelectValues,
        getAllowedIds,
        combineAllowedIds,
        unionAllowedWithCurrentSelection,
        expandClusterForSelectedChildren,
        refreshPdDropdown,
        updateSelectOptions,
    } = cascade;

    function updatePdEzCascadeFilters() {
        if (isUpdating) return;
        isUpdating = true;
        const form = document.querySelector("#filtersCollapse form.pd-summary-filters-form");
        try {
            const currentEz = getSelectValues("#ds_ez");
            const currentRes = getSelectValues("#ds_res_ez");

            const resFromEz = getAllowedIds(currentEz, ezToRes);
            const resCluster = expandClusterForSelectedChildren(currentRes, ezToRes, resToEz);
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
