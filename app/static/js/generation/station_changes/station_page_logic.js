document.addEventListener("DOMContentLoaded", () => {
    // Экспорт station_changes без зависания страницы (по аналогии со stations)
    function setupExportButton(buttonId, exportPath) {
        const exportButton = document.getElementById(buttonId);
        if (!exportButton) return;

        exportButton.addEventListener("click", function (e) {
            e.preventDefault();

            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Экспорт...';
            this.disabled = true;

            // Берем текущие параметры из URL
            const currentUrl = new URL(window.location.href);
            const params = new URLSearchParams(currentUrl.search);

            // Фиксируем версию БД, с которой была отрисована эта вкладка, чтобы выгрузка
            // не зависела от того, что пользователь мог позже переключить версию в другой вкладке.
            if (!params.has("database_version_id") && window.initialState && window.initialState.dbVersionId !== undefined) {
                const v = window.initialState.dbVersionId;
                if (v === null) {
                    params.set("database_version_id", "null");
                } else if (v !== undefined) {
                    params.set("database_version_id", String(v));
                }
            }

            // Формируем URL для экспорта
            const exportUrl = exportPath + '?' + params.toString();

            // Запускаем скачивание в новой вкладке, чтобы не блокировать UI
            window.open(exportUrl, '_blank');

            setTimeout(() => {
                this.innerHTML = originalText;
                this.disabled = false;
            }, 800);
        });
    }

    setupExportButton("exportStationChangesExcel", "/generation/station_changes/station_changes_list/export");
    setupExportButton("exportStationChangesAppendixBExcel", "/generation/station_changes/station_changes_list/export_appendix_b");
    setupExportButton("exportStationChangesPril2RussiaExcel", "/generation/station_changes/station_changes_list/export_pril_2_russia");
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
        // Фильтры-датчики (год), которые применяем только по кнопке "Ок"
        const dateFilters = [
            'date_exploitation_filter',
            'date_decompressing_expected_filter',
            'date_modernization_expected_filter'
        ];

        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.addEventListener('change', e => {
                if (e.target.matches('input[type="checkbox"]')) {
                    const filterName = e.target.name;
                    // Для годовых фильтров не применяем автоматически
                    if (dateFilters.includes(filterName)) {
                        return;
                    }
                    const params = new URLSearchParams(window.location.search);
                    params.delete(filterName);
                    document.querySelectorAll(`input[name="${filterName}"]:checked`).forEach(cb => {
                        params.append(filterName, cb.value);
                    });
                    // При изменении фильтра возвращаемся на первую страницу
                    params.set('page', '1');
                    window.location.href = window.location.pathname + "?" + params.toString();
                }
            });
        });
    }

    // === 2.1. Кнопки "Ок" / "Сбросить" для годовых фильтров в шапке таблицы
    function setupHeaderDateFilterButtons() {
        // Кнопка "Ок" — применяем значения фильтра и перегружаем страницу
        document.querySelectorAll('.filter-apply-btn').forEach(button => {
            button.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                const filterName = this.getAttribute('data-filter-name');
                if (!filterName) return;

                const params = new URLSearchParams(window.location.search);
                params.delete(filterName);

                document.querySelectorAll(`input[name="${filterName}"]:checked`).forEach(cb => {
                    params.append(filterName, cb.value);
                });

                params.set('page', '1');
                window.location.href = window.location.pathname + "?" + params.toString();
            });
        });

        // Кнопка "Сбросить" — просто снимает галочки (без перезагрузки)
        document.querySelectorAll('.filter-reset-btn').forEach(button => {
            button.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                const filterName = this.getAttribute('data-filter-name');
                if (!filterName) return;

                document.querySelectorAll(`input[name="${filterName}"]`).forEach(cb => {
                    cb.checked = false;
                });
            });
        });
    }

    // === 2.2. Кнопка "X" рядом с фильтром в шапке таблицы — сброс выбранного фильтра
    function setupHeaderFilterClearButtons() {
        document.querySelectorAll('.filter-clear-btn').forEach(button => {
            button.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                const filterName = this.getAttribute('data-filter-name');
                if (!filterName) return;

                const params = new URLSearchParams(window.location.search);
                params.delete(filterName);
                params.set('page', '1');

                const newUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
                window.location.href = newUrl;
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

    // === 4. Переключатель "все электростанции / постранично" + выпадающий список
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
        "/static/js/generation/station_changes/station_filters_first_row.js",
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
    setupHeaderDateFilterButtons();
    setupHeaderFilterClearButtons();
    setupMachinePowerRows();
    setupPerPageToggle();
    setupRoundingDigits();
    setupShowTotalsToggle();
});