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
        // Только эти чекбоксы в шапке перезагружают страницу сразу при изменении.
        // Годовые фильтры (Ввод/Модерн./…) применяются только по кнопке «Ок» — их имя здесь не указываем.
        const instantApplyCheckboxFilters = [
            'station_type_filter',
            'tes_type_filter',
            'tes_machine_type_filter',
            'fuel_type_filter',
            'relabing_outcome_filter',
            'pgu_tes_machine_type_filter',
        ];

        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.addEventListener('change', e => {
                if (e.target.matches('input[type="checkbox"]')) {
                    const filterName = e.target.name;
                    if (!instantApplyCheckboxFilters.includes(filterName)) {
                        return;
                    }
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
    
    // === 2.1. Обработка фильтров с подтверждением (ОК/Отмена) для дат
    function setupDateFilterDropdowns() {
        const dateFilters = ['date_commission_filter', 'date_exploitation_filter', 'date_decompressing_expected_filter', 'date_modernization_expected_filter', 'date_modernization_no_power_expected_filter'];
        
        // Сохраняем исходное состояние чекбоксов при открытии dropdown
        document.querySelectorAll('.date-filter-dropdown').forEach(menu => {
            const filterName = menu.getAttribute('data-filter-name');
            if (!dateFilters.includes(filterName)) return;
            
            let originalState = {};
            
            // Находим кнопку, которая открывает dropdown
            const dropdownButton = menu.previousElementSibling;
            if (!dropdownButton) return;
            
            // Сохраняем состояние при показе dropdown (используем событие Bootstrap)
            dropdownButton.addEventListener('shown.bs.dropdown', () => {
                // Сохраняем текущее состояние всех чекбоксов
                menu.querySelectorAll(`input[name="${filterName}"]`).forEach(cb => {
                    originalState[cb.value] = cb.checked;
                });
            });
            
            // Обработчик кнопки ОК
            const okButton = menu.querySelector('.date-filter-ok');
            if (okButton) {
                okButton.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const params = new URLSearchParams(window.location.search);
                    params.delete(filterName);
                    
                    // Добавляем только выбранные чекбоксы
                    menu.querySelectorAll(`input[name="${filterName}"]:checked`).forEach(cb => {
                        params.append(filterName, cb.value);
                    });
                    
                    params.set('page', '1'); // Сбрасываем на первую страницу
                    
                    // Закрываем dropdown
                    const dropdownInstance = bootstrap.Dropdown.getInstance(dropdownButton);
                    if (dropdownInstance) {
                        dropdownInstance.hide();
                    }
                    
                    // Применяем фильтр
                    window.location.href = window.location.pathname + "?" + params.toString();
                });
            }
            
            // Обработчик кнопки Отмена - восстанавливаем исходное состояние
            const cancelButton = menu.querySelector('.date-filter-cancel');
            if (cancelButton) {
                cancelButton.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Восстанавливаем исходное состояние чекбоксов
                    menu.querySelectorAll(`input[name="${filterName}"]`).forEach(cb => {
                        cb.checked = originalState[cb.value] || false;
                    });
                    
                    // Закрываем dropdown
                    const dropdownInstance = bootstrap.Dropdown.getInstance(dropdownButton);
                    if (dropdownInstance) {
                        dropdownInstance.hide();
                    }
                });
            }
            
            // Обработчик "Все" - сбрасывает все галочки и применяет фильтр
            const clearItem = menu.querySelector('.clear-filter-item');
            if (clearItem) {
                clearItem.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Снимаем все галочки
                    menu.querySelectorAll(`input[name="${filterName}"]`).forEach(cb => {
                        cb.checked = false;
                    });
                    
                    const params = new URLSearchParams(window.location.search);
                    params.delete(filterName);
                    params.set('page', '1');
                    
                    // Закрываем dropdown
                    const dropdownInstance = bootstrap.Dropdown.getInstance(dropdownButton);
                    if (dropdownInstance) {
                        dropdownInstance.hide();
                    }
                    
                    // Применяем фильтр (пустой, т.е. сбрасываем)
                    window.location.href = window.location.pathname + "?" + params.toString();
                });
            }
        });
    }
    
    // Скрипт для отображения строк с располагаемой мощность и ограничениями мощности
    (function setupPowerRowsVanilla() {
        if (window.machineRowsSetupDone) return;
        window.machineRowsSetupDone = true;

        // Сохраним исходный rowspan у ячеек агрегатов — только один раз
        document.querySelectorAll('.rowspan-td').forEach(td => {
            if (td.dataset.originalRowspan == null) {
                td.dataset.originalRowspan = td.getAttribute('rowspan') || '';
            }
        });

        // Сохраняем базовое количество агрегатов на станцию — только один раз
        document.querySelectorAll('.station-rowspan-td').forEach(td => {
            const dataTotalMachines = td.getAttribute('data-total-machines');
            const dataTotalPgu = td.getAttribute('data-total-pgu-count');

            if (td.dataset.totalMachines == null) {
                if (dataTotalMachines != null) {
                    td.dataset.totalMachines = String(parseInt(dataTotalMachines, 10) || 0);
                } else {
                    const originalRowspan = parseInt(td.getAttribute('rowspan') || '0', 10);
                    const totalMachines = (originalRowspan - 1) / 3;
                    td.dataset.totalMachines = String(totalMachines || 0);
                }
            }
            if (td.dataset.totalPguCount == null && dataTotalPgu != null) {
                td.dataset.totalPguCount = String(parseInt(dataTotalPgu, 10) || 0);
            }
        });

        function showEl(el) {
            if (!el) return;
            const tag = (el.tagName || '').toUpperCase();
            // Для табличных элементов важно явно выставлять display,
            // иначе некоторые браузеры могут не восстановить корректную геометрию таблицы.
            if (tag === 'TR') el.style.display = 'table-row';
            else if (tag === 'TD' || tag === 'TH') el.style.display = 'table-cell';
            else el.style.display = '';
        }

        function hideEl(el) {
            if (!el) return;
            el.style.display = 'none';
        }

        const showEls = (nodes) => nodes.forEach(showEl);
        const hideEls = (nodes) => nodes.forEach(hideEl);

        // Функция обновления строк
        function updateRows() {
            const showPOgr = !!document.getElementById('toggleP_Ogr')?.checked;
            const showPRasp = !!document.getElementById('toggleP_Rasp')?.checked;
            const hideAggregates = !!document.getElementById('hide_aggregates_switch')?.checked;

            const machineOgrRows = Array.from(document.querySelectorAll('.p-ogr-row.machine-ogr-row'));
            const machineRaspRows = Array.from(document.querySelectorAll('.p-rasp-row.machine-rasp-row'));
            const aggregatedOgrRows = Array.from(document.querySelectorAll('.p-ogr-row:not(.station-ogr-row):not(.machine-ogr-row)'));
            const aggregatedRaspRows = Array.from(document.querySelectorAll('.p-rasp-row:not(.station-rasp-row):not(.machine-rasp-row)'));

            // Машинные строки: зависят от showPOgr/showPRasp и hideAggregates
            if (showPOgr && !hideAggregates) showEls(machineOgrRows); else hideEls(machineOgrRows);
            if (showPRasp && !hideAggregates) showEls(machineRaspRows); else hideEls(machineRaspRows);

            // Агрегированные строки (не машинные): зависят только от переключателей
            if (showPOgr) showEls(aggregatedOgrRows); else hideEls(aggregatedOgrRows);
            if (showPRasp) showEls(aggregatedRaspRows); else hideEls(aggregatedRaspRows);

            // Итоговые строки по станции подчиняются соответствующим переключателям
            document.querySelectorAll('.station-ogr-row').forEach(row => { showPOgr ? showEl(row) : hideEl(row); });
            document.querySelectorAll('.station-rasp-row').forEach(row => { showPRasp ? showEl(row) : hideEl(row); });

            // Количество отображаемых строк на агрегат (1..3)
            const aggregatorRows = 1 + (showPOgr ? 1 : 0) + (showPRasp ? 1 : 0);

            // Обновляем rowspan для ячеек "Всего по станции"
            document.querySelectorAll('.total-row-cell').forEach(td => td.setAttribute('rowspan', String(aggregatorRows)));

            // Меняем rowspan для ячеек агрегатов: baseRows + extras
            document.querySelectorAll('.rowspan-td').forEach(td => {
                const baseRowsAttr = td.getAttribute('data-machine-base-rowspan');
                const baseRows = parseInt(baseRowsAttr || '', 10);
                if (Number.isFinite(baseRows) && baseRows > 0) {
                    const extras = aggregatorRows - 1;
                    td.setAttribute('rowspan', String(baseRows + extras));
                } else {
                    td.setAttribute('rowspan', String(aggregatorRows));
                }
            });

            // Ячейку с субъектом РФ больше не объединяем вниз (rowspan убран в шаблоне)

            // Синхронизация высоты ячеек "гр." и "Топливо (по СО ЕЭС)"
            const rowMultiplier = aggregatorRows; // 1..3
            document.querySelectorAll('.fuel-cell').forEach(cell => {
                const baseRows = parseInt(cell.getAttribute('data-base-rowspan') || '1', 10) || 1;
                const groupCount = parseInt(cell.getAttribute('data-group-machine-count') || '', 10);
                const fuelCount = parseInt(cell.getAttribute('data-fuel-machine-count') || '', 10);
                const machinesCount = Number.isFinite(groupCount) ? groupCount
                    : Number.isFinite(fuelCount) ? fuelCount
                    : 1;
                const extras = rowMultiplier - 1;
                const newRowspan = baseRows + machinesCount * extras;
                cell.setAttribute('rowspan', String(newRowspan));
                showEl(cell);
            });
        }

        // Экспортируем функцию для других обработчиков
        window.applyPowerRowsUpdate = updateRows;
        window.updateRows = updateRows; // совместимость

        updateRows();

        const togglePOgr = document.getElementById('toggleP_Ogr');
        const togglePRasp = document.getElementById('toggleP_Rasp');
        togglePOgr?.addEventListener('change', updateRows);
        togglePRasp?.addEventListener('change', updateRows);
    })();

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
            window.applyHideAggregatesUpdate?.();
            syncToggleStyles();
        });

        togglePRasp?.addEventListener('change', () => {
            window.applyPowerRowsUpdate?.();
            window.applyHideAggregatesUpdate?.();
            syncToggleStyles();
        });

        // Первичная синхронизация
        window.applyPowerRowsUpdate?.();
        syncToggleStyles();
    }

    // === 4. Переключатель отображения сумм и выбор количества станций
    function setupPerPageToggle() {
        const showTotalsCheckbox = document.getElementById("show_totals_switch");
        const fuelCheckCheckbox = document.getElementById("fuel_check_switch");
        const perPageSelect = document.getElementById("per_page_select");

        // Обработчик переключателя отображения сумм
        if (showTotalsCheckbox) {
            showTotalsCheckbox.addEventListener("change", () => {
                const params = new URLSearchParams(window.location.search);
                if (showTotalsCheckbox.checked) {
                    params.set("show_totals", "1");
                } else {
                    params.delete("show_totals");
                }
                params.set("page", 1); // Сбрасываем на первую страницу
                window.location.href = window.location.pathname + "?" + params.toString();
            });
        }

        // Обработчик проверки топлива (качество заполнения поля "Топливо (по СО ЕЭС)")
        if (fuelCheckCheckbox) {
            fuelCheckCheckbox.addEventListener("change", () => {
                const params = new URLSearchParams(window.location.search);
                if (fuelCheckCheckbox.checked) {
                    params.set("fuel_check", "1");
                } else {
                    params.delete("fuel_check");
                }
                params.set("page", 1); // Сбрасываем на первую страницу
                window.location.href = window.location.pathname + "?" + params.toString();
            });
        }

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

    // === 5. Переключатель скрытия агрегатов
    function setupHideAggregatesToggle() {
        const hideAggregatesCheckbox = document.getElementById("hide_aggregates_switch");
        const hideAggregatesLabel = document.querySelector('label[for="hide_aggregates_switch"]');

        if (!hideAggregatesCheckbox || !hideAggregatesLabel) return;

        // Функция для переключения видимости агрегатов
        function toggleAggregates() {
            const isHidden = hideAggregatesCheckbox.checked;
            const showPOgr = document.getElementById('toggleP_Ogr')?.checked || false;
            const showPRasp = document.getElementById('toggleP_Rasp')?.checked || false;
            
            // Скрываем/показываем строки с агрегатами
            document.querySelectorAll('.machine-row').forEach(row => {
                if (isHidden) {
                    row.style.display = 'none';
                } else {
                    // TR
                    row.style.display = 'table-row';
                }
            });

            // Также скрываем/показываем строки p-ogr и p-rasp для агрегатов
            // Учитываем состояние соответствующих чекбоксов
            document.querySelectorAll('.machine-ogr-row').forEach(row => {
                if (isHidden) {
                    row.style.display = 'none';
                } else {
                    row.style.display = showPOgr ? 'table-row' : 'none';
                }
            });
            
            document.querySelectorAll('.machine-rasp-row').forEach(row => {
                if (isHidden) {
                    row.style.display = 'none';
                } else {
                    row.style.display = showPRasp ? 'table-row' : 'none';
                }
            });

            // НЕ скрываем первую строку с названием станции
            // Она остается всегда видимой

            // Обновляем стиль кнопки и текст
            if (isHidden) {
                hideAggregatesLabel.classList.remove('btn-outline-secondary', 'text-dark');
                hideAggregatesLabel.classList.add('btn-primary');
                hideAggregatesLabel.textContent = 'Показать агрегаты';
            } else {
                hideAggregatesLabel.classList.remove('btn-primary');
                hideAggregatesLabel.classList.add('btn-outline-secondary', 'text-dark');
                hideAggregatesLabel.textContent = 'Скрыть агрегаты';
            }
        }

        // Обработчик изменения состояния чекбокса
        hideAggregatesCheckbox.addEventListener('change', toggleAggregates);

        // Инициализация при загрузке страницы
        toggleAggregates();

        // Экспортируем функцию для использования в других обработчиках
        window.applyHideAggregatesUpdate = toggleAggregates;
    }

    // === 6. Изменение округления
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

    // === 7. Обработка экспорта без блокировки страницы
    function setupExportFormSync() {
        const exportButton = document.getElementById("exportExcelFull");
        const hideAggregatesCheckbox = document.getElementById("hide_aggregates_switch");
        const showPOgrCheckbox = document.getElementById("toggleP_Ogr");
        const showPRaspCheckbox = document.getElementById("toggleP_Rasp");
        const showTotalsCheckbox = document.getElementById("show_totals_switch");

        if (!exportButton || !hideAggregatesCheckbox) return;

        exportButton.addEventListener("click", function(e) {
            e.preventDefault();
            
            // Визуальная индикация
            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Экспорт...';
            this.disabled = true;
            
            // Формируем URL с текущими параметрами
            const currentUrl = new URL(window.location.href);
            const params = new URLSearchParams(currentUrl.search);
            
            // Добавляем параметр hide_aggregates
            if (hideAggregatesCheckbox.checked) {
                params.set('hide_aggregates', '1');
            } else {
                params.delete('hide_aggregates');
            }
            
            // Добавляем параметры show_p_ogr и show_p_rasp из чекбоксов
            // Важно: явно передаем "0" или "1", а не удаляем параметр,
            // чтобы избежать использования значений по умолчанию на сервере
            if (showPOgrCheckbox) {
                params.set('show_p_ogr', showPOgrCheckbox.checked ? '1' : '0');
            }
            
            if (showPRaspCheckbox) {
                params.set('show_p_rasp', showPRaspCheckbox.checked ? '1' : '0');
            }
            
            // Добавляем параметр show_totals (показывать суммы по регионам)
            if (showTotalsCheckbox) {
                params.set('show_totals', showTotalsCheckbox.checked ? '1' : '0');
            }
            
            // Формируем URL для экспорта
            const exportUrl = '/generation/stations/export_station_full?' + params.toString();
            
            console.log('[EXPORT] Начало экспорта станций');
            console.log('[EXPORT] URL:', exportUrl);
            
            // Пробуем использовать fetch для лучшей обработки ошибок
            fetch(exportUrl, {
                method: 'GET',
                credentials: 'same-origin'
            })
            .then(response => {
                console.log('[EXPORT] Ответ получен, статус:', response.status);
                
                if (!response.ok) {
                    // Если ошибка, пытаемся получить текст ошибки
                    return response.text().then(text => {
                        console.error('[EXPORT] Ошибка сервера:', text);
                        throw new Error(`Ошибка сервера (${response.status}): ${text.substring(0, 200)}`);
                    });
                }
                
                // Проверяем тип контента
                const contentType = response.headers.get('content-type');
                console.log('[EXPORT] Content-Type:', contentType);
                
                if (contentType && contentType.includes('application/vnd.openxmlformats')) {
                    // Это Excel файл, скачиваем его
                    return response.blob().then(blob => {
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `stations_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                        console.log('[EXPORT] Файл успешно скачан');
                    });
                } else {
                    // Возможно, это редирект с сообщением об ошибке
                    return response.text().then(text => {
                        console.warn('[EXPORT] Неожиданный тип ответа:', contentType);
                        // Пробуем открыть как HTML (может быть страница с ошибкой)
                        const newWindow = window.open();
                        if (newWindow) {
                            newWindow.document.write(text);
                        }
                        throw new Error('Получен неожиданный тип ответа от сервера');
                    });
                }
            })
            .catch(error => {
                console.error('[EXPORT] Ошибка при экспорте:', error);
                alert('Ошибка при экспорте данных: ' + error.message + '\n\nПроверьте консоль браузера (F12) для подробностей.');
            })
            .finally(() => {
                // Возвращаем состояние кнопки
                this.innerHTML = originalText;
                this.disabled = false;
            });
        });
    }

    // === 8. Обработка экспорта СиПР без блокировки страницы
    function setupExportSiprSync() {
        const exportSiprButton = document.getElementById("exportExcelSipr");
        const exportSiprForm = document.getElementById("exportSiprForm");
        
        if (!exportSiprButton || !exportSiprForm) return;

        exportSiprButton.addEventListener("click", function(e) {
            e.preventDefault();
            
            // Визуальная индикация
            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Экспорт...';
            this.disabled = true;
            
            // Собираем URL из формы (action + все hidden поля)
            const formAction = exportSiprForm.action;
            const formData = new FormData(exportSiprForm);
            const params = new URLSearchParams(formData);
            const exportUrl = formAction + '?' + params.toString();
            
            // Открываем в новой вкладке - файл скачается, страница не зависнет
            window.open(exportUrl, '_blank');
            
            // Возвращаем состояние кнопки
            setTimeout(() => {
                this.innerHTML = originalText;
                this.disabled = false;
            }, 500);
        });
    }

    // === Инициализация всех блоков ===
    setupCollapseToggle(
        "filtersCollapse",
        "filtersToggleBtn",
        "/static/js/generation/stations/station_filters_first_row.js",
        "filtersScriptLoaded",
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
    setupDateFilterDropdowns();
    setupMachinePowerRows();
    setupPerPageToggle();
    setupHideAggregatesToggle();
    setupRoundingDigits();
    setupExportFormSync();
    setupExportSiprSync();
});