/**
 * Каскадные фильтры сводки по ФО: ФО ↔ субъект РФ (как get_territorial_filter_reference_data / Excel).
 *
 * Поведение таблицы (сервер по ds_fd / ds_rd):
 * — только выбранные ФО в URL → строки по этим ФО и по всем субъектам внутри них;
 * — к выбранным ФО добавлены субъекты в выпадающем списке → в URL попадает ds_rd:
 *   под ФО, из которых отмечены субъекты, — только они; под остальными выбранными ФО —
 *   все субъекты этих округов;
 * — только субъекты без ds_fd → плоский список по субъектам (без строки ФО).
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
    const allRd = filtersData.regional_district_list || [];
    const fdToRd = filtersData.fd_to_rd_mapping || {};
    const rdToFd = filtersData.rd_to_fd_mapping_one || {};

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
     * Уже выбранные id оставляем в multiselect (как на сводке по ОЭС): обратная связь
     * «субъект → один ФО» не должна убирать второй выбранный ФО из списка.
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

    /** Все субъекты, входящие в ФО выбранных субъектов (для списка «Субъект» при выборе только субъектов). */
    function expandRdClusterForSelectedRd(currentRd, fdToRdMap, rdToFdMap) {
        if (!currentRd || currentRd.length === 0) return null;
        const fdSet = new Set();
        currentRd.forEach(function (rid) {
            const fd = rdToFdMap[String(rid)] ?? rdToFdMap[Number(rid)];
            if (fd !== null && fd !== undefined) {
                fdSet.add(Number(fd));
            }
        });
        if (fdSet.size === 0) return new Set();
        const out = new Set();
        fdSet.forEach(function (fid) {
            const rds = fdToRdMap[String(fid)] || fdToRdMap[Number(fid)] || [];
            if (Array.isArray(rds)) {
                rds.forEach(function (x) {
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
            const currentRd = getSelectValues("#ds_rd_fo");

            const rdFromFd = getAllowedIds(currentFd, fdToRd);
            const rdCluster = expandRdClusterForSelectedRd(currentRd, fdToRd, rdToFd);
            /** При выбранных ФО список субъектов = все субъекты этих ФО (для сужения таблицы пользователь отмечает субъектов и отправляет форму). */
            let rdAllowed =
                currentFd && currentFd.length > 0
                    ? rdFromFd
                    : combineAllowedIds(rdFromFd, rdCluster);
            rdAllowed = unionAllowedWithCurrentSelection(rdAllowed, currentRd);

            const fdFromRd = getAllowedIdsFromOneToOne(currentRd, rdToFd);
            let fdAllowed = combineAllowedIds(fdFromRd);
            fdAllowed = unionAllowedWithCurrentSelection(fdAllowed, currentFd);

            if (form) {
                form.setAttribute("data-pd-cascade-silent", "1");
            }
            updateSelectOptions("#ds_fd", allFd, fdAllowed, currentFd, true);
            updateSelectOptions("#ds_rd_fo", allRd, rdAllowed, currentRd, true);
            if (form) {
                form.removeAttribute("data-pd-cascade-silent");
            }

            refreshPdDropdown("#ds_fd");
            refreshPdDropdown("#ds_rd_fo");
        } finally {
            isUpdating = false;
        }
    }

    window.updatePdFoCascadeFilters = updatePdFoCascadeFilters;

    document.getElementById("ds_fd")?.addEventListener("change", function () {
        updatePdFoCascadeFilters();
    });
    document.getElementById("ds_rd_fo")?.addEventListener("change", function () {
        updatePdFoCascadeFilters();
    });

    setTimeout(function () {
        updatePdFoCascadeFilters();
    }, 400);
})();
