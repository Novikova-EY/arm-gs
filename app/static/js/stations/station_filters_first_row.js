
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

    const selectedUnionValues = JSON.parse(union_energy_system_filter_json || '[]');
    const selectedFederalValues = JSON.parse(federal_district_filter_json || '[]');
    const regionalEnergySystemsMapping = JSON.parse(regional_energy_system_mapping_json || '{}');
    const allRegionalSystems = JSON.parse(regional_energy_system_list_json || '[]');
    const regionalDistrictsMapping = JSON.parse(regional_district_mapping_json || '{}');
    const allRegionalDistricts = JSON.parse(regional_district_list_json || '[]');

    function updateRegionalEnergySystemOptions(selectedUnionIDs) {
        let options = '<option></option>';
        const allowed = new Set();

        selectedUnionIDs.forEach(unionID => {
            (regionalEnergySystemsMapping[unionID] || []).forEach(id => allowed.add(id));
        });

        const prevSelected = $('#regional_energy_system').val() || [];
        const newSelected = [];

        allRegionalSystems.forEach(system => {
            if (allowed.has(system.id)) {
                const selected = prevSelected.includes(String(system.id));
                options += `<option value="${system.id}" ${selected ? "selected" : ""}>${system.name}</option>`;
                if (selected) newSelected.push(String(system.id));
            }
        });

        $('#regional_energy_system').html(options).val(newSelected).trigger('change.select2');
    }

    function updateRegionalDistrictOptions(selectedFederalIDs) {
        let options = '<option></option>';
        const allowed = new Set();

        selectedFederalIDs.forEach(fdID => {
            (regionalDistrictsMapping[fdID] || []).forEach(id => allowed.add(id));
        });

        const prevSelected = $('#regional_district').val() || [];
        const newSelected = [];

        allRegionalDistricts.forEach(district => {
            if (allowed.has(district.id)) {
                const selected = prevSelected.includes(String(district.id));
                options += `<option value="${district.id}" ${selected ? "selected" : ""}>${district.name}</option>`;
                if (selected) newSelected.push(String(district.id));
            }
        });

        $('#regional_district').html(options).val(newSelected).trigger('change.select2');
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

    if (selectedUnionValues.length > 0) {
        updateRegionalEnergySystemOptions(selectedUnionValues);
        $('#union_energy_system').val(selectedUnionValues).trigger('change.select2');
    }

    if (selectedFederalValues.length > 0) {
        updateRegionalDistrictOptions(selectedFederalValues);
        $('#federal_district').val(selectedFederalValues).trigger('change.select2');
    }
}
