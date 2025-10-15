document.addEventListener("DOMContentLoaded", () => {
    // Экспорт station_changes без зависания страницы (по аналогии со stations)
    const exportButton = document.getElementById("exportStationChangesExcel");
    if (exportButton) {
        exportButton.addEventListener("click", function (e) {
            e.preventDefault();

            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Экспорт...';
            this.disabled = true;

            // Берём текущие параметры из URL
            const currentUrl = new URL(window.location.href);
            const params = new URLSearchParams(currentUrl.search);

            // Формируем URL для экспорта
            const exportUrl = '/generation/station_changes/station_changes_list/export?' + params.toString();

            // Запускаем скачивание в новой вкладке, чтобы не блокировать UI
            window.open(exportUrl, '_blank');

            setTimeout(() => {
                this.innerHTML = originalText;
                this.disabled = false;
            }, 800);
        });
    }
});

// station_combined.js

document.addEventListener("DOMContentLoaded", () => {
    // === 0. Загрузка initialState (для collapse с фильтрами)
    const jsonEl = document.getElementById("initial-state-json");
    if (jsonEl) {
        try {
            window.initialState = JSON.parse(jsonEl.textContent);
        } catch (e) {
            window.initialState = { hasActiveFilters: false };
        }
    } else {
        window.initialState = { hasActiveFilters: false };
    }

    // === 1. Collapse-фильтры и импорт/экспорт с lazy-скриптами
    function setupCollapseToggle(collapseId, buttonId, scriptUrl, flagVar = "scriptLoaded", forceOpen = false) {
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
            script.onload = () => {
                // Только для фильтров
                if (collapseId === "filtersCollapse" && typeof initializeStationFilters === "function") {
                    initializeStationFilters();
                }
            };
            document.head.appendChild(script);
        }

        const collapse = new bootstrap.Collapse(collapseEl, { toggle: false });

        if (collapseEl.classList.contains("show") || forceOpen) {
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

    // === 2. Обработка фильтров в dropdown
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

    // === 3. Обработка отображения p_ogr / p_rasp
    function setupMachinePowerRows() {
        const togglePOgr = document.getElementById("toggleP_Ogr");
        const togglePRasp = document.getElementById("toggleP_Rasp");
        const form = document.getElementById('stationFilterForm');

        function update() {
            const showPOgr = togglePOgr?.checked || false;
            const showPRasp = togglePRasp?.checked || false;

            // Показ/скрытие всех строк Рогр (и станций, и машин)
            document.querySelectorAll(".p-ogr-row").forEach(row => {
                row.style.display = showPOgr ? "" : "none";
            });

            // Показ/скрытие всех строк Ррасп
            document.querySelectorAll(".p-rasp-row").forEach(row => {
                row.style.display = showPRasp ? "" : "none";
            });
        }

        // При изменении — автосабмит формы
        togglePOgr?.addEventListener('change', () => {
            form.submit();
        });

        togglePRasp?.addEventListener('change', () => {
            form.submit();
        });

        // Вызываем обновление видимости строк при загрузке (чтобы они скрывались даже без перезагрузки)
        update();

        window.updateRows = update;
    }

    // === 4. Переключатель "все станции / постранично" + выпадающий список
    function setupPerPageToggle() {
        const perPageSelect = document.getElementById("per_page_select");

        // Обработчик для выпадающего списка количества станций
        if (perPageSelect) {
            perPageSelect.addEventListener("change", () => {
                const params = new URLSearchParams(window.location.search);
                params.set("per_page", perPageSelect.value);
                params.set("page", 1); // Сбрасываем на первую страницу
                window.location.href = window.location.pathname + "?" + params.toString();
            });
        }
    }

    // === 5. Изменение округления
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

    // === 6. Переключатель "Суммы по регионам" (show_totals)
    function setupShowTotalsToggle() {
        const toggle = document.getElementById('show_totals_switch');
        if (!toggle) return;

        const updateUrl = () => {
            const url = new URL(window.location.href);
            url.searchParams.set('show_totals', toggle.checked ? '1' : '0');
            url.searchParams.set('page', 1);
            window.location.href = url.toString();
        };

        toggle.addEventListener('change', updateUrl);
    }

    // === Инициализация всех блоков ===
    setupCollapseToggle(
        "filtersCollapse",
        "filtersToggleBtn",
        "/static/js/generation/stations/station_filters_first_row.js",
        "stationFiltersInitialized",
        window.initialState.hasActiveFilters // ← только для фильтров
    );

    setupCollapseToggle(
        "importExportCollapse",
        "importExportToggleBtn",
        "/static/js/generation/stations/station_second_row.js",
        "importExportScriptLoaded",
        false // ← никогда не раскрывать импорт/экспорт автоматически
    );
    setupDropdownCheckboxFilters();
    setupMachinePowerRows();
    setupPerPageToggle();
    setupRoundingDigits();
    setupShowTotalsToggle();
});