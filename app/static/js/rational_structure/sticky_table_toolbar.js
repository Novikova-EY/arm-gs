(function () {
    "use strict";

    document.querySelectorAll(".rs-sticky-toolbar-page").forEach(function (page) {
        const toolbar = page.querySelector(".rs-table-toolbar");
        if (!toolbar) return;

        function updateHeight() {
            page.style.setProperty("--rs-table-toolbar-height", toolbar.getBoundingClientRect().height + "px");
        }

        new ResizeObserver(updateHeight).observe(toolbar);
        updateHeight();
    });
})();
