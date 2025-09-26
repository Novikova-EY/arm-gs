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
        // Сохраним исходный rowspan у ячеек агрегатов (где rowspan="3")
        $('.rowspan-td').each(function() {
            $(this).data('original-rowspan', $(this).attr('rowspan'));
        });

        // Сохраняем rowspan для ячеек с названием станции
        $('.station-rowspan-td').each(function() {
            let originalRowspan = parseInt($(this).attr('rowspan'), 10);
            let totalMachines = (originalRowspan - 1) / 3;
            $(this).data('total-machines', totalMachines);
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

            // Меняем rowspan для ячеек агрегатов
            $('.rowspan-td').each(function() {
                let original = parseInt($(this).data('original-rowspan'), 10);
                $(this).attr('rowspan', aggregatorRows);
            });

            // Меняем rowspan для ячеек с названием станции
            $('.station-rowspan-td').each(function() {
                let totalMachines = parseInt($(this).data('total-machines'), 10);
                let newRowSpan = totalMachines * aggregatorRows + 1;
                $(this).attr('rowspan', newRowSpan);
            });

            // Обновляем корректное отображение суммарных мощностей
            $('.power-column').each(function() {
                let totalRow = $(this).closest('tr').find('.total-row-cell');
                if (totalRow.length) {
                    totalRow.attr('rowspan', aggregatorRows);
                }
            });

        }

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