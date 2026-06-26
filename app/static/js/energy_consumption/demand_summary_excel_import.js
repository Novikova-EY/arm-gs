// Импорт сводки потребления из Excel: фоновое задание + опрос статуса (долгий проход по всем версиям БД).
(function () {
    "use strict";

    function initPdEcSummaryExcelImport() {
        var wrap = document.getElementById("pdEcFoEzSummaryImportWrap");
        if (!wrap) {
            return;
        }
        var inp = document.getElementById("pdEcFoEzSummaryImportFile");
        var btn = document.getElementById("pdEcFoEzSummaryImportBtn");
        var uploadUrl = wrap.dataset.importUrl || "";
        var statusUrlTemplate = wrap.dataset.importStatusUrl || "";
        var csrf = wrap.dataset.csrfToken || "";
        if (!inp || !btn || !uploadUrl || !statusUrlTemplate) {
            return;
        }

        function statusUrlForJob(jobId) {
            return statusUrlTemplate.replace("JOB_ID", encodeURIComponent(jobId));
        }

        function setBusy(isBusy, label) {
            if (isBusy) {
                if (!btn.dataset.prevHtml) {
                    btn.dataset.prevHtml = btn.innerHTML;
                }
                btn.disabled = true;
                btn.innerHTML =
                    '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' +
                    (label || "Импорт…");
                return;
            }
            btn.disabled = false;
            btn.innerHTML = btn.dataset.prevHtml || btn.innerHTML;
            delete btn.dataset.prevHtml;
        }

        function pollImportStatus(jobId, attempt) {
            var maxAttempts = 900;
            var delayMs = 2000;
            if (attempt >= maxAttempts) {
                setBusy(false);
                inp.value = "";
                alert(
                    "Импорт всё ещё выполняется на сервере, но браузер прекратил ожидание ответа.\n" +
                        "Проверьте журнал сервера и обновите страницу через несколько минут."
                );
                return;
            }
            fetch(statusUrlForJob(jobId), {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return null; }).then(function (j) {
                        return { resp: resp, data: j };
                    });
                })
                .then(function (pack) {
                    var data = pack.data;
                    if (!pack.resp.ok || !data) {
                        throw new Error((data && data.error) ? data.error : "Не удалось получить статус импорта.");
                    }
                    if (data.status === "running") {
                        var done = data.versions_done || 0;
                        var total = data.versions_total || 0;
                        var label = "Импорт…";
                        if (total > 0) {
                            label = "Импорт… " + done + "/" + total;
                        }
                        setBusy(true, label);
                        window.setTimeout(function () {
                            pollImportStatus(jobId, attempt + 1);
                        }, delayMs);
                        return;
                    }
                    setBusy(false);
                    inp.value = "";
                    if (data.status === "error" || !data.ok) {
                        alert(data.error || "Не удалось выполнить импорт.");
                        return;
                    }
                    var msg = data.message || "Готово.";
                    var hints = data.hints || [];
                    if (hints.length) {
                        msg += "\n\n" + hints.join("\n\n");
                    }
                    alert(msg);
                    window.location.reload();
                })
                .catch(function (err) {
                    setBusy(false);
                    inp.value = "";
                    var suffix = err && err.message ? "\nТехника: " + err.message + "." : "";
                    alert(
                        "Не удалось получить статус импорта с сервера." +
                            suffix +
                            "\nЕсли импорт только что запущен, подождите и обновите страницу."
                    );
                });
        }

        btn.addEventListener("click", function () {
            inp.click();
        });

        inp.addEventListener("change", function () {
            if (!inp.files || inp.files.length === 0) {
                return;
            }
            var fd = new FormData();
            fd.append("file", inp.files[0]);
            fd.append("csrf_token", csrf);
            setBusy(true, "Загрузка…");
            fetch(uploadUrl, {
                method: "POST",
                body: fd,
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (resp) {
                    return resp.json().catch(function () { return null; }).then(function (j) {
                        return { resp: resp, data: j };
                    });
                })
                .then(function (pack) {
                    var data = pack.data;
                    if (!pack.resp.ok || !data || !data.ok) {
                        throw new Error((data && data.error) ? data.error : "Не удалось запустить импорт.");
                    }
                    if (!data.job_id) {
                        throw new Error("Сервер не вернул идентификатор задания импорта.");
                    }
                    pollImportStatus(data.job_id, 0);
                })
                .catch(function (err) {
                    setBusy(false);
                    inp.value = "";
                    var suffix = err && err.message ? "\nТехника: " + err.message + "." : "";
                    alert("Не удалось запустить импорт." + suffix);
                });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPdEcSummaryExcelImport);
    } else {
        initPdEcSummaryExcelImport();
    }
})();
