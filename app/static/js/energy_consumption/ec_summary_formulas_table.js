/**
 * Таблица текстов формул: интерфейс как у сводки power_demand (загрузчик, прокрутка)
 * и фильтры в шапке столбцов (выпадающие списки с галочками).
 */
(function () {
    "use strict";

    const collator = new Intl.Collator("ru", { sensitivity: "base", numeric: true });
    const loaderStartedAt = Date.now();
    const LOADER_MIN_MS = 400;

    function normalizePageFilterLine(value) {
        // Старые закладки/разметка могли содержать «;» в конце подписи страницы.
        return String(value || "").trim().replace(/;+\s*$/, "");
    }

    function rowPageLines(row) {
        const raw = row.getAttribute("data-filter-page-lines") || "";
        if (!raw) {
            return [];
        }
        return raw.split("||").map(normalizePageFilterLine).filter(Boolean);
    }

    function rowFilterValue(row, col) {
        if (col === "formula_text") {
            const ta = row.querySelector(".ec-formula-text-input");
            return (ta && ta.value ? ta.value : "").trim().toLowerCase();
        }
        if (col === "page") {
            return rowPageLines(row).join("\n");
        }
        const attr = "data-filter-" + col.replace(/_/g, "-");
        return (row.getAttribute(attr) || "").trim();
    }

    function finishInitialRender() {
        const shell = document.getElementById("ecFormulaSummaryLoaderShell");
        const overlay = document.getElementById("ecFormulaSummaryLoadingOverlay");
        const scrollWrap = document.getElementById("ecFormulaSummaryScrollWrap");
        if (!shell || shell.dataset.ready === "1") {
            return;
        }
        shell.dataset.ready = "1";
        const waitMs = Math.max(0, LOADER_MIN_MS - (Date.now() - loaderStartedAt));

        function reveal() {
            window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () {
                    if (scrollWrap) {
                        scrollWrap.style.visibility = "";
                    }
                    if (overlay) {
                        overlay.style.display = "none";
                    }
                    shell.setAttribute("aria-busy", "false");
                });
            });
        }

        if (waitMs > 0) {
            setTimeout(reveal, waitMs);
        } else {
            reveal();
        }
    }

    function getActiveCheckboxFilters(col) {
        const menu = document.querySelector(
            '.ec-formula-filter-menu[data-ec-filter-col="' + col + '"]'
        );
        if (!menu) {
            return [];
        }
        return Array.from(
            menu.querySelectorAll('input.ec-formula-filter-cb[data-ec-filter-col="' + col + '"]:checked')
        ).map(function (cb) {
            return cb.value;
        });
    }

    function syncFilterButtonUi(col, active) {
        const btn = document.querySelector(
            'button.filter-button[data-ec-filter-col="' + col + '"]'
        );
        const clearBtn = document.querySelector(
            '.ec-formula-filter-clear[data-ec-filter-col="' + col + '"]'
        );
        if (btn) {
            let icon = btn.querySelector(".ec-formula-filter-active-icon");
            if (active && !icon) {
                icon = document.createElement("i");
                icon.className = "bi bi-funnel-fill text-warning ms-1 ec-formula-filter-active-icon";
                icon.setAttribute("aria-hidden", "true");
                btn.appendChild(icon);
            } else if (!active && icon) {
                icon.remove();
            }
        }
        if (clearBtn) {
            clearBtn.classList.toggle("d-none", !active);
        }
    }

    function syncFiltersToggleBtn() {
        const toggleBtn = document.getElementById("ecFormulaFiltersToggleBtn");
        if (!toggleBtn) {
            return;
        }
        const textFilter = document.querySelector('.ec-col-filter[data-col="formula_text"]');
        const anyCol = ["page", "aggregation", "cell"].some(function (col) {
            return getActiveCheckboxFilters(col).length > 0;
        });
        const anyText = textFilter && String(textFilter.value || "").trim() !== "";
        const active = anyCol || anyText;
        toggleBtn.classList.toggle("btn-warning", active);
        toggleBtn.classList.toggle("text-dark", active);
        toggleBtn.classList.toggle("btn-primary", !active);
        toggleBtn.classList.toggle("text-white", !active);
        if (active) {
            toggleBtn.innerHTML = '<i class="bi bi-funnel-fill"></i> Фильтры / Поиск';
        } else {
            toggleBtn.innerHTML = "🔍 Фильтры / Поиск";
        }
    }

    function syncFiltersToUrl(pageNeed, aggNeed, cellNeed, textNeed) {
        const params = new URLSearchParams();
        pageNeed.forEach(function (v) {
            params.append("page", v);
        });
        aggNeed.forEach(function (v) {
            params.append("aggregation", v);
        });
        cellNeed.forEach(function (v) {
            params.append("cell", v);
        });
        if (textNeed) {
            params.set("q", textNeed);
        }
        const qs = params.toString();
        const url = window.location.pathname + (qs ? "?" + qs : "") + window.location.hash;
        window.history.replaceState(null, "", url);
    }

    function restoreFiltersFromUrl(table) {
        const params = new URLSearchParams(window.location.search);
        const pages = params.getAll("page");
        const aggs = params.getAll("aggregation");
        const cells = params.getAll("cell");
        const text = params.get("q") || "";

        [
            { col: "page", values: pages.map(normalizePageFilterLine).filter(Boolean) },
            { col: "aggregation", values: aggs },
            { col: "cell", values: cells },
        ].forEach(function (item) {
            if (!item.values.length) {
                return;
            }
            table
                .querySelectorAll(
                    'input.ec-formula-filter-cb[data-ec-filter-col="' + item.col + '"]'
                )
                .forEach(function (cb) {
                    cb.checked = item.values.indexOf(cb.value) >= 0;
                });
        });

        const textInput = table.querySelector('.ec-col-filter[data-col="formula_text"]');
        if (textInput && text) {
            textInput.value = text;
        }
    }

    function applyFilters(table, dataRows) {
        const textNeed = (function () {
            const inp = table.querySelector('.ec-col-filter[data-col="formula_text"]');
            return inp ? String(inp.value || "").trim().toLowerCase() : "";
        })();
        const pageNeed = getActiveCheckboxFilters("page");
        const aggNeed = getActiveCheckboxFilters("aggregation");
        const cellNeed = getActiveCheckboxFilters("cell");

        syncFilterButtonUi("page", pageNeed.length > 0);
        syncFilterButtonUi("aggregation", aggNeed.length > 0);
        syncFilterButtonUi("cell", cellNeed.length > 0);
        syncFiltersToggleBtn();

        let visible = 0;
        dataRows.forEach(function (row) {
            let show = true;
            if (pageNeed.length) {
                const rowPages = rowPageLines(row);
                if (!rowPages.some(function (line) {
                    return pageNeed.indexOf(line) >= 0;
                })) {
                    show = false;
                }
            }
            if (aggNeed.length && aggNeed.indexOf(rowFilterValue(row, "aggregation")) < 0) {
                show = false;
            }
            if (cellNeed.length && cellNeed.indexOf(rowFilterValue(row, "cell")) < 0) {
                show = false;
            }
            if (textNeed && !rowFilterValue(row, "formula_text").includes(textNeed)) {
                show = false;
            }
            row.classList.toggle("d-none", !show);
            if (show) {
                visible += 1;
            }
        });

        const counter = document.querySelector(".ec-formula-visible-count");
        if (counter) {
            counter.textContent = String(visible);
        }

        syncFiltersToUrl(pageNeed, aggNeed, cellNeed, textNeed);
    }

    function buildFilterMenu(table, col, values) {
        const menu = table.querySelector(
            '.ec-formula-filter-menu[data-ec-filter-col="' + col + '"]'
        );
        if (!menu) {
            return;
        }
        menu.innerHTML = "";
        values.sort(function (a, b) {
            return collator.compare(a, b);
        }).forEach(function (val) {
            const li = document.createElement("li");
            const label = document.createElement("label");
            label.className = "dropdown-item d-flex align-items-center gap-2";
            label.style.whiteSpace = "normal";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "ec-formula-filter-cb";
            cb.setAttribute("data-ec-filter-col", col);
            cb.value = val;
            const span = document.createElement("span");
            span.textContent = val;
            label.appendChild(cb);
            label.appendChild(span);
            li.appendChild(label);
            menu.appendChild(li);
        });
        const divider = document.createElement("li");
        divider.innerHTML = '<hr class="dropdown-divider">';
        menu.appendChild(divider);
        const actions = document.createElement("li");
        actions.className = "px-3 pb-2 d-flex justify-content-between gap-2";
        const resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "btn btn-sm btn-outline-secondary ec-formula-filter-reset-col";
        resetBtn.setAttribute("data-ec-filter-col", col);
        resetBtn.textContent = "Сбросить";
        const applyBtn = document.createElement("button");
        applyBtn.type = "button";
        applyBtn.className = "btn btn-sm btn-primary ec-formula-filter-apply-col";
        applyBtn.setAttribute("data-ec-filter-col", col);
        applyBtn.textContent = "Ок";
        actions.appendChild(resetBtn);
        actions.appendChild(applyBtn);
        menu.appendChild(actions);
    }

    function initTheadFilters(table) {
        const dataRows = Array.from(table.querySelectorAll("tbody tr[data-formula-key]"));
        if (!dataRows.length) {
            return;
        }

        const columns = ["page", "aggregation", "cell"];
        const columnValues = { page: new Set(), aggregation: new Set(), cell: new Set() };

        dataRows.forEach(function (row) {
            rowPageLines(row).forEach(function (line) {
                columnValues.page.add(line);
            });
            ["aggregation", "cell"].forEach(function (col) {
                const val = rowFilterValue(row, col);
                if (val) {
                    columnValues[col].add(val);
                }
            });
        });

        columns.forEach(function (col) {
            buildFilterMenu(table, col, Array.from(columnValues[col]));
        });

        restoreFiltersFromUrl(table);

        table.addEventListener("click", function (ev) {
            const applyCol = ev.target.closest(".ec-formula-filter-apply-col");
            if (applyCol) {
                applyFilters(table, dataRows);
                return;
            }
            const resetCol = ev.target.closest(".ec-formula-filter-reset-col");
            if (resetCol) {
                const col = resetCol.getAttribute("data-ec-filter-col");
                table
                    .querySelectorAll(
                        'input.ec-formula-filter-cb[data-ec-filter-col="' + col + '"]'
                    )
                    .forEach(function (cb) {
                        cb.checked = false;
                    });
                applyFilters(table, dataRows);
                return;
            }
            const clearCol = ev.target.closest(".ec-formula-filter-clear");
            if (clearCol) {
                const col = clearCol.getAttribute("data-ec-filter-col");
                table
                    .querySelectorAll(
                        'input.ec-formula-filter-cb[data-ec-filter-col="' + col + '"]'
                    )
                    .forEach(function (cb) {
                        cb.checked = false;
                    });
                applyFilters(table, dataRows);
            }
        });

        const textInput = table.querySelector('.ec-col-filter[data-col="formula_text"]');
        if (textInput) {
            textInput.addEventListener("input", function () {
                applyFilters(table, dataRows);
            });
        }

        const clearAll = document.getElementById("ec-formula-clear-filters");
        if (clearAll) {
            clearAll.addEventListener("click", function () {
                columns.forEach(function (col) {
                    table
                        .querySelectorAll(
                            'input.ec-formula-filter-cb[data-ec-filter-col="' + col + '"]'
                        )
                        .forEach(function (cb) {
                            cb.checked = false;
                        });
                });
                if (textInput) {
                    textInput.value = "";
                }
                applyFilters(table, dataRows);
            });
        }

        applyFilters(table, dataRows);
    }

    function initSaveHandlers(table) {
        const saveUrl = table.getAttribute("data-save-url");
        const resetUrl = table.getAttribute("data-reset-url");
        const csrfToken = table.getAttribute("data-csrf-token");
        const flashEl = document.getElementById("ec-formula-flash");
        if (!saveUrl || !resetUrl || !csrfToken || !flashEl) {
            return;
        }

        function showFlash(message, ok) {
            flashEl.textContent = message;
            flashEl.className = "alert alert-" + (ok ? "success" : "danger") + " mx-2";
            flashEl.classList.remove("d-none");
        }

        async function postJson(url, body) {
            const resp = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(body),
            });
            return resp.json();
        }

        table.addEventListener("click", async function (ev) {
            const tr = ev.target.closest("tr[data-formula-key]");
            if (!tr) {
                return;
            }
            const key = tr.getAttribute("data-formula-key");
            const textarea = tr.querySelector(".ec-formula-text-input");
            if (ev.target.classList.contains("ec-formula-save-btn")) {
                const data = await postJson(saveUrl, {
                    formula_key: key,
                    formula_text: textarea.value,
                });
                if (data.ok) {
                    showFlash("Сохранено.", true);
                    window.armGsPageScrollRestore.reload({
                        table: table,
                        anchorElement: textarea
                    });
                } else {
                    showFlash(data.error || "Ошибка сохранения.", false);
                }
            }
            if (ev.target.classList.contains("ec-formula-reset-btn")) {
                if (!confirm("Вернуть текст формулы по умолчанию?")) {
                    return;
                }
                const data = await postJson(resetUrl, { formula_key: key });
                if (data.ok) {
                    showFlash("Сброшено.", true);
                    window.armGsPageScrollRestore.reload({
                        table: table,
                        anchorElement: textarea
                    });
                } else {
                    showFlash(data.error || "Ошибка.", false);
                }
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const table =
            document.getElementById("ecFormulaSummaryTable") ||
            document.getElementById("ec-formula-table");
        if (!table) {
            finishInitialRender();
            return;
        }
        initTheadFilters(table);
        initSaveHandlers(table);
        finishInitialRender();
    });
})();
