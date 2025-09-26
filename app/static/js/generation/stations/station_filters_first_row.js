
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
            $(selector).select2({
                placeholder: placeholder,
                allowClear: true,
                width: '100%',
                closeOnSelect: false,
                minimumResultsForSearch: Infinity
            });
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

    const selectedUnionValues = (window.union_energy_system_filter_json ?? []);
    const selectedFederalValues = (window.federal_district_filter_json ?? []);
    const regionalEnergySystemsMapping = (window.regional_energy_system_mapping_json ?? {});
    const allRegionalSystems = (window.regional_energy_system_list_json ?? []);
    const regionalDistrictsMapping = (window.regional_district_mapping_json ?? {});
    const allRegionalDistricts = (window.regional_district_list_json ?? []);

    function updateRegionalEnergySystemOptions(selectedUnionIDs) {
        let options = '<option></option>';
        const prevSelected = ($('#regional_energy_system').val() || []).map(String);
        const newSelected = [];

        // Если ОЭС не выбраны — показываем все РЭС
        if (!selectedUnionIDs || selectedUnionIDs.length === 0) {
            allRegionalSystems.forEach(system => {
                const selected = prevSelected.includes(String(system.id));
                // ВНИМАНИЕ: имя поля — name или name_full? Поставьте то, что реально есть в DTO
                options += `<option value="${system.id}" ${selected ? "selected" : ""}>${system.name || system.name_full}</option>`;
                if (selected) newSelected.push(String(system.id));
            });
            $('#regional_energy_system').html(options).val(newSelected).trigger('change');
            return;
        }

        // Иначе — только те, что входят в выбранные ОЭС
        const allowed = new Set();
        selectedUnionIDs.forEach(unionID => {
            const ids = regionalEnergySystemsMapping[unionID] || regionalEnergySystemsMapping[String(unionID)] || [];
            ids.forEach(id => allowed.add(Number(id))); // на всякий случай приводим к числу
        });

        allRegionalSystems.forEach(system => {
            if (allowed.has(Number(system.id))) {
                const selected = prevSelected.includes(String(system.id));
                options += `<option value="${system.id}" ${selected ? "selected" : ""}>${system.name || system.name_full}</option>`;
                if (selected) newSelected.push(String(system.id));
            }
        });

        $('#regional_energy_system').html(options).val(newSelected).trigger('change');
    }

    function updateRegionalDistrictOptions(selectedFederalIDs) {
        let options = '<option></option>';
        const prevSelected = ($('#regional_district').val() || []).map(String);
        const newSelected = [];

        // Если ФО не выбраны — показываем все субъекты
        if (!selectedFederalIDs || selectedFederalIDs.length === 0) {
            allRegionalDistricts.forEach(district => {
                const selected = prevSelected.includes(String(district.id));
                options += `<option value="${district.id}" ${selected ? "selected" : ""}>${district.name}</option>`;
                if (selected) newSelected.push(String(district.id));
            });
            $('#regional_district').html(options).val(newSelected).trigger('change');
            return;
        }

        // Иначе — только те, что входят в выбранные ФО
        const allowed = new Set();
        selectedFederalIDs.forEach(fdID => {
            const ids = regionalDistrictsMapping[fdID] || regionalDistrictsMapping[String(fdID)] || [];
            ids.forEach(id => allowed.add(Number(id)));
        });

        allRegionalDistricts.forEach(district => {
            if (allowed.has(Number(district.id))) {
                const selected = prevSelected.includes(String(district.id));
                options += `<option value="${district.id}" ${selected ? "selected" : ""}>${district.name}</option>`;
                if (selected) newSelected.push(String(district.id));
            }
        });

        $('#regional_district').html(options).val(newSelected).trigger('change');
    }

    $('#union_energy_system').on('change', function () {
        updateRegionalEnergySystemOptions($(this).val() || []);
    });

    $('#federal_district').on('change', function () {
        updateRegionalDistrictOptions($(this).val() || []);
    });

    $('#union_energy_system').on('select2:clear', function () {
        $('#regional_energy_system').val([]).empty().append('<option></option>').trigger('change.select2');
    });

    $('#federal_district').on('select2:clear', function () {
        $('#regional_district').val([]).empty().append('<option></option>').trigger('change.select2');
    });

    if ((selectedUnionValues ?? []).length === 0) {
        updateRegionalEnergySystemOptions([]);
    } else {
        updateRegionalEnergySystemOptions((selectedUnionValues || []).map(String));
        $('#union_energy_system').val((selectedUnionValues || []).map(String)).trigger('change');
    }

    if ((selectedFederalValues ?? []).length === 0) {
        updateRegionalDistrictOptions([]);
    } else {
        updateRegionalDistrictOptions((selectedFederalValues || []).map(String));
        $('#federal_district').val((selectedFederalValues || []).map(String)).trigger('change');
    }
    console.log('RES total:', window.regional_energy_system_list_json?.length, window.regional_energy_system_list_json?.[0]);
    console.log('UES->RES keys:', Object.keys(window.regional_energy_system_mapping_json || {}));
    console.log('RD total:', window.regional_district_list_json?.length, window.regional_district_list_json?.[0]);
    console.log('FD->RD keys:', Object.keys(window.regional_district_mapping_json || {}));

}

    // Скрипт для автоматической подстановки данных по наименованию субъекта
    document.addEventListener("DOMContentLoaded", function() {
        document.getElementById("id_regional_district").addEventListener("change", function() {
            let district_id = this.value;
            
            // Проверка, выбран ли субъект РФ
            if (!district_id) return;
    
            fetch(`/generation/stations/get_energy_system_data/${district_id}`)
                .then(response => response.json())
                .then(data => {
                    console.log("Данные с сервера:", data); // Отладка
    
                    // Проверяем, существуют ли элементы перед изменением
                    if (document.getElementById("federal_district")) {
                        document.getElementById("federal_district").innerText = data.federal_district || "Нет данных";
                    }
                    if (document.getElementById("union_energy_system")) {
                        document.getElementById("union_energy_system").innerText = data.union_energy_system || "Нет данных";
                    }
                    if (document.getElementById("energy_system_type")) {
                        document.getElementById("energy_system_type").innerText = data.energy_system_type || "Нет данных";
                    }
                    if (document.getElementById("regional_energy_system")) {
                        document.getElementById("regional_energy_system").innerText = data.regional_energy_system || "Нет данных";
                    }
                })
                .catch(error => console.error("Ошибка загрузки данных:", error));
        });
    });