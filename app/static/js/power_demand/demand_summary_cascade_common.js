/**
 * Shared helpers for power demand summary cascade filters.
 */
(function () {
    "use strict";

    function mappingValue(mapping, id) {
        return mapping[String(id)] || mapping[Number(id)];
    }

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
     * null means the dimension is unrestricted. Empty Set means it is restricted
     * but no ids are available, so the option list must become empty.
     */
    function getAllowedIds(selectedIds, mapping) {
        if (!selectedIds || selectedIds.length === 0) return null;
        const allowed = new Set();
        selectedIds.forEach(function (id) {
            const ids = mappingValue(mapping, id) || [];
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
            const mappedId = mappingValue(mapping, id);
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

    function expandClusterForSelectedChildren(currentChildren, parentToChildrenMap, childToParentsMap) {
        if (!currentChildren || currentChildren.length === 0) return null;
        const parentSet = new Set();
        currentChildren.forEach(function (childId) {
            const parents = mappingValue(childToParentsMap, childId) || [];
            if (Array.isArray(parents)) {
                parents.forEach(function (parentId) {
                    if (parentId !== null && parentId !== undefined) {
                        parentSet.add(Number(parentId));
                    }
                });
            }
        });
        if (parentSet.size === 0) return new Set();

        const out = new Set();
        parentSet.forEach(function (parentId) {
            const children = mappingValue(parentToChildrenMap, parentId) || [];
            if (Array.isArray(children)) {
                children.forEach(function (x) {
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
        const naItems = [];
        const otherItems = [];

        (allItems || []).forEach(function (item) {
            const name = String(item && item.name ? item.name : "")
                .trim()
                .toLowerCase();
            if (name === "не указано") {
                naItems.push(item);
            } else {
                otherItems.push(item);
            }
        });

        const frag = document.createDocumentFragment();
        naItems.concat(otherItems).forEach(function (item) {
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

        el.replaceChildren(frag);
        setSelectValues(selector, newSelected, !!skipTrigger);

        if (!skipTrigger && !(typeof window.$ !== "undefined" && window.$(el).data("select2"))) {
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    window.PowerDemandSummaryCascade = {
        getSelectValues,
        getAllowedIds,
        getAllowedIdsFromOneToOne,
        combineAllowedIds,
        unionAllowedWithCurrentSelection,
        expandClusterForSelectedChildren,
        refreshPdDropdown,
        updateSelectOptions,
    };
})();
