// main_optimized.js
document.addEventListener("DOMContentLoaded", () => {
    const jsonEl = document.getElementById("initial-state-json");
    if (jsonEl) {
        try {
            window.initialState = JSON.parse(jsonEl.textContent);
            console.log("✅ initialState загружен:", window.initialState);
        } catch (e) {
            console.error("❌ Ошибка парсинга initialState:", e);
        }
    } else {
        console.warn("⚠️ initial-state-json не найден в DOM");
    }
});

// 1. Collapse логика
function setupCollapseToggle(collapseId, buttonId, scriptUrl, flagVar = "scriptLoaded") {
    const collapseEl = document.getElementById(collapseId);
    const buttonEl = document.getElementById(buttonId);
    if (!collapseEl || !buttonEl) return;

    function highlight() {
        buttonEl.classList.remove("btn-outline-secondary");
        buttonEl.classList.add("btn-primary", "text-white");
    }

    function reset() {
        buttonEl.classList.remove("btn-primary", "text-white");
        buttonEl.classList.add("btn-outline-secondary");
    }

    function lazyLoadScript() {
        if (window[flagVar]) return;
        window[flagVar] = true;
        const script = document.createElement("script");
        script.src = scriptUrl;
        document.head.appendChild(script);
    }

    const collapse = new bootstrap.Collapse(collapseEl, { toggle: false });

    if (collapseEl.classList.contains("show") || window.initialState.hasActiveFilters) {
        collapse.show();
        highlight();
        lazyLoadScript();
    }

    collapseEl.addEventListener("show.bs.collapse", () => {
        highlight();
        lazyLoadScript();
    });

    collapseEl.addEventListener("hide.bs.collapse", reset);
}

// 2. Обработка чекбоксов фильтров
function setupDropdownCheckboxFilters() {
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.addEventListener('change', e => {
            if (e.target.matches('input[type="checkbox"]')) {
                const filterName = e.target.name;
                const params = new URLSearchParams(window.location.search);
                params.delete(filterName);
                document.querySelectorAll(`input[name="${filterName}"]:checked`).forEach(cb => {
                    params.append(filterName, cb.value);
                });
                window.location.href = window.location.pathname + "?" + params.toString();
            }
        });
    });
}

// 3. Обработка отображения p_ogr и p_rasp
function setupMachinePowerRows() {
    const togglePOgr = document.getElementById("toggleP_Ogr");
    const togglePRasp = document.getElementById("toggleP_Rasp");

    if (togglePRasp && !togglePRasp.checked) togglePRasp.checked = true;

    function update() {
        const showPOgr = togglePOgr?.checked || false;
        const showPRasp = togglePRasp?.checked || false;
        const rowsPerMachine = 1 + (showPOgr ? 1 : 0) + (showPRasp ? 1 : 0);

        document.querySelectorAll(".p-ogr-row").forEach(r => r.style.display = showPOgr ? "" : "none");
        document.querySelectorAll(".p-rasp-row").forEach(r => r.style.display = showPRasp ? "" : "none");
        document.querySelectorAll(".rowspan-td").forEach(td => td.setAttribute("rowspan", rowsPerMachine));

        document.querySelectorAll(".station-rowspan-td").forEach(td => {
            const total = parseInt(td.dataset.totalMachines || "1", 10);
            td.setAttribute("rowspan", total * rowsPerMachine + 1);
        });

        document.querySelectorAll(".fuel-cell").forEach(cell => {
            const base = parseInt(cell.dataset.baseRowspan || "1", 10);
            cell.setAttribute("rowspan", base * rowsPerMachine);
            cell.style.display = "table-cell";
        });

        document.querySelectorAll(".total-row-cell").forEach(td => td.setAttribute("rowspan", rowsPerMachine));
    }

    // Инициализация
    document.querySelectorAll(".rowspan-td").forEach(td => td.dataset.originalRowspan = td.getAttribute("rowspan"));
    document.querySelectorAll(".station-rowspan-td").forEach(td => {
        const val = parseInt(td.getAttribute("rowspan"), 10);
        td.dataset.totalMachines = (val - 1) / 3;
    });
    document.querySelectorAll(".fuel-cell").forEach(td => td.dataset.baseRowspan = td.getAttribute("rowspan") || "1");

    [togglePOgr, togglePRasp].forEach(t => t?.addEventListener("change", update));
    if ('requestIdleCallback' in window) requestIdleCallback(update);
    else setTimeout(update, 0);
}

// 4. Переключение "все станции / постранично"
function setupPerPageToggle() {
    const checkbox = document.getElementById("per_page_switch");
    const selectBlock = document.getElementById("per_page_select_block");

    if (!checkbox) return;

    checkbox.addEventListener("change", () => {
        const params = new URLSearchParams(window.location.search);
        params.set("per_page", checkbox.checked ? "all" : "10");
        window.location.href = window.location.pathname + "?" + params.toString();
    });

    if (selectBlock) {
        selectBlock.classList.toggle("d-none", checkbox.checked);
    }
}

// 5. Изменение округления
function setupRoundingDigits() {
    const select = document.getElementById("rounding_digits");
    if (!select) return;

    select.addEventListener("change", () => {
        const url = new URL(window.location.href);
        url.searchParams.set("rounding_digits", select.value);
        url.searchParams.set("page", 1);
        window.location.href = url.toString();
    });
}

// ==== Инициализация всех функций ==== //
document.addEventListener("DOMContentLoaded", () => {
    setupCollapseToggle("filtersCollapse", "filtersToggleBtn", "/static/js/stations/station_filters_first_row.js", "stationFiltersInitialized");
    setupCollapseToggle("importExportCollapse", "importExportToggleBtn", "/static/js/stations/station_second_row.js", "importExportScriptLoaded");
    setupDropdownCheckboxFilters();
    setupMachinePowerRows();
    setupPerPageToggle();
    setupRoundingDigits();
});
