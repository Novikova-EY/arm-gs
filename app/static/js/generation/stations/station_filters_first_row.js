
window.stationFiltersInitialized = false;

function initializeStationFilters() {
    if (window.stationFiltersInitialized) return;
    window.stationFiltersInitialized = true;

    // Важно для production/deb: фильтры должны работать без CDN-зависимостей.
    // Если jQuery/Select2 есть — можно проинициализировать Select2, но это не обязательное условие.
    const hasJQuery = typeof window.$ !== 'undefined';
    const hasSelect2 = hasJQuery && window.$.fn && window.$.fn.select2;

    // Если Select2 отсутствует, `<select multiple>` выглядит как "развёрнутый" список.
    // Чтобы поля "сворачивались" (как dropdown), делаем лёгкую обёртку на Bootstrap dropdown,
    // оставляя исходный <select> скрытым (для корректной отправки формы и логики фильтрации).
    function ensureDropdownMultiSelect(selector, placeholder) {
        const selectEl = document.querySelector(selector);
        if (!selectEl) return;
        if (selectEl.dataset.multiDropdownInit === '1') return;

        selectEl.dataset.multiDropdownInit = '1';

        const wrapper = document.createElement('div');
        wrapper.className = 'dropdown w-100';

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'form-select w-100 text-start';
        btn.setAttribute('data-bs-toggle', 'dropdown');
        // не закрываем при клике по чекбоксам внутри
        btn.setAttribute('data-bs-auto-close', 'outside');
        btn.setAttribute('aria-expanded', 'false');

        const menu = document.createElement('div');
        menu.className = 'dropdown-menu p-2 filter-dropdown-menu';

        // Скрываем исходный select, но оставляем в DOM для submit'а формы
        selectEl.classList.add('d-none');

        // Вставляем wrapper на место select
        const parent = selectEl.parentNode;
        if (!parent) return;
        parent.replaceChild(wrapper, selectEl);
        wrapper.appendChild(btn);
        wrapper.appendChild(menu);
        wrapper.appendChild(selectEl);

        function setButtonText() {
            const selected = Array.from(selectEl.selectedOptions)
                .map(o => o.textContent || '')
                .map(s => s.trim())
                .filter(Boolean);

            if (selected.length === 0) {
                btn.textContent = placeholder;
                return;
            }

            // Короткий текст, чтобы поле не раздувало строку
            const preview = selected.slice(0, 1).join(', ');
            const suffix = selected.length > 1 ? ` (+${selected.length - 1})` : '';
            btn.textContent = `${preview}${suffix}`;
        }

        function renderMenu() {
            menu.innerHTML = '';

            const actions = document.createElement('div');
            actions.className = 'd-flex justify-content-between align-items-center mb-2 gap-2';

            const title = document.createElement('div');
            title.className = 'fw-bold';
            title.textContent = placeholder;

            const clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.className = 'btn btn-sm btn-outline-danger';
            clearBtn.textContent = 'Сбросить';
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                // Явный сброс пользователем: не автоподставлять "единственный доступный" вариант обратно
                // до тех пор, пока пользователь сам не выберет значение в этом поле.
                selectEl.dataset.skipAutoselect = '1';
                Array.from(selectEl.options).forEach(opt => { opt.selected = false; });
                setButtonText();
                selectEl.dispatchEvent(new Event('change', { bubbles: true }));
                renderMenu();
            });

            actions.appendChild(title);
            actions.appendChild(clearBtn);
            menu.appendChild(actions);

            const list = document.createElement('div');
            list.className = 'd-flex flex-column gap-1';

            Array.from(selectEl.options).forEach(opt => {
                const value = (opt.value ?? '').toString();
                // пустой option используем как placeholder/allowClear — в меню не показываем
                if (value === '') return;

                const item = document.createElement('label');
                item.className = 'dropdown-item d-flex align-items-center gap-2';
                item.style.whiteSpace = 'normal';

                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = !!opt.selected;
                cb.addEventListener('click', (e) => {
                    // не закрываем dropdown
                    e.stopPropagation();
                });
                cb.addEventListener('change', (e) => {
                    e.stopPropagation();
                    // Пользователь меняет поле вручную — разрешаем автоподстановку снова.
                    delete selectEl.dataset.skipAutoselect;
                    // находим option по value (opt может быть пересоздан при updateSelectOptions)
                    const found = Array.from(selectEl.options).find(o => String(o.value) === value);
                    if (found) found.selected = cb.checked;
                    setButtonText();
                    selectEl.dispatchEvent(new Event('change', { bubbles: true }));
                });

                const text = document.createElement('span');
                text.textContent = (opt.textContent || '').trim();

                item.appendChild(cb);
                item.appendChild(text);
                list.appendChild(item);
            });

            menu.appendChild(list);
            setButtonText();
        }

        // экспортируем рендер для обновления после пересборки options
        selectEl._multiDropdownRender = renderMenu;

        renderMenu();
    }

    function refreshDropdownMultiSelect(selector) {
        const el = document.querySelector(selector);
        if (!el) return;
        if (el.dataset.multiDropdownInit !== '1') return;
        if (typeof el._multiDropdownRender === 'function') {
            el._multiDropdownRender();
        }
    }

    function initializeSelect2IfAvailable(selector, placeholder) {
        if (!hasSelect2) return;
        const $el = window.$(selector);
        if (!$el.length) return;
        if ($el.data('select2')) return;
        $el.select2({
            placeholder,
            allowClear: true,
            width: '100%',
            closeOnSelect: false,
            minimumResultsForSearch: Infinity
        });
    }

    // Откладываем инициализацию, чтобы collapse успел отрисоваться
    setTimeout(() => {
        initializeSelect2IfAvailable('#energy_system_type', 'Тип энергосистемы');
        initializeSelect2IfAvailable('#union_energy_system', 'ОЭС');
        initializeSelect2IfAvailable('#regional_energy_system', 'Региональная энергосистема');
        initializeSelect2IfAvailable('#federal_district', 'Федеральный округ');
        initializeSelect2IfAvailable('#regional_district', 'Субъект РФ');

        // Если Select2 нет — делаем "сворачиваемые" dropdown-поля
        if (!hasSelect2) {
            ensureDropdownMultiSelect('#energy_system_type', 'Тип энергосистемы');
            ensureDropdownMultiSelect('#union_energy_system', 'ОЭС');
            ensureDropdownMultiSelect('#regional_energy_system', 'Региональная энергосистема');
            ensureDropdownMultiSelect('#federal_district', 'Федеральный округ');
            ensureDropdownMultiSelect('#regional_district', 'Субъект РФ');
        }
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

    // Если разрешен ровно один id — возвращаем его, иначе null.
    // Служебный id=0 ("не указано") автоподставлять не будем.
    function getSingleAllowedId(allowedIds) {
        if (!allowedIds || !(allowedIds instanceof Set)) return null;
        if (allowedIds.size !== 1) return null;
        const only = [...allowedIds][0];
        const num = Number(only);
        if (!Number.isFinite(num)) return null;
        if (num === 0) return null;
        return num;
    }

    function getSelectValues(selector) {
        const el = document.querySelector(selector);
        if (!el) return [];
        return Array.from(el.selectedOptions).map(o => Number(o.value)).filter(v => Number.isFinite(v));
    }

    function setSelectValues(selector, values) {
        const el = document.querySelector(selector);
        if (!el) return;
        const set = new Set((values || []).map(String));
        Array.from(el.options).forEach(opt => {
            opt.selected = set.has(String(opt.value));
        });
        if (hasSelect2) {
            window.$(selector).trigger('change.select2');
        } else {
            refreshDropdownMultiSelect(selector);
        }
    }

    // Функция для обновления опций в select (работает и без select2)
    function updateSelectOptions(selector, allItems, allowedIds, prevSelected, skipTrigger = false) {
        const el = document.querySelector(selector);
        if (!el) return;

        const prevSelectedSet = new Set((prevSelected || []).map(String));
        const newSelected = [];

        // Сохраняем placeholder-пустой option (как было) — для allowClear
        const frag = document.createDocumentFragment();
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        frag.appendChild(emptyOpt);

        // UX: "не указано" всегда должно быть первым пунктом.
        // Порядок, который приходит с бэка, может отличаться (например, для ОЭС).
        const sortedItems = [...(allItems || [])].sort((a, b) => {
            const an = String(a?.name ?? '').trim().toLowerCase();
            const bn = String(b?.name ?? '').trim().toLowerCase();
            const aIsNA = an === 'не указано';
            const bIsNA = bn === 'не указано';
            if (aIsNA && !bIsNA) return -1;
            if (!aIsNA && bIsNA) return 1;
            return an.localeCompare(bn, 'ru', { sensitivity: 'base' });
        });

        sortedItems.forEach(item => {
            const itemId = Number(item.id);
            const isAllowed = allowedIds === null || allowedIds.has(itemId);
            const wasSelected = prevSelectedSet.has(String(itemId));
            if (!isAllowed) return;

            const opt = document.createElement('option');
            opt.value = String(itemId);
            opt.textContent = item.name;
            opt.selected = wasSelected;
            frag.appendChild(opt);
            if (wasSelected) newSelected.push(String(itemId));
        });

        // Полная замена options
        el.innerHTML = '';
        el.appendChild(frag);

        // Восстанавливаем выбранные
        setSelectValues(selector, newSelected);
        // если select "завёрнут" в dropdown — пересобираем меню
        refreshDropdownMultiSelect(selector);

        if (!skipTrigger) {
            // Для нативного селекта просто диспатчим change, для Select2 — обновили выше
            if (!hasSelect2) {
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    // Функция для обновления всех фильтров на основе текущих выборов
    function updateAllFilters() {
        // Предотвращаем рекурсию
        if (isUpdating) return;
        isUpdating = true;

        try {
            const currentEst = getSelectValues('#energy_system_type');
            const currentUes = getSelectValues('#union_energy_system');
            const currentRes = getSelectValues('#regional_energy_system');
            const currentFd = getSelectValues('#federal_district');
            const currentRd = getSelectValues('#regional_district');

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
    document.getElementById('energy_system_type')?.addEventListener('change', () => updateAllFilters());
    document.getElementById('union_energy_system')?.addEventListener('change', () => updateAllFilters());
    document.getElementById('regional_energy_system')?.addEventListener('change', function() {
        // "Как в Excel": выбранная РЭС однозначно задаёт ФО, ОЭС и тип энергосистемы.
        // Если выбрана ровно одна РЭС — синхронизируем связанные поля автоматически.
        if (isUpdating) return;
        const currentRes = getSelectValues('#regional_energy_system');
        if (currentRes.length === 1) {
            const resId = currentRes[0];

            // ФО (РЭС -> [ФО])
            const mappedFd = resToFd[String(resId)] || resToFd[Number(resId)] || [];
            const fdArr = Array.isArray(mappedFd) ? mappedFd : [mappedFd];
            const fdUnique = [...new Set(fdArr.filter(x => x !== null && x !== undefined).map(Number))];

            // ОЭС (РЭС -> ОЭС) one-to-one
            const mappedUes = resToUesOne[String(resId)] || resToUesOne[Number(resId)];
            const uesUnique = (mappedUes !== null && mappedUes !== undefined) ? [Number(mappedUes)] : [];

            // Тип ЭС (РЭС -> ТипЭС) one-to-one
            const mappedEst = resToEst[String(resId)] || resToEst[Number(resId)];
            const estUnique = (mappedEst !== null && mappedEst !== undefined) ? [Number(mappedEst)] : [];

            // Выставляем связанные поля одним проходом, без каскадных событий.
            let didSync = false;
            isUpdating = true;
            try {
                if (estUnique.length === 1) {
                    const currentEst = getSelectValues('#energy_system_type');
                    if (currentEst.length !== 1 || currentEst[0] !== estUnique[0]) {
                        setSelectValues('#energy_system_type', [String(estUnique[0])]);
                        didSync = true;
                    }
                }

                if (uesUnique.length === 1) {
                    const currentUes = getSelectValues('#union_energy_system');
                    if (currentUes.length !== 1 || currentUes[0] !== uesUnique[0]) {
                        setSelectValues('#union_energy_system', [String(uesUnique[0])]);
                        didSync = true;
                    }
                }

                if (fdUnique.length === 1) {
                    const currentFd = getSelectValues('#federal_district');
                    if (currentFd.length !== 1 || currentFd[0] !== fdUnique[0]) {
                        setSelectValues('#federal_district', [String(fdUnique[0])]);
                        didSync = true;
                    }
                }
            } finally {
                isUpdating = false;
            }

            if (didSync) {
                updateAllFilters();
                return;
            }
        }

        updateAllFilters();
    });

    document.getElementById('federal_district')?.addEventListener('change', () => updateAllFilters());
    document.getElementById('regional_district')?.addEventListener('change', () => updateAllFilters());

    // Инициализация при загрузке страницы
    if (selectedEst.length > 0) setSelectValues('#energy_system_type', selectedEst.map(String));
    if (selectedUes.length > 0) setSelectValues('#union_energy_system', selectedUes.map(String));
    if (selectedRes.length > 0) setSelectValues('#regional_energy_system', selectedRes.map(String));
    if (selectedFd.length > 0) setSelectValues('#federal_district', selectedFd.map(String));
    if (selectedRd.length > 0) setSelectValues('#regional_district', selectedRd.map(String));

    // Вызываем updateAllFilters для первоначальной настройки
    setTimeout(() => {
        updateAllFilters();
    }, 200);
}
