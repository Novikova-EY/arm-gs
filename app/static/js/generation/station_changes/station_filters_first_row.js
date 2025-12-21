
window.stationFiltersInitialized = false;

function initializeStationFilters() {
    if (window.stationFiltersInitialized) return;
    window.stationFiltersInitialized = true;

    if (!$.fn.select2) {
        alert("⚠️ Ошибка: Select2 не загружена!");
        return;
    }

    function initializeSelect2(selector, placeholder) {
        if ($(selector).length) {
            // Проверяем, не инициализирован ли уже Select2
            if (!$(selector).data('select2')) {
                $(selector).select2({
                    placeholder: placeholder,
                    allowClear: true,
                    width: '100%',
                    closeOnSelect: false,
                    minimumResultsForSearch: Infinity
                });
            }
        } else {
            console.warn(`❌ Select2: элемент ${selector} не найден`);
        }
    }

    // Откладываем инициализацию select2, чтобы collapse успел отрисоваться
    setTimeout(() => {
        initializeSelect2('#energy_system_type', 'Тип энергосистемы');
        initializeSelect2('#union_energy_system', 'ОЭС');
        initializeSelect2('#regional_energy_system', 'Региональная энергосистема');
        initializeSelect2('#federal_district', 'Федеральный округ');
        initializeSelect2('#regional_district', 'Субъект РФ');
    }, 100);

    function parseMaybeJSON(value, fallback) {
        if (value == null) return fallback;
        if (typeof value === 'string') {
            const trimmed = value.trim();
            if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                try { return JSON.parse(trimmed); } catch (e) { return fallback; }
            }
            return fallback;
        }
        return value;
    }

    // Источник данных: JSON-блок на странице
    let filtersData = null;
    const filtersEl = document.getElementById('filters-data');
    if (filtersEl && filtersEl.textContent) {
        try { filtersData = JSON.parse(filtersEl.textContent); } catch (e) { filtersData = null; }
    }

    // Получаем все данные из filtersData
    const allEnergySystemTypes = filtersData?.energy_system_type_list || [];
    const allUnionEnergySystems = filtersData?.union_energy_system_list || [];
    const allRegionalEnergySystems = filtersData?.regional_energy_system_list || [];
    const allFederalDistricts = filtersData?.federal_district_list || [];
    const allRegionalDistricts = filtersData?.regional_district_list || [];

    // Получаем все маппинги
    const estToUes = filtersData?.est_to_ues_mapping || {};
    const estToRes = filtersData?.est_to_res_mapping || {};
    const estToRd = filtersData?.est_to_rd_mapping || {};
    const estToFd = filtersData?.est_to_fd_mapping || {};
    const uesToEst = filtersData?.ues_to_est_mapping || {};
    const uesToRes = filtersData?.regional_energy_system_mapping || {}; // старое название
    const uesToRd = filtersData?.ues_to_rd_mapping || {};
    const uesToFd = filtersData?.ues_to_fd_mapping || {};
    const resToEst = filtersData?.res_to_est_mapping || {};
    const resToRd = filtersData?.res_to_rd_mapping || {};
    const resToFd = filtersData?.res_to_fd_mapping || {};
    const resToUesOne = filtersData?.res_to_ues_mapping_one || {}; // один-к-одному
    const rdToRes = filtersData?.rd_to_res_mapping || {};
    const rdToUes = filtersData?.rd_to_ues_mapping || {};
    const rdToEst = filtersData?.rd_to_est_mapping || {};
    const rdToFdOne = filtersData?.rd_to_fd_mapping_one || {}; // один-к-одному
    const fdToRes = filtersData?.fd_to_res_mapping || {};
    const fdToUes = filtersData?.fd_to_ues_mapping || {};
    const fdToEst = filtersData?.fd_to_est_mapping || {};
    const fdToRd = filtersData?.regional_district_mapping || {}; // старое название

    // Получаем текущие выбранные значения
    const selectedEst = parseMaybeJSON(filtersData?.energy_system_type_filter, []);
    const selectedUes = parseMaybeJSON(filtersData?.union_energy_system_filter, []);
    const selectedRes = parseMaybeJSON(filtersData?.regional_energy_system_filter, []);
    const selectedFd = parseMaybeJSON(filtersData?.federal_district_filter, []);
    const selectedRd = parseMaybeJSON(filtersData?.regional_district_filter, []);

    // Флаг для предотвращения рекурсии
    let isUpdating = false;

    // Функция для получения разрешенных ID на основе выбранных фильтров (один-ко-многим)
    function getAllowedIds(selectedIds, mapping) {
        if (!selectedIds || selectedIds.length === 0) return null;
        const allowed = new Set();
        selectedIds.forEach(id => {
            const ids = mapping[String(id)] || mapping[Number(id)] || [];
            if (Array.isArray(ids)) {
                ids.forEach(allowedId => allowed.add(Number(allowedId)));
            } else if (ids !== null && ids !== undefined) {
                // Для один-к-одному маппингов
                allowed.add(Number(ids));
            }
        });
        return allowed.size > 0 ? allowed : null;
    }

    // Функция для получения разрешенных ID из один-к-одному маппинга
    function getAllowedIdsFromOneToOne(selectedIds, mapping) {
        if (!selectedIds || selectedIds.length === 0) return null;
        const allowed = new Set();
        selectedIds.forEach(id => {
            const mappedId = mapping[String(id)] || mapping[Number(id)];
            if (mappedId !== null && mappedId !== undefined) {
                allowed.add(Number(mappedId));
            }
        });
        return allowed.size > 0 ? allowed : null;
    }

    // Функция для объединения нескольких наборов разрешенных ID
    function combineAllowedIds(...allowedSets) {
        const nonNull = allowedSets.filter(s => s !== null);
        if (nonNull.length === 0) return null;
        if (nonNull.length === 1) return nonNull[0];
        
        // Пересечение всех наборов
        let result = new Set(nonNull[0]);
        for (let i = 1; i < nonNull.length; i++) {
            result = new Set([...result].filter(x => nonNull[i].has(x)));
        }
        return result.size > 0 ? result : null;
    }

    // Функция для обновления опций в select
    function updateSelectOptions(selector, allItems, allowedIds, prevSelected, skipTrigger = false) {
        let options = '<option></option>';
        const newSelected = [];
        const prevSelectedSet = new Set((prevSelected || []).map(String));

        allItems.forEach(item => {
            const itemId = Number(item.id);
            const isAllowed = allowedIds === null || allowedIds.has(itemId);
            const wasSelected = prevSelectedSet.has(String(itemId));

            if (isAllowed) {
                const selected = wasSelected ? "selected" : "";
                options += `<option value="${itemId}" ${selected}>${item.name}</option>`;
                if (wasSelected) newSelected.push(String(itemId));
            }
        });

        $(selector).html(options).val(newSelected);
        if (!skipTrigger) {
            // Обновляем Select2 без триггера события change
            $(selector).trigger('change.select2');
        }
    }

    // Функция для обновления всех фильтров на основе текущих выборов
    function updateAllFilters() {
        // Предотвращаем рекурсию
        if (isUpdating) return;
        isUpdating = true;

        try {
            const currentEst = ($('#energy_system_type').val() || []).map(Number);
            const currentUes = ($('#union_energy_system').val() || []).map(Number);
            const currentRes = ($('#regional_energy_system').val() || []).map(Number);
            const currentFd = ($('#federal_district').val() || []).map(Number);
            const currentRd = ($('#regional_district').val() || []).map(Number);

            // Вычисляем разрешенные ID для каждого фильтра
            // Тип энергосистемы: фильтруется по выбранным ОЭС, РЭС, субъектам РФ, ФО
            const estAllowedFromUes = getAllowedIdsFromOneToOne(currentUes, uesToEst);
            const estAllowedFromRes = getAllowedIdsFromOneToOne(currentRes, resToEst);
            const estAllowedFromRd = getAllowedIds(currentRd, rdToEst);
            const estAllowedFromFd = getAllowedIds(currentFd, fdToEst);
            const estAllowed = combineAllowedIds(estAllowedFromUes, estAllowedFromRes, estAllowedFromRd, estAllowedFromFd);

            // ОЭС: фильтруется по типу ЭС, РЭС, субъекту РФ, ФО
            const uesAllowedFromEst = getAllowedIds(currentEst, estToUes);
            const uesAllowedFromRes = getAllowedIdsFromOneToOne(currentRes, resToUesOne);
            const uesAllowedFromRd = getAllowedIds(currentRd, rdToUes);
            const uesAllowedFromFd = getAllowedIds(currentFd, fdToUes);
            const uesAllowed = combineAllowedIds(uesAllowedFromEst, uesAllowedFromRes, uesAllowedFromRd, uesAllowedFromFd);

            // РЭС: фильтруется по типу ЭС, ОЭС, субъекту РФ, ФО
            const resAllowedFromEst = getAllowedIds(currentEst, estToRes);
            const resAllowedFromUes = getAllowedIds(currentUes, uesToRes);
            const resAllowedFromRd = getAllowedIds(currentRd, rdToRes);
            const resAllowedFromFd = getAllowedIds(currentFd, fdToRes);
            const resAllowed = combineAllowedIds(resAllowedFromEst, resAllowedFromUes, resAllowedFromRd, resAllowedFromFd);

            // Федеральный округ: фильтруется по типу ЭС, ОЭС, РЭС, субъекту РФ
            const fdAllowedFromEst = getAllowedIds(currentEst, estToFd);
            const fdAllowedFromUes = getAllowedIds(currentUes, uesToFd);
            const fdAllowedFromRes = getAllowedIds(currentRes, resToFd);
            const fdAllowedFromRd = getAllowedIdsFromOneToOne(currentRd, rdToFdOne);
            const fdAllowed = combineAllowedIds(fdAllowedFromEst, fdAllowedFromUes, fdAllowedFromRes, fdAllowedFromRd);

            // Субъект РФ: фильтруется по типу ЭС, ОЭС, РЭС, ФО
            const rdAllowedFromEst = getAllowedIds(currentEst, estToRd);
            const rdAllowedFromUes = getAllowedIds(currentUes, uesToRd);
            const rdAllowedFromRes = getAllowedIds(currentRes, resToRd);
            const rdAllowedFromFd = getAllowedIds(currentFd, fdToRd);
            const rdAllowed = combineAllowedIds(rdAllowedFromEst, rdAllowedFromUes, rdAllowedFromRes, rdAllowedFromFd);

            // Обновляем все select'ы без триггера события change (чтобы избежать рекурсии)
            updateSelectOptions('#energy_system_type', allEnergySystemTypes, estAllowed, currentEst, true);
            updateSelectOptions('#union_energy_system', allUnionEnergySystems, uesAllowed, currentUes, true);
            updateSelectOptions('#regional_energy_system', allRegionalEnergySystems, resAllowed, currentRes, true);
            updateSelectOptions('#federal_district', allFederalDistricts, fdAllowed, currentFd, true);
            updateSelectOptions('#regional_district', allRegionalDistricts, rdAllowed, currentRd, true);
        } finally {
            isUpdating = false;
        }
    }


    // Обработчики изменений для каждого фильтра
    $('#energy_system_type').on('change', function() {
        updateAllFilters();
    });

    $('#union_energy_system').on('change', function() {
        updateAllFilters();
    });

    $('#regional_energy_system').on('change', function() {
        updateAllFilters();
    });

    $('#federal_district').on('change', function() {
        updateAllFilters();
    });

    $('#regional_district').on('change', function() {
        updateAllFilters();
    });

    // Инициализация при загрузке страницы
    if (selectedEst.length > 0) {
        $('#energy_system_type').val(selectedEst.map(String)).trigger('change');
    }
    if (selectedUes.length > 0) {
        $('#union_energy_system').val(selectedUes.map(String)).trigger('change');
    }
    if (selectedRes.length > 0) {
        $('#regional_energy_system').val(selectedRes.map(String)).trigger('change');
    }
    if (selectedFd.length > 0) {
        $('#federal_district').val(selectedFd.map(String)).trigger('change');
    }
    if (selectedRd.length > 0) {
        $('#regional_district').val(selectedRd.map(String)).trigger('change');
    }

    // Вызываем updateAllFilters для первоначальной настройки
    setTimeout(() => {
        updateAllFilters();
    }, 200);
}
