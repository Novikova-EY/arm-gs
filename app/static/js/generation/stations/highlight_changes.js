document.addEventListener("DOMContentLoaded", function () {
    const button = document.getElementById("highlightChangesBtn");
    if (!button) {
        console.warn("Кнопка подсветки не найдена");
        return;
    }

    let isHighlighted = false;
    // Хелпер: добавить подсветку ячейке и вложенному input/select (если есть)
    function addHighlightToCellAndField(cell, className) {
        if (!cell) return;
        cell.classList.add(className);
        const field = cell.querySelector('input, select');
        if (field) field.classList.add(className);
    }

    function getPowerCellsForRow(row) {
        const directCells = Array.from(row.querySelectorAll("td.power-column"));
        if (directCells.length) return directCells;

        if (!row.classList.contains("p-ogr-row") &&
            !row.classList.contains("p-rasp-row") &&
            !row.classList.contains("total-power-row")) {
            return [];
        }

        return Array.from(row.querySelectorAll("td")).filter(cell => {
            if (cell.classList.contains("fuel-column") ||
                cell.classList.contains("rowspan-td") ||
                cell.classList.contains("fuel-cell") ||
                cell.classList.contains("total-row-cell") ||
                cell.classList.contains("total-row_cell")) {
                return false;
            }

            if (cell.hasAttribute("rowspan") || cell.hasAttribute("colspan")) return false;

            const text = (cell.textContent || "").trim();
            if (!text) return false;
            if (text === "Руст" || text === "Рогр" || text === "Ррасп") return false;

            return true;
        });
    }

    button.addEventListener("click", function () {
        // СБРОС ПОДСВЕТКИ
        if (isHighlighted) {
            document.querySelectorAll(".highlight-green, .highlight-red, .highlight-blue").forEach(cell => {
                cell.classList.remove("highlight-green", "highlight-red", "highlight-blue");
            });

            // Сброс у input
            document.querySelectorAll(".power-column input").forEach(input => {
                input.classList.remove("highlight-blue", "highlight-green", "highlight-red");
            });

            button.textContent = "✨ Подсветить изменения";
            isHighlighted = false;
            return;
        }

        console.log("✨ Подсветка изменений активирована");

        document.querySelectorAll("tr").forEach(row => {
            const powerCells = getPowerCellsForRow(row);
            const fuelCells = row.querySelectorAll("td.fuel-column");

            let previousPowerCell = null;
            let previousFuelCell = null;

            powerCells.forEach(cell => {
                const inputEl = cell.querySelector('input');
                const currentValue = inputEl ? (inputEl.value || '').trim() : cell.textContent.trim();
                const currentNumericValue = parseFloat(currentValue.replace(',', '.'));
                const isCurrentDash = currentValue === "-" || currentValue === "—";
                const num = Number.isFinite(currentNumericValue) ? currentNumericValue : null;

                cell.setAttribute("data-prev-value", currentValue);

                if (previousPowerCell) {
                    const prevInputEl = previousPowerCell.querySelector('input');
                    const previousValue = prevInputEl ? (prevInputEl.value || '').trim() : previousPowerCell.getAttribute("data-prev-value");
                    const previousNumeric = parseFloat(previousValue.replace(',', '.'));
                    const isPreviousDash = previousValue === "-" || previousValue === "—";
                    const prevNum = Number.isFinite(previousNumeric) ? previousNumeric : null;

                    if ((prevNum === 0 || isPreviousDash) && num > 0) {
                        addHighlightToCellAndField(previousPowerCell, "highlight-green");
                        addHighlightToCellAndField(cell, "highlight-green");
                    } else if (prevNum > 0 && (num === 0 || isCurrentDash)) {
                        addHighlightToCellAndField(previousPowerCell, "highlight-red");
                        addHighlightToCellAndField(cell, "highlight-red");
                    } else if (previousValue !== currentValue && !(isPreviousDash && isCurrentDash)) {
                        addHighlightToCellAndField(previousPowerCell, "highlight-blue");
                        addHighlightToCellAndField(cell, "highlight-blue");
                    }
                }

                previousPowerCell = cell;
            });

            // Подсветка для «Тип ТЭС» и «Топливо»: подсвечиваем только границы изменения между соседними годами
            (function(){
                let prevCell = null;
                let prevVal = null;
                const isDash = (v) => v === '-' || v === '—' || v === '' || v === null || v === undefined;
                fuelCells.forEach(cell => {
                    const fieldEl = cell.querySelector('select, input');
                    const currRaw = fieldEl ? (fieldEl.value || '').trim() : (cell.textContent || '').trim();
                    const currIsDash = isDash(currRaw);

                    if (prevCell !== null) {
                        const prevIsDash = isDash(prevVal);
                        const changed = (prevIsDash && !currIsDash) || (!prevIsDash && currIsDash) || (prevVal !== currRaw);
                        if (changed) {
                            // Пара «было/стало»
                            if (prevIsDash && !currIsDash) {
                                addHighlightToCellAndField(prevCell, 'highlight-green');
                                addHighlightToCellAndField(cell, 'highlight-green');
                            } else if (!prevIsDash && currIsDash) {
                                addHighlightToCellAndField(prevCell, 'highlight-red');
                                addHighlightToCellAndField(cell, 'highlight-red');
                            } else {
                                addHighlightToCellAndField(prevCell, 'highlight-blue');
                                addHighlightToCellAndField(cell, 'highlight-blue');
                            }
                        }
                    }

                    prevCell = cell;
                    prevVal = currRaw;
                });
            })();
        });

        // ПОДСВЕТКА INPUT-ПОЛЕЙ (РУСТ/РОГР/РРАСП)
        document.querySelectorAll(".power-column input").forEach(input => {
            const origRaw = (input.getAttribute("data-original-value") || "").replace(",", ".").trim();
            const currRaw = (input.value || "").replace(",", ".").trim();

            const isDash = val => val === "-" || val === "—" || val === "";

            const origVal = parseFloat(origRaw);
            const currVal = parseFloat(currRaw);

            const origIsZero = isDash(origRaw) || isNaN(origVal) || origVal === 0;
            const currIsZero = isDash(currRaw) || isNaN(currVal) || currVal === 0;
            const cell = input.closest("td.power-column");

            if (origIsZero && currVal > 0) {
                addHighlightToCellAndField(cell, "highlight-green");
            } else if (!origIsZero && currIsZero) {
                addHighlightToCellAndField(cell, "highlight-red");
            } else if (!isNaN(origVal) && !isNaN(currVal) && origVal !== currVal) {
                addHighlightToCellAndField(cell, "highlight-blue");
            }
        });

        // Добавляем стили, если еще не добавлены
        if (!document.getElementById("highlightStyle")) {
            const style = document.createElement("style");
            style.id = "highlightStyle";
            style.innerHTML = `
                .highlight-green { background-color: lightgreen !important; }
                .highlight-red   { background-color: lightcoral !important; }
                .highlight-blue  { background-color: lightblue !important; }
            `;
            document.head.appendChild(style);
        }

        button.textContent = "❌ Сбросить подсветку";
        isHighlighted = true;
    });
});
