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
    
    // Скрипт для отображения строк с располагаемой мощность и ограничениями мощности
    $(document).ready(function() {
        if (window.machineRowsSetupDone) {
            return;
        }
        window.machineRowsSetupDone = true;

        // Сохраним исходный rowspan у ячеек агрегатов (где rowspan="3") — только один раз
        $('.rowspan-td').each(function() {
            if ($(this).data('original-rowspan') == null) {
                $(this).data('original-rowspan', $(this).attr('rowspan'));
            }
        });

        // Сохраняем базовое количество агрегатов на станцию — только один раз
        $('.station-rowspan-td').each(function() {
            // Приоритет: использовать данные из разметки, если есть
            const dataTotalMachines = $(this).attr('data-total-machines');
            const dataTotalPgu = $(this).attr('data-total-pgu-count');
            if ($(this).data('total-machines') == null) {
                if (dataTotalMachines != null) {
                    $(this).data('total-machines', parseInt(dataTotalMachines, 10) || 0);
                } else {
                    let originalRowspan = parseInt($(this).attr('rowspan'), 10);
                    let totalMachines = (originalRowspan - 1) / 3;
                    $(this).data('total-machines', totalMachines);
                }
            }
            if ($(this).data('total-pgu-count') == null && dataTotalPgu != null) {
                $(this).data('total-pgu-count', parseInt(dataTotalPgu, 10) || 0);
            }
        });

        // Функция обновления строк
        function updateRows() {
            let showPOgr  = $('#toggleP_Ogr').prop('checked');   // "Отображать ограничения мощности"
            let showPRasp = $('#toggleP_Rasp').prop('checked');  // "Отображать располагаемую мощность"

            // Показываем/скрываем строки p_ogr-row
            if (showPOgr) {
                $('.p-ogr-row').show();
            } else {
                $('.p-ogr-row').hide();
            }

            // Показываем/скрываем строки p_rasp-row
            if (showPRasp) {
                $('.p-rasp-row').show();
            } else {
                $('.p-rasp-row').hide();
            }

            // Количество отображаемых строк на агрегат (1..3)
            let aggregatorRows = 1 + (showPOgr ? 1 : 0) + (showPRasp ? 1 : 0);

            // Обновляем rowspan для ячейки "Всего по станции"
            $('.total-row-cell').attr('rowspan', aggregatorRows);

            // Меняем rowspan для ячеек агрегатов: baseRows + extras
            $('.rowspan-td').each(function() {
                const baseRowsAttr = this.getAttribute('data-machine-base-rowspan');
                const baseRows = parseInt(baseRowsAttr, 10);
                if (Number.isFinite(baseRows) && baseRows > 0) {
                    const extras = aggregatorRows - 1; // доп. строки на агрегат
                    this.setAttribute('rowspan', String(baseRows + extras));
                } else {
                    // fallback для ячеек без базового атрибута
                    this.setAttribute('rowspan', String(aggregatorRows));
                }
            });

            // Меняем rowspan для ячеек с названием станции
            $('.station-rowspan-td').each(function() {
                const totalMachines = parseInt($(this).data('total-machines'), 10) || 0;
                const totalPgu = parseInt($(this).data('total-pgu-count'), 10) || 0;
                const newRowSpan = (totalMachines * aggregatorRows) + totalPgu + 1;
                $(this).attr('rowspan', newRowSpan);
            });

            // Обновляем rowspan для ячейки "Всего по станции" согласно формуле
            $('.total-row-cell').attr('rowspan', aggregatorRows);

            // Синхронизация высоты ячеек "гр." и "Топливо (по СО ЕЭС)"
            const rowMultiplier = aggregatorRows; // 1..3
            document.querySelectorAll('.fuel-cell').forEach(cell => {
                if (!cell) return;
                // baseRows = сумма базовых строк по всем агрегатам группы: Σ(1 + num_pgu)
                const baseRows = parseInt(cell.getAttribute('data-base-rowspan'), 10) || 1;
                const groupCount = parseInt(cell.getAttribute('data-group-machine-count'), 10);
                const fuelCount = parseInt(cell.getAttribute('data-fuel-machine-count'), 10);
                const machinesCount = Number.isFinite(groupCount) ? groupCount
                    : Number.isFinite(fuelCount) ? fuelCount
                    : 1;
                // extras = число доп. строк (Рогр, Ррасп) на агрегат
                const extras = rowMultiplier - 1;
                // Итог: Σ(1 + num_pgu) + countMachines * extras
                const newRowspan = baseRows + machinesCount * extras;
                cell.setAttribute('rowspan', String(newRowspan));
                cell.style.display = 'table-cell';
            });

        }

        // Экспортируем функцию для других обработчиков
        window.applyPowerRowsUpdate = updateRows;
        // Алиас для совместимости с вызовами в station_details.html
        window.updateRows = updateRows;

        // Обновляем строки при загрузке страницы
        updateRows();

        // Обновляем строки при изменении чекбоксов
        $('#toggleP_Ogr, #toggleP_Rasp').on('change', function() {
            updateRows();
        });
    });

    // === 3. Обработка отображения p_ogr / p_rasp
    function setupMachinePowerRows() {
        const togglePOgr = document.getElementById("toggleP_Ogr");
        const togglePRasp = document.getElementById("toggleP_Rasp");
        const labelPOgr = document.querySelector('label[for="toggleP_Ogr"]');
        const labelPRasp = document.querySelector('label[for="toggleP_Rasp"]');

        function syncToggleStyles() {
            if (labelPRasp && togglePRasp) {
                labelPRasp.classList.toggle('btn-primary', togglePRasp.checked);
                labelPRasp.classList.toggle('btn-outline-primary', !togglePRasp.checked);
            }
            if (labelPOgr && togglePOgr) {
                // Сохраняем существующий стиль: активная = заливка, неактивная = outline
                labelPOgr.classList.toggle('btn-primary', togglePOgr.checked);
                labelPOgr.classList.toggle('btn-outline-primary', !togglePOgr.checked);
            }
        }

        // При изменении — только единая функция обновления, без дублирования логики
        togglePOgr?.addEventListener('change', () => {
            window.applyPowerRowsUpdate?.();
            syncToggleStyles();
        });

        togglePRasp?.addEventListener('change', () => {
            window.applyPowerRowsUpdate?.();
            syncToggleStyles();
        });

        // Первичная синхронизация
        window.applyPowerRowsUpdate?.();
        syncToggleStyles();
    }

    // === 4. Переключатель "все станции / постранично"
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

    // === Инициализация всех блоков ===
    setupCollapseToggle(
        "filtersCollapse",
        "filtersToggleBtn",
        "/static/js/generation/stations/station_filters_first_row.js",
        "initializeStationFilters",
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
});