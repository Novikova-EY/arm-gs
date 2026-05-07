/**
 * Проверка формы параметров потребления перед POST (согласовано с validate_energy_consumption_post_complete).
 */
(function () {
    "use strict";

    function fieldNonempty(el) {
        if (!el) return false;
        return String(el.value || "").trim() !== "";
    }

    function parseDecimal(val) {
        var s = String(val == null ? "")
            .trim()
            .replace(",", ".");
        if (!s) return null;
        var n = Number(s);
        return Number.isFinite(n) ? n : null;
    }

    function parseYearSlice(raw) {
        var s = String(raw || "").trim();
        if (s === "" || s === "hist") return null;
        if (/^\d+$/.test(s)) return parseInt(s, 10);
        return null;
    }

    /**
     * @param {HTMLFormElement} form
     * @returns {string[]}
     */
    function collectIssues(form) {
        var tbody = form.querySelector("#demand-rows");
        if (!tbody) return [];

        var issues = [];
        var trs = tbody.querySelectorAll("tr");

        trs.forEach(function (tr, i) {
            var sliceSel = tr.querySelector('select[name="slice_year[]"]');
            var ecMln = tr.querySelector('input[name="ec_mln[]"]');
            var ecSipr = tr.querySelector('input[name="ec_sipr[]"]');
            var noteIn = tr.querySelector('textarea[name="note[]"]');
            var ridIn = tr.querySelector('input[name="row_id[]"]');
            var delCb = tr.querySelector('input[type="checkbox"][name="del[]"]');

            if (!sliceSel || !ecMln || !ecSipr || !ridIn) return;

            var rid = String(ridIn.value || "").trim();
            if (delCb && delCb.checked && rid) return;

            var sl = String(sliceSel.value || "").trim();
            var mlnv = String(ecMln.value || "").trim();
            var siprv = String(ecSipr.value || "").trim();
            var notev = noteIn ? String(noteIn.value || "").trim() : "";

            var rowLabel = "строка таблицы №" + (i + 1);

            if (!rid) {
                var allEmpty = !sl && !mlnv && !siprv && !notev;
                if (allEmpty) return;
                rowLabel = "новая строка";
            }

            if (sl === "hist") {
                issues.push(rowLabel + ": выберите календарный год (исторический максимум не используется).");
                return;
            }

            var y = parseYearSlice(sl);
            if (y == null) {
                issues.push(rowLabel + ": не выбран год.");
                return;
            }

            if (fieldNonempty(ecMln) && parseDecimal(ecMln.value) == null) {
                issues.push(
                    rowLabel + ': некорректное число в «Потребление электрической энергии, млн кВт·ч».'
                );
            }
            if (fieldNonempty(ecSipr) && parseDecimal(ecSipr.value) == null) {
                issues.push(rowLabel + ': некорректное число в «Потребление (СиПР), млн кВт·ч».');
            }
        });

        return issues;
    }

    function initDemandSaveValidate(form) {
        if (!form || form.dataset.demandValidateBound === "1") return;
        form.dataset.demandValidateBound = "1";

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var issues = collectIssues(form);
            if (issues.length) {
                var msg =
                    "Нельзя сохранить: не все обязательные поля заполнены или формат неверный.\n\n" +
                    issues.slice(0, 15).join("\n");
                if (issues.length > 15) msg += "\n…";
                alert(msg);
                return;
            }
            form.submit();
        });
    }

    window.initDemandSaveValidate = initDemandSaveValidate;
})();
