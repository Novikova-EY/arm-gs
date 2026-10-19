/**
 * Выгрузка Excel без перезагрузки страницы.
 *
 * Кнопка «Экспорт в Excel» делает GET-запрос по адресу выгрузки через fetch:
 * страница не уходит в навигацию (иначе при скачивании файла на ней навсегда
 * остаётся прелоадер и она становится неактивной), а полученный файл скачивается
 * по временной ссылке. Пока идёт выгрузка, спиннер показывается в самой кнопке.
 *
 * Используется на /energy_balance/ee_transfers/ и /ecology/gis_tek/{pg,pollutants}/.
 */
(function () {
    'use strict';

    function parseFilename(contentDisposition, fallback) {
        if (!contentDisposition) {
            return fallback;
        }

        var utf8Match = /filename\*=UTF-8''([^;\n]+)/i.exec(contentDisposition);
        if (utf8Match && utf8Match[1]) {
            try {
                return decodeURIComponent(utf8Match[1].trim());
            } catch (e) {
                return utf8Match[1].trim();
            }
        }

        var quotedMatch = /filename="([^"]+)"/i.exec(contentDisposition);
        if (quotedMatch && quotedMatch[1]) {
            return quotedMatch[1].trim();
        }

        var bareMatch = /filename=([^;\n]+)/i.exec(contentDisposition);
        if (bareMatch && bareMatch[1]) {
            return bareMatch[1].trim().replace(/^["']|["']$/g, '');
        }

        return fallback;
    }

    function saveBlob(blob, filename) {
        var url = window.URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
    }

    function isExcelResponse(response) {
        var contentType = response.headers.get('content-type') || '';
        return (
            contentType.indexOf('application/vnd.openxmlformats') !== -1 ||
            contentType.indexOf('application/vnd.ms-excel') !== -1
        );
    }

    window.armGsExportExcel = function (button, exportUrl, progressText) {
        if (!button || button.disabled) {
            return;
        }

        var idleHtml = button.innerHTML;
        button.disabled = true;
        button.innerHTML =
            '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' +
            (progressText || 'Экспорт…');

        fetch(exportUrl, { method: 'GET', credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) {
                    return response.text().then(function (text) {
                        throw new Error(
                            'Ошибка сервера (' + response.status + '): ' + text.substring(0, 200)
                        );
                    });
                }
                if (!isExcelResponse(response)) {
                    return response.text().then(function () {
                        throw new Error('Получен неожиданный тип ответа от сервера');
                    });
                }
                return response.blob().then(function (blob) {
                    saveBlob(
                        blob,
                        parseFilename(response.headers.get('content-disposition'), 'export.xlsx')
                    );
                });
            })
            .catch(function (error) {
                window.alert(
                    'Ошибка при экспорте данных: ' + ((error && error.message) || error)
                );
            })
            .finally(function () {
                button.innerHTML = idleHtml;
                button.disabled = false;
            });
    };
})();
