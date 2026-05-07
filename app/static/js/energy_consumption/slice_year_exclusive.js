/**
 * В списке «Год» скрывает уже занятые на других строках календарные года.
 */
(function () {
    "use strict";

    function initSliceYearExclusive() {
        var container = document.getElementById("demand-rows");
        var jsonEl = document.getElementById("power-demand-year-options-json");
        if (!container || !jsonEl) {
            return;
        }
        var YEARS;
        try {
            YEARS = JSON.parse(jsonEl.textContent || "[]");
        } catch (e) {
            YEARS = [];
        }

        function getSelects() {
            return Array.prototype.slice.call(container.querySelectorAll('select[name="slice_year[]"]'));
        }

        function rebuildAll() {
            var selects = getSelects();
            var snapshot = selects.map(function (s) {
                return s.value;
            });

            selects.forEach(function (sel, idx) {
                var taken = new Set();
                snapshot.forEach(function (v, j) {
                    if (j !== idx && v !== "" && v != null) {
                        taken.add(String(v));
                    }
                });

                var current = snapshot[idx];

                var frag = document.createDocumentFragment();

                var blank = document.createElement("option");
                blank.value = "";
                blank.textContent = "—";
                if (current === "") {
                    blank.selected = true;
                }
                frag.appendChild(blank);

                YEARS.forEach(function (yn) {
                    var ys = String(yn);
                    if (current === ys || !taken.has(ys)) {
                        var oy = document.createElement("option");
                        oy.value = ys;
                        oy.textContent = ys;
                        if (current === ys) {
                            oy.selected = true;
                        }
                        frag.appendChild(oy);
                    }
                });

                sel.innerHTML = "";
                sel.appendChild(frag);
                if (sel.options.length && sel.selectedIndex < 0) {
                    sel.options[0].selected = true;
                }
            });
        }

        getSelects().forEach(function (sel) {
            sel.addEventListener("change", rebuildAll);
        });

        rebuildAll();
    }

    window.initSliceYearExclusive = initSliceYearExclusive;
})();
