/**
 * Каскадные фильтры сводки по ФО: ФО ↔ РЭС,
 * логика как при построении дерева сводки (РЭС входит в ФО, если есть субъект округа в составе РЭС).
 *
 * Поведение таблицы (сервер по ds_fd / ds_res):
 * — только выбранные ФО в URL → строки по этим ФО и по всем РЭС внутри них;
 * — к выбранным ФО добавлены РЭС в выпадающем списке → в URL попадает ds_res:
 *   под ФО, из которых отмечены РЭС, — только они; под остальными выбранными ФО —
 *   все РЭС этих округов;
 * — только РЭС без ds_fd → плоский список по РЭС (без строки ФО).
 */
(function () {
    const dataEl = document.getElementById("pd-fo-filters-data");
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

    const allFd = filtersData.federal_district_list || [];
    const allRes = filtersData.regional_energy_system_list || [];
    const fdToRes = filtersData.fd_to_res_mapping || {};
    const resToFd = filtersData.res_to_fd_mapping || {};

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

    function updatePdFoCascadeFilters() {
        if (isUpdating) return;
        isUpdating = true;
        const form = document.querySelector("#filtersCollapse form.pd-summary-filters-form");
        try {
            const currentFd = getSelectValues("#ds_fd");
            const currentRes = getSelectValues("#ds_res_fo");

            const resFromFd = getAllowedIds(currentFd, fdToRes);
            const resCluster = expandClusterForSelectedChildren(currentRes, fdToRes, resToFd);
            let resAllowed =
                currentFd && currentFd.length > 0
                    ? resFromFd
                    : combineAllowedIds(resFromFd, resCluster);
            resAllowed = unionAllowedWithCurrentSelection(resAllowed, currentRes);

            const fdFromRes = getAllowedIds(currentRes, resToFd);
            let fdAllowed = combineAllowedIds(fdFromRes);
            fdAllowed = unionAllowedWithCurrentSelection(fdAllowed, currentFd);

            if (form) {
                form.setAttribute("data-pd-cascade-silent", "1");
            }
            updateSelectOptions("#ds_fd", allFd, fdAllowed, currentFd, true);
            updateSelectOptions("#ds_res_fo", allRes, resAllowed, currentRes, true);
            if (form) {
                form.removeAttribute("data-pd-cascade-silent");
            }

            refreshPdDropdown("#ds_fd");
            refreshPdDropdown("#ds_res_fo");
        } finally {
            isUpdating = false;
        }
    }

    window.updatePdFoCascadeFilters = updatePdFoCascadeFilters;

    document.getElementById("ds_fd")?.addEventListener("change", function () {
        updatePdFoCascadeFilters();
    });
    document.getElementById("ds_res_fo")?.addEventListener("change", function () {
        updatePdFoCascadeFilters();
    });

    setTimeout(function () {
        updatePdFoCascadeFilters();
    }, 400);
})();
