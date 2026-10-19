/**
 * Выбор слагаемых столбца «Нормируемые ЗВ» в шапке таблицы ГИС ТЭК.
 * Выпадающий список без Select2 (как фильтр по numb1120): кнопка, чекбоксы, «По умолчанию» / «Ок».
 * Применение — переход по ссылке с параметром norm_zv: суммы считает сервер.
 */
(function () {
    "use strict";

    var STYLE_ID = "norm-zv-header-filter-style";
    var PARAM = "norm_zv";

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }
        var st = document.createElement("style");
        st.id = STYLE_ID;
        st.textContent = [
            ".norm-zv-filter-wrap {",
            "  margin-top: 0.35rem;",
            "  font-weight: 400;",
            "  text-align: left;",
            "  width: 0;",
            "  min-width: 100%;",
            "  max-width: 100%;",
            "  box-sizing: border-box;",
            "}",
            ".norm-zv-filter-btn {",
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
            ".norm-zv-filter-menu {",
            "  position: fixed;",
            "  z-index: 2000;",
            "  display: flex;",
            "  flex-direction: column;",
            "  min-width: 16rem;",
            "  max-width: 26rem;",
            "  padding: 0.5rem;",
            "  overflow-y: auto;",
            "  background: #fff;",
            "  border: 1px solid var(--bs-border-color, #dee2e6);",
            "  border-radius: 0.375rem;",
            "  box-shadow: 0 0.5rem 1rem rgba(0,0,0,.15);",
            "}",
            ".norm-zv-filter-hint {",
            "  position: sticky;",
            "  top: 0;",
            "  z-index: 1;",
            "  background: #fff;",
            "  font-size: 0.78rem;",
            "  line-height: 1.25;",
            "}",
            ".norm-zv-filter-list {",
            "  overflow-x: hidden;",
            "}",
            ".norm-zv-filter-item {",
            "  white-space: nowrap;",
            "  cursor: pointer;",
            "  user-select: none;",
            "}",
            ".norm-zv-filter-footer {",
            "  position: sticky;",
            "  bottom: 0;",
            "  background: #fff;",
            "  flex-shrink: 0;",
            "  padding-top: 0.25rem;",
            "}",
        ].join("\n");
        document.head.appendChild(st);
    }

    function parseList(raw) {
        return String(raw || "")
            .split(",")
            .map(function (part) {
                return part.trim();
            })
            .filter(Boolean);
    }

    function urlValues() {
        var out = [];
        new URLSearchParams(window.location.search)
            .getAll(PARAM)
            .forEach(function (raw) {
                parseList(raw).forEach(function (name) {
                    if (out.indexOf(name) === -1) {
                        out.push(name);
                    }
                });
            });
        return out.sort();
    }

    function hasUrlParam() {
        return new URLSearchParams(window.location.search).has(PARAM);
    }

    function defaultValues(selectEl) {
        return parseList(selectEl.getAttribute("data-default")).sort();
    }

    /** Набор, который сейчас показан в столбце: из ссылки, иначе — по умолчанию. */
    function appliedValues(selectEl) {
        return hasUrlParam() ? urlValues() : defaultValues(selectEl);
    }

    function checkedValues(selectEl) {
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

    function applyValues(values) {
        var url = new URL(window.location.href);
        url.searchParams.delete(PARAM);
        if (values.length) {
            values.forEach(function (value) {
                url.searchParams.append(PARAM, value);
            });
        } else {
            // Пустое значение — сознательно очищенный выбор: в столбце прочерки.
            url.searchParams.set(PARAM, "");
        }
        var overlay = document.getElementById("loading-overlay");
        if (overlay) {
            overlay.style.display = "flex";
        }
        window.location.assign(url.toString());
    }

    function initDropdown(selectEl) {
        if (!selectEl || selectEl.dataset.normZvInit === "1") {
            return;
        }
        selectEl.dataset.normZvInit = "1";
        selectEl.classList.add("d-none");

        var parent = selectEl.parentNode;
        if (!parent) {
            return;
        }

        var wrap = document.createElement("div");
        wrap.className = "norm-zv-filter-wrap w-100";

        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "form-select form-select-sm norm-zv-filter-btn w-100 text-start";
        btn.setAttribute("aria-expanded", "false");
        btn.setAttribute("aria-haspopup", "listbox");

        var menu = document.createElement("div");
        menu.className = "norm-zv-filter-menu d-none";
        menu.setAttribute("role", "listbox");

        var hint = document.createElement("div");
        hint.className = "norm-zv-filter-hint flex-shrink-0 pb-1";
        var hintTitle = document.createElement("div");
        hintTitle.className = "fw-semibold";
        hintTitle.textContent =
            "Слагаемые столбца «" +
            (selectEl.getAttribute("data-placeholder") || "Нормируемые ЗВ") +
            "»";
        var hintCount = document.createElement("div");
        hintCount.className = "text-muted";
        hint.appendChild(hintTitle);
        hint.appendChild(hintCount);

        var list = document.createElement("div");
        list.className = "norm-zv-filter-list d-flex flex-column gap-1";

        var divider = document.createElement("hr");
        divider.className = "dropdown-divider";

        var footer = document.createElement("div");
        footer.className = "norm-zv-filter-footer d-flex justify-content-between gap-2";
        var resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "btn btn-sm btn-outline-secondary";
        resetBtn.textContent = "По умолчанию";
        var okBtn = document.createElement("button");
        okBtn.type = "button";
        okBtn.className = "btn btn-sm btn-primary";
        okBtn.textContent = "Ок";
        footer.appendChild(resetBtn);
        footer.appendChild(okBtn);

        menu.appendChild(hint);
        menu.appendChild(list);
        menu.appendChild(divider);
        menu.appendChild(footer);

        parent.insertBefore(wrap, selectEl);
        wrap.appendChild(btn);
        wrap.appendChild(selectEl);
        document.body.appendChild(menu);

        function selectableOptions() {
            return Array.prototype.filter.call(selectEl.options, function (opt) {
                return String(opt.value || "").trim() !== "";
            });
        }

        function optionLabel(opt) {
            return String(opt.textContent || opt.value || "").trim();
        }

        function labelsFor(values) {
            return selectableOptions()
                .filter(function (opt) {
                    return values.indexOf(String(opt.value).trim()) !== -1;
                })
                .map(optionLabel);
        }

        /** Подпись кнопки в шапке — по уже применённому набору (его и считает сервер). */
        function updateButton() {
            var labels = labelsFor(appliedValues(selectEl));
            btn.textContent = "";
            var caption = document.createElement("span");
            caption.textContent = labels.length
                ? "Выбрано: " + labels.length + " из " + selectableOptions().length
                : "Слагаемые не выбраны";
            btn.appendChild(caption);
            var caret = document.createElement("i");
            caret.className = "bi bi-caret-down-fill ms-1";
            btn.appendChild(caret);
            btn.title = labels.length
                ? "Сумма выбранных показателей: " + labels.join(" + ")
                : "Сумма не считается: не выбран ни один показатель";
        }

        /** Подсказка и кнопка «Ок» — по отмеченным сейчас галочкам. */
        function updateHint() {
            var checked = checkedValues(selectEl);
            var total = selectableOptions().length;
            hintCount.textContent = checked.length
                ? "Отмечено " + checked.length + " из " + total + " — нажмите «Ок»"
                : "Ничего не отмечено — сумма не считается";
            var dirty = !sameValues(checked, appliedValues(selectEl));
            // Подпись всегда «Ок»; не применённые галочки выделяются цветом кнопки.
            okBtn.textContent = "Ок";
            okBtn.classList.toggle("btn-primary", !dirty);
            okBtn.classList.toggle("btn-success", dirty);
        }

        function renderList() {
            list.innerHTML = "";
            selectableOptions().forEach(function (opt) {
                var item = document.createElement("label");
                item.className = "dropdown-item norm-zv-filter-item d-flex align-items-center gap-2 py-1 px-1";
                item.title = optionLabel(opt);

                var cb = document.createElement("input");
                cb.type = "checkbox";
                cb.checked = !!opt.selected;
                cb.addEventListener("click", function (e) {
                    e.stopPropagation();
                });
                cb.addEventListener("change", function (e) {
                    e.stopPropagation();
                    opt.selected = cb.checked;
                    updateHint();
                });

                var text = document.createElement("span");
                text.textContent = optionLabel(opt);
                item.appendChild(cb);
                item.appendChild(text);
                list.appendChild(item);
            });
        }

        /** Галочки списка при загрузке страницы — по набору из ссылки (или по умолчанию). */
        function syncFromApplied() {
            var applied = appliedValues(selectEl);
            Array.prototype.forEach.call(selectEl.options, function (opt) {
                opt.selected = applied.indexOf(String(opt.value).trim()) !== -1;
            });
        }

        /** Меню целиком в пределах окна: футер с «Ок» приклеен к низу и всегда виден. */
        function placeMenu() {
            var gap = 4;
            var margin = 8;
            var viewportW = window.innerWidth;
            var viewportH = window.innerHeight;
            var rect = btn.getBoundingClientRect();

            // Ширина: измеряем «естественную» и не даём меню выйти за границы окна.
            menu.style.width = "";
            menu.style.maxWidth = "";
            menu.style.maxHeight = "";
            var maxWidth = Math.min(26 * 16, viewportW - margin * 2);
            var menuW = Math.max(200, Math.min(Math.max(menu.offsetWidth, 256), maxWidth));
            menu.style.minWidth = "0";
            menu.style.maxWidth = maxWidth + "px";
            menu.style.width = menuW + "px";
            menu.style.left =
                Math.max(margin, Math.min(rect.left, viewportW - margin - menuW)) + "px";

            // Высота: ставим туда, где больше места, и не выходим за окно.
            var spaceBelow = viewportH - rect.bottom - gap - margin;
            var spaceAbove = rect.top - gap - margin;
            var below = spaceBelow >= spaceAbove;
            var available = Math.max(120, below ? spaceBelow : spaceAbove);
            menu.style.maxHeight = available + "px";
            menu.style.overflowY = "auto";

            var menuH = menu.offsetHeight || available;
            var top = below ? rect.bottom + gap : rect.top - gap - menuH;
            top = Math.max(margin, Math.min(top, viewportH - margin - menuH));
            menu.style.top = top + "px";
        }

        function isOpen() {
            return !menu.classList.contains("d-none");
        }

        function openMenu() {
            if (isOpen()) {
                return;
            }
            renderList();
            updateHint();
            menu.classList.remove("d-none");
            btn.setAttribute("aria-expanded", "true");
            placeMenu();
        }

        function closeMenu() {
            if (!isOpen()) {
                return;
            }
            menu.classList.add("d-none");
            btn.setAttribute("aria-expanded", "false");
        }

        function confirmSelection() {
            var values = checkedValues(selectEl);
            if (sameValues(values, appliedValues(selectEl))) {
                closeMenu();
                return;
            }
            applyValues(values);
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
            var defaults = defaultValues(selectEl);
            Array.prototype.forEach.call(selectEl.options, function (opt) {
                opt.selected = defaults.indexOf(String(opt.value).trim()) !== -1;
            });
            renderList();
            updateHint();
        });

        okBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            confirmSelection();
        });

        menu.addEventListener("mousedown", function (e) {
            e.stopPropagation();
        });
        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });
        menu.addEventListener("keydown", function (e) {
            e.stopPropagation();
            if (e.key === "Escape") {
                e.preventDefault();
                closeMenu();
            } else if (e.key === "Enter") {
                e.preventDefault();
                confirmSelection();
            }
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

        syncFromApplied();
        renderList();
        updateButton();
        updateHint();
    }

    function init() {
        injectStyles();
        var el = document.getElementById("normZvHeaderFilter");
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
