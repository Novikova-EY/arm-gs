const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/static/js/fuel/fuel_param_cell_warnings.js", "utf8");

function element(attrs = {}, textContent = "") {
    const classes = new Set();
    return {
        textContent,
        getAttribute: name => Object.hasOwn(attrs, name) ? attrs[name] : null,
        hasAttribute: name => Object.hasOwn(attrs, name),
        setAttribute: (name, value) => { attrs[name] = value; },
        removeAttribute: name => { delete attrs[name]; },
        classList: {
            contains: name => classes.has(name),
            add: (...names) => names.forEach(name => classes.add(name)),
            remove: (...names) => names.forEach(name => classes.delete(name)),
        },
    };
}

function fixture({ nust = 160.26, previousNust = 160.26, qotr = null, previousQotr = null,
    nt = 0, editable = true, displayNust = "160,3", displayQotr = "", displayNt = "0" } = {}) {
    const cells = {};
    for (const [attr, raw, display] of [["nust", nust, displayNust], ["qotr", qotr, displayQotr], ["nt", nt, displayNt]]) {
        const td = element({ "data-column": attr, "data-warning-value": raw == null ? "" : String(raw) }, display);
        const input = editable ? element({ "data-initial": display }) : null;
        if (input) input.value = display;
        td.input = input;
        td.querySelector = () => input;
        cells[attr] = td;
    }
    const row = element({ "data-prev-nust": String(previousNust), "data-prev-qotr": previousQotr == null ? "" : String(previousQotr) });
    row.querySelector = selector => cells[selector.match(/data-column="([^"]+)"/)[1]] || null;
    const year = element({}, "2024");
    row.querySelectorAll = selector => selector === "td" ? [year, ...Object.values(cells)] : Object.values(cells);
    const table = { querySelectorAll: () => [row] };
    const window = {};
    vm.runInNewContext(source, { window });
    const refresh = () => window.bindFuelParamCellWarnings(table, { listen: false });
    return { cells, year, refresh };
}

for (const editable of [true, false]) {
    test(`unchanged exact capacity does not warn after display rounding (editable=${editable})`, () => {
        const { cells, year, refresh } = fixture({ editable, qotr: 10, previousQotr: 10, displayQotr: "10" });
        refresh();
        assert.equal(cells.qotr.classList.contains("table-danger"), false);
        assert.equal(cells.nust.classList.contains("table-warning"), false);
        assert.equal(year.classList.contains("table-warning"), false);
        assert.equal(cells.qotr.getAttribute("title"), null);
    });
}

for (const qotr of [null, 0]) {
    test(`empty/zero QOTR does not produce a composition warning (${qotr})`, () => {
        const { cells, year, refresh } = fixture({ previousNust: 150, qotr, previousQotr: qotr });
        refresh();
        assert.equal(cells.qotr.classList.contains("table-danger"), false);
        assert.equal(cells.qotr.getAttribute("title"), null);
        assert.equal(year.classList.contains("table-warning"), true);
    });
}

test("actual input change warns for unchanged positive QOTR and clears on revert", () => {
    const { cells, refresh } = fixture({ qotr: 10.26, previousQotr: 10.26, displayQotr: "10,3" });
    cells.nust.input.value = "170";
    refresh();
    assert.equal(cells.qotr.classList.contains("table-danger"), true);
    assert.match(cells.qotr.getAttribute("title"), /изменение состава агрегатов/);
    cells.qotr.input.value = "12";
    refresh();
    assert.equal(cells.qotr.classList.contains("table-danger"), false);
    cells.qotr.input.value = "10,3";
    cells.nust.input.value = "160,3";
    refresh();
    assert.equal(cells.qotr.classList.contains("table-danger"), false);
});

for (const [qotr, expected] of [[799.99, false], [800, true]]) {
    test(`thermal hours use exact QOTR, not rounded 800 (${qotr})`, () => {
        const { cells, refresh } = fixture({ qotr, nt: 100, displayQotr: "800", displayNt: "100" });
        refresh();
        assert.equal(cells.qotr.classList.contains("table-danger"), expected);
        if (expected) assert.match(cells.qotr.getAttribute("title"), /8000/);
    });
}

test("parts sum mismatch warning remains even when QOTR is empty", () => {
    const { cells, refresh } = fixture();
    cells.qotr.setAttribute("data-parts-sum-mismatch-msg", "Сумма частей не совпадает");
    refresh();
    assert.equal(cells.qotr.classList.contains("table-danger"), true);
    assert.equal(cells.qotr.getAttribute("title"), "Сумма частей не совпадает");
});
