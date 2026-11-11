(function () {
    "use strict";

    var config = JSON.parse(document.getElementById("user-settings-reset-config").textContent);
    if (!config.token) return;

    var exactKeys = new Set([
        "start_year", "end_year", "rounding_digits", "toggleP_Ogr", "toggleP_Rasp",
        "externalCodeCheck.hiddenVersions", "ecology.calculation_summary.territories",
        "egCardShowEmptyParamRows",
        "fuel_param_columns_visible", "fuelParamsDetailPanelsVisible",
        "arm_gs_fuel_batch_recalc_filters_v1"
    ]);
    var prefixes = [
        "pdEcSummary", "pdPdSummary", "powerDemandSummary", "powerDemandCoeff",
        "pdCoeffMixinRowUi", "energyConsumptionSummaryMaxYearSegVisible",
        "eeGenerationVerificationMode", "eeGenerationTotalsVerificationMode",
        "fuelParams_", "fuelParamsPageShowEmptyRows", "fuelEditShowEmptyRows",
        "naturalFuel_", "specificFuelCost_", "specificFuelPrice_", "fuelTotals_",
        "armGsScrollRestore_", "armGs.ltEiRowGroupState:"
    ];
    var marker = "armGs.settingsReset:" + config.userId;

    function clearDisplaySettings(storage) {
        var keys = [];
        for (var i = 0; i < storage.length; i++) {
            var key = storage.key(i);
            if (exactKeys.has(key) || prefixes.some(function (prefix) { return key.startsWith(prefix); })) {
                keys.push(key);
            }
        }
        keys.forEach(function (key) { storage.removeItem(key); });
        storage.setItem(marker, config.token);
    }

    // localStorage общий для вкладок, sessionStorage нужно сбрасывать в каждой вкладке.
    try {
        if (localStorage.getItem(marker) !== config.token) clearDisplaySettings(localStorage);
        if (sessionStorage.getItem(marker) !== config.token) clearDisplaySettings(sessionStorage);
    } catch (error) {
        console.warn("Не удалось сбросить настройки отображения в хранилище браузера.", error);
    }
}());
