const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../app/static/js/generation/stations/external_code_check.js"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));

function element() {
    const classes = new Set();
    const listeners = {};
    return {
        disabled: true, textContent: "", innerHTML: "Сохранить изменения",
        classList: {
            add(name) { classes.add(name); }, remove(name) { classes.delete(name); },
            contains(name) { return classes.has(name); },
            toggle(name, active) { if (active) classes.add(name); else classes.delete(name); },
        },
        addEventListener(name, callback) { listeners[name] = callback; },
        emit(name, event) { return listeners[name](event); },
    };
}

function start(inputs, success = true) {
    const table = element();
    const button = element();
    const hint = element();
    const calls = [];
    const alerts = [];
    let reloads = 0;
    table.querySelectorAll = () => inputs;
    const nodes = {
        externalCodeCheckTable: table, externalCodeSaveBtn: button, externalCodeChangedHint: hint,
        "initial-state-json": { textContent: JSON.stringify({ externalCodeUpdateUrl: "/codes/update", csrfToken: "csrf" }) },
    };
    vm.runInNewContext(source, {
        document: { getElementById: id => nodes[id], addEventListener: (name, callback) => callback() },
        fetch: async (url, options) => {
            calls.push({ url, options });
            return { ok: success, json: async () => success ? { ok: true, updated: 1 } : { ok: false, error: "Код уже занят" } };
        },
        alert: text => alerts.push(text), window: { location: { reload() { reloads++; } } },
    });
    return { table, button, hint, calls, alerts, reloads: () => reloads };
}

function input(type, id, value, original = "original") {
    const node = element();
    node.classList.add("external-code-input");
    node.value = value;
    node.dataset = { entityType: type, recordId: String(id), originalValue: original };
    return node;
}

test("group, station and machine codes use the same save action and CSRF", async () => {
    const inputs = [input("equipment_group", 22, " group-code "), input("station", 2, "station-code"), input("machine", 3, "machine-code")];
    const ui = start(inputs);
    ui.table.emit("input", { target: inputs[0] });
    assert.equal(ui.button.disabled, false);
    assert.match(ui.hint.textContent, /3/);
    ui.button.emit("click");
    await tick();
    assert.equal(ui.calls[0].url, "/codes/update");
    assert.equal(ui.calls[0].options.headers["X-CSRFToken"], "csrf");
    assert.deepEqual(JSON.parse(ui.calls[0].options.body).updates, [
        { entity_type: "equipment_group", record_id: 22, new_external_code: "group-code" },
        { entity_type: "station", record_id: 2, new_external_code: "station-code" },
        { entity_type: "machine", record_id: 3, new_external_code: "machine-code" },
    ]);
    assert.equal(inputs[0].dataset.originalValue, "group-code");
    assert.equal(ui.reloads(), 1);
    assert.equal(ui.button.disabled, true);
});

test("a rejected group code stays unsaved and available for correction", async () => {
    const changed = input("equipment_group", 22, "used-code");
    const ui = start([changed], false);
    ui.table.emit("input", { target: changed });
    ui.button.emit("click");
    await tick();
    assert.deepEqual(ui.alerts, ["Код уже занят"]);
    assert.equal(changed.dataset.originalValue, "original");
    assert.equal(changed.classList.contains("is-changed"), true);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.reloads(), 0);
});

test("unchanged group codes do not cause a write request", async () => {
    const changed = input("equipment_group", 22, " original ");
    const ui = start([changed]);
    ui.table.emit("input", { target: changed });
    ui.button.emit("click");
    await tick();
    assert.equal(ui.button.disabled, true);
    assert.equal(ui.calls.length, 0);
});
