(function () {
    "use strict";

    // Delegation also covers info icons inserted by live table rendering.
    new bootstrap.Tooltip(document.body, {
        selector: ':is(.bi-info-circle, .bi-info-square):is([title], [data-bs-original-title]):not([data-bs-toggle])',
        container: "body",
        trigger: "hover focus"
    });
})();
