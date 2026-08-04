/**
 * Блокирует отправку формы параметров нагрузки, если не заполнены обязательные поля
 * (согласовано с validate_demand_post_complete на сервере).
 */
(function () {
    "use strict";

    function fieldNonempty(el) {
        if (!el) return false;
        return String(el.value || "").trim() !== "";
    }

    function parseDecimal(val) {
        var s = String(val == null ? "" : val)
            .trim()
            .replace(",", ".");
        if (!s) return null;
        var n = Number(s);
        return Number.isFinite(n) ? n : null;
    }

    function expandTwoDigitYear(yy) {
        return yy <= 68 ? 2000 + yy : 1900 + yy;
    }

    function normalizePeakDatetimeText(val) {
        var text = String(val == null ? "" : val)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ");
        var lines = text.split(/\r?\n/);
        var parts = [];
        for (var li = 0; li < lines.length; li++) {
            var t = lines[li].trim();
            if (t) {
                parts.push(t);
            }
        }
        var s = parts.length ? parts.join(" ") : text.trim();
        s = s.replace(/\s+/g, " ").trim();
        var qmarks = "\"'«»“”";
        while (
            s.length >= 2 &&
            s.charAt(0) === s.charAt(s.length - 1) &&
            qmarks.indexOf(s.charAt(0)) >= 0
        ) {
            s = s.slice(1, -1).trim();
        }
        s = s.replace(/^["'«»“”]+|["'«»“”]+$/g, "").trim();
        // «10.01.23 18-00» → время через двоеточие
        s = s.replace(
            /((?:\d{1,2}\.){2}\d{2,4})\s+(\d{1,2})-(\d{2})(?::(\d{2}))?/,
            function (_m, datePart, hh, mm, ss) {
                var out =
                    datePart +
                    " " +
                    String(parseInt(hh, 10)).padStart(2, "0") +
                    ":" +
                    mm;
                if (ss) {
                    out += ":" + ss;
                }
                return out;
            }
        );
        // Двузначный год и выравнивание ДД.ММ
        s = s.replace(/\b(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})\b/, function (_m, d, mo, yRaw) {
            var y = parseInt(yRaw, 10);
            if (yRaw.length === 2) {
                y = expandTwoDigitYear(y);
            }
            return (
                String(parseInt(d, 10)).padStart(2, "0") +
                "." +
                String(parseInt(mo, 10)).padStart(2, "0") +
                "." +
                String(y).padStart(4, "0")
            );
        });
        s = s.replace(
            /((?:\d{2}\.){2}\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/,
            function (_m, datePart, hh, mm, ss) {
                var out =
                    datePart +
                    " " +
                    String(parseInt(hh, 10)).padStart(2, "0") +
                    ":" +
                    mm;
                if (ss) {
                    out += ":" + ss;
                }
                return out;
            }
        );
        return s;
    }

    function parsePeakDatetimeParts(s) {
        if (!s) return null;
        if (/^\d{4}$/.test(s)) {
            var yy = parseInt(s, 10);
            if (yy >= 1000 && yy <= 9999) {
                return new Date(yy, 0, 1, 0, 0, 0, 0);
            }
            return null;
        }
        var m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})(?::(\d{2}))?$/.exec(s);
        if (!m) {
            m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(s);
            if (!m) {
                var dateM = /(\d{2}\.\d{2}\.\d{4})/.exec(s);
                if (!dateM) return null;
                var timeM = /(\d{1,2}:\d{2}(?::\d{2})?)/.exec(s);
                if (timeM) {
                    var timePart = timeM[1];
                    if (/^\d:\d{2}(?::\d{2})?$/.test(timePart)) {
                        timePart = "0" + timePart;
                    }
                    s = dateM[1] + " " + timePart;
                    m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})(?::(\d{2}))?$/.exec(s);
                } else {
                    m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(dateM[1]);
                    if (!m) return null;
                    m = [m[0], m[1], m[2], m[3], "0", "0", "0"];
                }
            } else {
                m = [m[0], m[1], m[2], m[3], "0", "0", "0"];
            }
        }
        if (!m) return null;
        var d = parseInt(m[1], 10);
        var mo = parseInt(m[2], 10) - 1;
        var y = parseInt(m[3], 10);
        var h = parseInt(m[4], 10);
        var mi = parseInt(m[5], 10);
        var dt = new Date(y, mo, d, h, mi, 0, 0);
        if (
            dt.getFullYear() !== y ||
            dt.getMonth() !== mo ||
            dt.getDate() !== d ||
            dt.getHours() !== h ||
            dt.getMinutes() !== mi
        ) {
            return null;
        }
        return dt;
    }

    function parsePeakDatetime(val) {
        return parsePeakDatetimeParts(normalizePeakDatetimeText(val));
    }

    function parseSliceYear(raw) {
        var s = String(raw || "").trim();
        if (s === "hist") return { ok: true, isHist: true, year: null };
        if (!s) return { ok: false, isHist: false, year: null };
        if (/^\d+$/.test(s)) return { ok: true, isHist: false, year: parseInt(s, 10) };
        return { ok: false, isHist: false, year: null };
    }

    /**
     * @param {HTMLFormElement} form
     * @returns {string[]}
     */
    function collectIssues(form) {
        var requireOE = form.getAttribute("data-require-oe") === "1";
        var requireEZ = form.getAttribute("data-require-ez") === "1";
        var tbody = form.querySelector("#demand-rows");
        if (!tbody) return [];

        var issues = [];
        var trs = tbody.querySelectorAll("tr");

        trs.forEach(function (tr, i) {
            var sliceSel = tr.querySelector('select[name="slice_year[]"]');
            var pMax = tr.querySelector('input[name="p_max[]"]');
            var dtIn = tr.querySelector('[name="dt[]"]');
            var tnvIn = tr.querySelector('input[name="tnv[]"]');
            var oesIn = tr.querySelector('input[name="oes[]"]');
            var eesIn = tr.querySelector('input[name="ees[]"]');
            var ezIn = tr.querySelector('input[name="ez[]"]');
            var ridIn = tr.querySelector('input[name="row_id[]"]');
            var delCb = tr.querySelector('input[type="checkbox"][name="del[]"]');

            if (!sliceSel || !pMax || !dtIn || !tnvIn || !ridIn) return;

            var rid = String(ridIn.value || "").trim();
            if (delCb && delCb.checked && rid) return;

            var sl = String(sliceSel.value || "").trim();
            var pmax = String(pMax.value || "").trim();
            var dtv = String(dtIn.value || "").trim();
            var tnvv = String(tnvIn.value || "").trim();
            var oesv = oesIn ? String(oesIn.value || "").trim() : "";
            var eesv = eesIn ? String(eesIn.value || "").trim() : "";
            var ezv = ezIn ? String(ezIn.value || "").trim() : "";

            var rowLabel = "строка таблицы №" + (i + 1);

            if (!rid) {
                var coreEmpty = !sl && !pmax && !dtv && !tnvv;
                var oeEmpty = !oesv;
                var eeEmpty = !eesv;
                var ezEmpty = !ezv;
                if (
                    coreEmpty &&
                    (!requireOE || (oeEmpty && eeEmpty)) &&
                    (!requireEZ || ezEmpty)
                ) {
                    return;
                }
                rowLabel = "новая строка";
            }

            var sy = parseSliceYear(sl);
            if (!sy.ok || (!sy.isHist && sy.year == null)) {
                issues.push(rowLabel + ": не выбран срез или год.");
                return;
            }

            if (!fieldNonempty(pMax)) {
                issues.push(rowLabel + ': не заполнено «Максимальное потребление, МВт».');
            } else if (parseDecimal(pMax.value) == null) {
                issues.push(
                    rowLabel + ': некорректное число в «Максимальное потребление, МВт».'
                );
            }

            if (!fieldNonempty(dtIn)) {
                issues.push(rowLabel + ': не заполнено «Дата и время».');
            } else {
                var pdt = parsePeakDatetime(dtIn.value);
                if (!pdt) {
                    issues.push(
                        rowLabel +
                            ': «Дата и время»: укажите дату в формате ДД.ММ.ГГГГ ЧЧ:ММ или только год (ГГГГ).'
                    );
                } else if (!sy.isHist && sy.year != null && pdt.getFullYear() !== sy.year) {
                    issues.push(
                        rowLabel +
                            ': год в «Дата и время» (' +
                            pdt.getFullYear() +
                            ') должен совпадать с годом в столбце «Срез / год» (' +
                            sy.year +
                            ').'
                    );
                }
            }

            if (!fieldNonempty(tnvIn)) {
                issues.push(rowLabel + ': не заполнено «Среднесуточная ТНВ».');
            } else if (parseDecimal(tnvIn.value) == null) {
                issues.push(rowLabel + ': некорректное число в «Среднесуточная ТНВ».');
            }

            if (requireOE) {
                if (!fieldNonempty(oesIn)) {
                    issues.push(rowLabel + ': не заполнено «Совмещённый на ОЭС».');
                } else if (parseDecimal(oesIn.value) == null) {
                    issues.push(rowLabel + ': некорректное число в «Совмещённый на ОЭС».');
                }
                if (!fieldNonempty(eesIn)) {
                    issues.push(rowLabel + ': не заполнено «Совмещённый на ЕЭС».');
                } else if (parseDecimal(eesIn.value) == null) {
                    issues.push(rowLabel + ': некорректное число в «Совмещённый на ЕЭС».');
                }
            }

            if (requireEZ) {
                if (!fieldNonempty(ezIn)) {
                    issues.push(rowLabel + ': не заполнено «Совмещённый на энергозону, МВт».');
                } else if (parseDecimal(ezIn.value) == null) {
                    issues.push(
                        rowLabel + ': некорректное число в «Совмещённый на энергозону, МВт».'
                    );
                }
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
