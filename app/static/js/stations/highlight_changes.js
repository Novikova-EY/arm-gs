
document.addEventListener("DOMContentLoaded", function () {
    const button = document.getElementById("highlightChangesBtn");
    if (!button) {
        console.warn("Кнопка подсветки не найдена");
        return;
    }

    let isHighlighted = false;

    button.addEventListener("click", function () {
        if (isHighlighted) {
            document.querySelectorAll(".highlight-green, .highlight-red, .highlight-blue").forEach(cell => {
                cell.classList.remove("highlight-green", "highlight-red", "highlight-blue");
            });
            button.textContent = "✨ Подсветить изменения";
            isHighlighted = false;
            return;
        }

        console.log("✨ Подсветка изменений активирована");

        document.querySelectorAll("tr").forEach(row => {
            let powerCells = row.querySelectorAll(".power-column");
            let fuelCells = row.querySelectorAll(".fuel-column");

            let previousPowerCell = null;
            let previousFuelCell = null;

            powerCells.forEach(cell => {
                const currentValue = cell.textContent.trim();
                const currentNumericValue = parseFloat(currentValue.replace(',', '.'));
                const isCurrentDash = currentValue === "-" || currentValue === "—";
                const num = Number.isFinite(currentNumericValue) ? currentNumericValue : null;

                cell.setAttribute("data-prev-value", currentValue);

                if (previousPowerCell) {
                    const previousValue = previousPowerCell.getAttribute("data-prev-value");
                    const previousNumeric = parseFloat(previousValue.replace(',', '.'));
                    const isPreviousDash = previousValue === "-" || previousValue === "—";
                    const prevNum = Number.isFinite(previousNumeric) ? previousNumeric : null;

                    if ((prevNum === 0 || isPreviousDash) && num > 0) {
                        previousPowerCell.classList.add("highlight-green");
                        cell.classList.add("highlight-green");
                    } else if (prevNum > 0 && (num === 0 || isCurrentDash)) {
                        previousPowerCell.classList.add("highlight-red");
                        cell.classList.add("highlight-red");
                    } else if (previousValue !== currentValue && !(isPreviousDash && isCurrentDash)) {
                        previousPowerCell.classList.add("highlight-blue");
                        cell.classList.add("highlight-blue");
                    }
                }

                previousPowerCell = cell;
            });

            fuelCells.forEach(cell => {
                const currentValue = cell.textContent.trim();
                const isCurrentDash = currentValue === "-" || currentValue === "—";
                cell.setAttribute("data-prev-value", currentValue);

                if (previousFuelCell) {
                    const previousValue = previousFuelCell.getAttribute("data-prev-value");
                    const isPreviousDash = previousValue === "-" || previousValue === "—";

                    if (isPreviousDash && !isCurrentDash) {
                        previousFuelCell.classList.add("highlight-green");
                        cell.classList.add("highlight-green");
                    } else if (!isPreviousDash && isCurrentDash) {
                        previousFuelCell.classList.add("highlight-red");
                        cell.classList.add("highlight-red");
                    } else if (previousValue !== currentValue) {
                        previousFuelCell.classList.add("highlight-blue");
                        cell.classList.add("highlight-blue");
                    }
                }

                previousFuelCell = cell;
            });
        });

        // Добавим стили, если ещё не добавлены
        if (!document.getElementById("highlightStyle")) {
            const style = document.createElement("style");
            style.id = "highlightStyle";
            style.innerHTML = `
                .highlight-green { background-color: lightgreen !important; }
                .highlight-red { background-color: lightcoral !important; }
                .highlight-blue { background-color: lightblue !important; }
            `;
            document.head.appendChild(style);
        }

        button.textContent = "❌ Сбросить подсветку";
        isHighlighted = true;
    });
});
