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

    /** Все РЭС тех же ФО, что и у выбранных РЭС (кластер по округам). */
    function expandResClusterForSelectedRes(currentRes, fdToResMap, resToFdMap) {
        if (!currentRes || currentRes.length === 0) return null;
        const fdSet = new Set();
        currentRes.forEach(function (resId) {
            const fds = resToFdMap[String(resId)] || resToFdMap[Number(resId)] || [];
            if (Array.isArray(fds)) {
                fds.forEach(function (fid) {
                    if (fid !== null && fid !== undefined) {
                        fdSet.add(Number(fid));
                    }
                });
            }
        });
        if (fdSet.size === 0) return new Set();
        const out = new Set();
        fdSet.forEach(function (fdid) {
            const ress = fdToResMap[String(fdid)] || fdToResMap[Number(fdid)] || [];
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

    function updatePdFoCascadeFilters() {
        if (isUpdating) return;
        isUpdating = true;
        const form = document.querySelector("#filtersCollapse form.pd-summary-filters-form");
        try {
            const currentFd = getSelectValues("#ds_fd");
            const currentRes = getSelectValues("#ds_res_fo");

            const resFromFd = getAllowedIds(currentFd, fdToRes);
            const resCluster = expandResClusterForSelectedRes(currentRes, fdToRes, resToFd);
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
