(function () {
    "use strict";

    const symbols = {
        "МотхNOx": "М<sub>отх</sub><sup>NO<sub>x</sub></sup>",
        "МотхCO2": "М<sub>отх</sub><sup>CO<sub>2</sub></sup>",
        "МотхCO": "М<sub>отх</sub><sup>CO</sup>",
        "МвыбSO2": "М<sub>выб</sub><sup>SO<sub>2</sub></sup>",
        "МвыбNOx": "М<sub>выб</sub><sup>NO<sub>x</sub></sup>",
        "МвыбCO2": "М<sub>выб</sub><sup>CO<sub>2</sub></sup>",
        "МвыбCO": "М<sub>выб</sub><sup>CO</sup>",
        "Мотх": "М<sub>отх</sub>", "Мвыб": "М<sub>выб</sub>",
        "BH": "B<sup>H</sup>", "Вн": "B<sup>H</sup>", "ВН": "B<sup>H</sup>",
        "KCO2": "K<sub>CO<sub>2</sub></sub>",
        "CO2": "CO<sub>2</sub>", "SO2": "SO<sub>2</sub>", "NOx": "NO<sub>x</sub>",
        "аун": "a<sub>ун</sub>", "Aр": "A<sup>р</sup>", "Ар": "A<sup>р</sup>",
        "Sp": "S<sup>p</sup>", "qч": "q<sub>ч</sub>", "bj": "b<sub>j</sub>",
        "q3": "q<sub>3</sub>", "q4": "q<sub>4</sub>", "Qн": "Q<sub>н</sub>"
    };
    const symbolPattern = new RegExp(
        "(?<![A-Za-zА-Яа-яЕе0-9_])(?:" + Object.keys(symbols).join("|") + ")(?![A-Za-zА-Яа-яЕе0-9_])",
        "g"
    );

    function formatFormula(text, html) {
        const source = document.createElement("div");
        if (html) {
            // HTML titles are already escaped by the server's formula formatters.
            source.innerHTML = text;
        } else {
            source.textContent = text;
        }
        const result = document.createElement("div");
        result.className = "ecology-formula-content";
        if (source.querySelector("p, ul, ol, table, div")) {
            result.append(...source.childNodes);
        } else {
            const parts = source.innerHTML.split(
                /(?:\r?\n)+|(?<=;)\s+|(?<=[.!?])\s+(?=[А-ЯЕA-ZΣ]|[a-zа-яе](?:[0-9]|<\/?(?:sub|sup)>)*\s*[––])/u
            );
            parts.filter(part => part.trim()).forEach(function (part, index) {
                const paragraph = document.createElement("p");
                paragraph.innerHTML = part;
                if (index === 0 && /[=Σ]/u.test(paragraph.textContent)) {
                    paragraph.className = "ecology-formula-expression";
                }
                result.appendChild(paragraph);
            });
        }
        const walker = document.createTreeWalker(result, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) {
            if (!walker.currentNode.parentElement.closest("sub, sup")) {
                nodes.push(walker.currentNode);
            }
        }
        nodes.forEach(function (node) {
            const escaped = document.createElement("span");
            escaped.textContent = node.textContent;
            const formatted = escaped.innerHTML.replace(symbolPattern, symbol => symbols[symbol]);
            const fragment = document.createElement("template");
            fragment.innerHTML = formatted;
            node.replaceWith(fragment.content);
        });
        return result;
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll('[title]:is(.bi-info-circle, .bi-info-square, :has(> .bi-info-circle), :has(> .bi-info-square))').forEach(function (icon) {
            const formatted = formatFormula(icon.getAttribute("title"), icon.dataset.bsHtml === "true");
            icon.setAttribute("title", formatted.outerHTML);
            icon.dataset.bsHtml = "true";
            icon.dataset.bsCustomClass = "ecology-formula-tooltip";
            if (!icon.matches("button, a, input, [tabindex]")) {
                icon.tabIndex = 0;
            }
        });
        document.querySelectorAll("#ecFormulaSummaryTable tr[data-formula-key]").forEach(function (row) {
            const input = row.querySelector(".ec-formula-text-input");
            const preview = row.querySelector(".ecology-formula-preview");
            function updatePreview() {
                preview.replaceChildren(formatFormula(input.value, false));
            }
            updatePreview();
            input.addEventListener("input", updatePreview);
        });
    });
})();
