/**
 * Фильтр строк таблицы ТЭП по numb1120 в шапке столбца.
 * Выпадающий список без Select2 (как фильтры ОЭС): кнопка, поле поиска, прокрутка, несколько кодов.
 */
(function () {
    "use strict";

    var STYLE_ID = "numb1120-header-filter-style";
    var PARAM = "numb1120_filter";

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }
        var st = document.createElement("style");
        st.id = STYLE_ID;
        st.textContent = [
            "th.fuel-param-col-numb1120 {",
            "  width: 1%;",
            "  min-width: min-content;",
            "  white-space: normal;",
            "  word-break: normal;",
            "  overflow-wrap: normal;",
            "  overflow: visible;",
            "  vertical-align: middle !important;",
            "}",
            ".numb1120-filter-wrap {",
            "  margin-top: 0.35rem;",
            "  font-weight: 400;",
            "  text-align: left;",
            "  width: 0;",
            "  min-width: 100%;",
            "  max-width: 100%;",
            "  box-sizing: border-box;",
            "}",
            ".numb1120-filter-btn {",
            "  display: inline-flex;",
            "  align-items: center;",
            "  justify-content: space-between;",
            "  font-size: 0.85rem;",
            "  padding: 0.2rem 0.45rem;",
            "  min-height: 2rem;",
            "  min-width: 0;",
            "  max-width: 100%;",
            "  white-space: nowrap;",
            "  overflow: hidden;",
            "  text-overflow: ellipsis;",
            "}",
            ".numb1120-filter-menu {",
            "  position: fixed;",
            "  z-index: 2000;",
            "  display: flex;",
            "  flex-direction: column;",
            "  min-width: 14rem;",
            "  max-width: 22rem;",
            "  padding: 0.5rem;",
            "  background: #fff;",
            "  border: 1px solid var(--bs-border-color, #dee2e6);",
            "  border-radius: 0.375rem;",
            "  box-shadow: 0 0.5rem 1rem rgba(0,0,0,.15);",
            "}",
            ".numb1120-filter-list {",
            "  max-height: 16rem;",
            "  overflow-y: auto;",
            "  overflow-x: hidden;",
            "}",
            ".numb1120-filter-item {",
            "  white-space: nowrap;",
            "  cursor: pointer;",
            "}",
            ".numb1120-filter-menu hr {",
            "  margin: 0.4rem 0;",
            "}",
            ".numb1120-filter-footer {",
            "  flex-shrink: 0;",
            "  padding-top: 0.15rem;",
            "}",
            ".numb1120-filter-clear {",
            "  padding: 2px 6px;",
            "  line-height: 1;",
            "}",
        ].join("\n");
        document.head.appendChild(st);
    }

    function parseCodes(raw) {
        var out = [];
        var seen = {};
        String(raw || "")
            .replace(/[,;]+/g, " ")
            .split(/\s+/)
            .forEach(function (part) {
                var s = String(part || "").trim();
                if (!s || !/^\d+$/.test(s) || seen[s]) {
                    return;
                }
                seen[s] = true;
                out.push(s);
            });
        return out;
    }

    function selectedValues(selectEl) {
        return Array.prototype.map
            .call(selectEl.selectedOptions || [], function (opt) {
                return String(opt.value || "").trim();
            })
            .filter(Boolean)
            .sort();
    }

    function sameValues(a, b) {
        if (a.length !== b.length) {
            return false;
        }
        for (var i = 0; i < a.length; i++) {
            if (a[i] !== b[i]) {
                return false;
            }
        }
        return true;
    }

    function currentUrlValues() {
        var params = new URLSearchParams(window.location.search);
        var out = [];
        var seen = {};
        params.getAll(PARAM).forEach(function (v) {
            parseCodes(v).forEach(function (s) {
                if (seen[s]) {
                    return;
                }
                seen[s] = true;
                out.push(s);
            });
        });
        out.sort();
        return out;
    }

    var applying = false;

    function applyFilter(values) {
        if (applying || sameValues(values, currentUrlValues())) {
            return;
        }
        applying = true;
        var url = new URL(window.location.href);
        url.searchParams.delete(PARAM);
        url.searchParams.delete("page");
        values.forEach(function (v) {
            url.searchParams.append(PARAM, v);
        });
        var overlay = document.getElementById("loading-overlay");
        if (overlay) {
            overlay.style.display = "flex";
        }
        window.location.assign(url.toString());
    }

    function ensureOption(selectEl, value) {
        var found = Array.prototype.find.call(selectEl.options, function (o) {
            return String(o.value) === String(value);
        });
        if (found) {
            return found;
        }
        var opt = document.createElement("option");
        opt.value = value;
        opt.textContent = value;
        selectEl.appendChild(opt);
        return opt;
    }

    function initDropdown(selectEl) {
        if (!selectEl || selectEl.dataset.numb1120Init === "1") {
            return;
        }
        selectEl.dataset.numb1120Init = "1";
        selectEl.classList.add("d-none");

        var placeholder = selectEl.getAttribute("data-placeholder") || "Фильтр";
        var parent = selectEl.parentNode;
        if (!parent) {
            return;
        }

        var wrap = document.createElement("div");
        wrap.className = "numb1120-filter-wrap w-100";

        var row = document.createElement("div");
        row.className = "d-flex align-items-center justify-content-center gap-1";

        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "form-select form-select-sm numb1120-filter-btn w-100 text-start";
        btn.setAttribute("aria-expanded", "false");
        btn.setAttribute("aria-haspopup", "listbox");

        var headerClear = document.createElement("button");
        headerClear.type = "button";
        headerClear.className = "btn btn-sm btn-outline-danger filter-clear-btn numb1120-filter-clear d-none";
        headerClear.title = "Сбросить фильтр";
        headerClear.innerHTML = '<i class="bi bi-x-lg"></i>';

        var menu = document.createElement("div");
        menu.className = "numb1120-filter-menu d-none";
        menu.setAttribute("role", "listbox");

        var searchInput = document.createElement("input");
        searchInput.type = "text";
        searchInput.className = "form-control form-control-sm mb-2";
        searchInput.placeholder = "Введите код…";
        searchInput.setAttribute("autocomplete", "off");
        searchInput.setAttribute("aria-label", "Поиск по коду группы оборудования");

        var list = document.createElement("div");
        list.className = "numb1120-filter-list d-flex flex-column gap-1";

        var footer = document.createElement("div");
        footer.className = "numb1120-filter-footer d-flex justify-content-between gap-2";
        var resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "btn btn-sm btn-outline-secondary";
        resetBtn.textContent = "Сбросить";
        var okBtn = document.createElement("button");
        okBtn.type = "button";
        okBtn.className = "btn btn-sm btn-primary";
        okBtn.textContent = "Ок";
        footer.appendChild(resetBtn);
        footer.appendChild(okBtn);

        var divider = document.createElement("hr");
        divider.className = "dropdown-divider";
        menu.appendChild(searchInput);
        menu.appendChild(list);
        menu.appendChild(divider);
        menu.appendChild(footer);

        parent.insertBefore(wrap, selectEl);
        wrap.appendChild(row);
        row.appendChild(btn);
        row.appendChild(headerClear);
        wrap.appendChild(selectEl);
        document.body.appendChild(menu);

        function setButtonText() {
            var applied = currentUrlValues();
            btn.textContent = "";
            var label = document.createElement("span");
            if (!applied.length) {
                label.textContent = placeholder;
            } else {
                var suffix = applied.length > 1 ? " (+" + (applied.length - 1) + ")" : "";
                label.textContent = applied[0] + suffix;
            }
            btn.appendChild(label);
            if (applied.length) {
                var icon = document.createElement("i");
                icon.className = "bi bi-funnel-fill text-warning ms-1";
                btn.appendChild(icon);
            }
            headerClear.classList.toggle("d-none", !applied.length);
        }

        function restoreFromUrl() {
            var applied = {};
            currentUrlValues().forEach(function (v) {
                applied[v] = true;
                ensureOption(selectEl, v);
            });
            Array.prototype.forEach.call(selectEl.options, function (opt) {
                opt.selected = !!applied[String(opt.value)];
            });
        }

        function applySearchFilter() {
            var q = (searchInput.value || "").trim().toLowerCase();
            var codes = parseCodes(searchInput.value);
            var useCodes = codes.length > 1;
            list.querySelectorAll("[data-search-text]").forEach(function (el) {
                var text = el.getAttribute("data-search-text") || "";
                var match;
                if (useCodes) {
                    match = codes.indexOf(text) !== -1;
                } else {
                    match = !q || text.indexOf(q) !== -1;
                }
                el.classList.toggle("d-none", !match);
            });
        }

        function renderList() {
            list.innerHTML = "";
            Array.prototype.forEach.call(selectEl.options, function (opt) {
                var value = String(opt.value || "").trim();
                if (!value) {
                    return;
                }
                var item = document.createElement("label");
                item.className = "dropdown-item numb1120-filter-item d-flex align-items-center gap-2 py-1 px-1";
                item.setAttribute("data-search-text", value);

                var cb = document.createElement("input");
                cb.type = "checkbox";
                cb.checked = !!opt.selected;
                cb.addEventListener("click", function (e) {
                    e.stopPropagation();
                });
                cb.addEventListener("change", function (e) {
                    e.stopPropagation();
                    var found = ensureOption(selectEl, value);
                    found.selected = cb.checked;
                });

                var text = document.createElement("span");
                text.textContent = value;
                item.appendChild(cb);
                item.appendChild(text);
                list.appendChild(item);
            });
            applySearchFilter();
        }

        function placeMenu() {
            var rect = btn.getBoundingClientRect();
            var menuWidth = Math.max(rect.width, 224);
            var left = rect.left;
            if (left + menuWidth > window.innerWidth - 8) {
                left = Math.max(8, window.innerWidth - menuWidth - 8);
            }
            menu.style.minWidth = menuWidth + "px";
            menu.style.left = left + "px";

            var spaceBelow = window.innerHeight - rect.bottom - 8;
            var spaceAbove = rect.top - 8;
            var chrome = (searchInput.offsetHeight || 32) + (footer.offsetHeight || 40) + 24;
            var listMax = Math.max(72, Math.min(256, Math.max(spaceBelow, spaceAbove) - chrome));
            list.style.maxHeight = listMax + "px";

            var menuH = menu.offsetHeight || chrome + listMax;
            if (spaceBelow < menuH && spaceAbove > spaceBelow) {
                menu.style.top = Math.max(8, rect.top - menuH - 4) + "px";
            } else {
                menu.style.top = rect.bottom + 4 + "px";
            }
        }

        function isOpen() {
            return !menu.classList.contains("d-none");
        }

        function openMenu() {
            if (isOpen()) {
                return;
            }
            restoreFromUrl();
            searchInput.value = "";
            renderList();
            menu.classList.remove("d-none");
            btn.setAttribute("aria-expanded", "true");
            placeMenu();
            setTimeout(function () {
                searchInput.focus();
                searchInput.select();
            }, 0);
        }

        function closeMenu() {
            if (!isOpen()) {
                return;
            }
            menu.classList.add("d-none");
            btn.setAttribute("aria-expanded", "false");
            restoreFromUrl();
        }

        function confirmSelection() {
            var values = selectedValues(selectEl);
            if (sameValues(values, currentUrlValues())) {
                closeMenu();
                return;
            }
            applyFilter(values);
        }

        function selectCodesFromInput() {
            var codes = parseCodes(searchInput.value);
            if (!codes.length) {
                return false;
            }
            codes.forEach(function (code) {
                ensureOption(selectEl, code).selected = true;
            });
            searchInput.value = "";
            renderList();
            return true;
        }

        btn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (isOpen()) {
                closeMenu();
            } else {
                openMenu();
            }
        });

        resetBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            Array.prototype.forEach.call(selectEl.options, function (opt) {
                opt.selected = false;
            });
            searchInput.value = "";
            renderList();
        });

        okBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            confirmSelection();
        });

        headerClear.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            applyFilter([]);
        });

        searchInput.addEventListener("input", applySearchFilter);
        searchInput.addEventListener("keydown", function (e) {
            e.stopPropagation();
            if (e.key === "Escape") {
                e.preventDefault();
                closeMenu();
                return;
            }
            if (e.key === "Enter") {
                e.preventDefault();
                selectCodesFromInput();
                confirmSelection();
            }
        });
        searchInput.addEventListener("mousedown", function (e) {
            e.stopPropagation();
        });
        menu.addEventListener("mousedown", function (e) {
            e.stopPropagation();
        });
        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });

        document.addEventListener("mousedown", function (e) {
            if (!isOpen()) {
                return;
            }
            if (wrap.contains(e.target) || menu.contains(e.target)) {
                return;
            }
            closeMenu();
        });
        window.addEventListener(
            "scroll",
            function (e) {
                if (!isOpen()) {
                    return;
                }
                if (menu.contains(e.target)) {
                    return;
                }
                placeMenu();
            },
            true
        );
        window.addEventListener("resize", function () {
            if (isOpen()) {
                placeMenu();
            }
        });

        setButtonText();
    }

    function init() {
        injectStyles();
        var el = document.getElementById("numb1120HeaderFilter");
        if (!el) {
            return;
        }
        initDropdown(el);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
