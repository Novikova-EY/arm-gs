const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/static/js/fuel/stations_equipment_groups_inline_edit.js", "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = (data, ok = true) => ({
    ok, redirected: false, headers: { get: () => "application/json" }, json: async () => data,
});

function input(field = "note", groupId = "1", tagName = "INPUT") {
    const listeners = {};
    const classes = new Set();
    const cellClasses = new Set();
    const cellListeners = {};
    const labelListeners = {};
    const label = {
        textContent: "Original label", tabIndex: 0,
        addEventListener(name, callback) { labelListeners[name] = callback; },
        emit(name, event = {}) { labelListeners[name]?.(event); },
    };
    const cell = {
        title: "",
        classList: {
            add: name => cellClasses.add(name), remove: name => cellClasses.delete(name),
            toggle: (name, on) => on ? cellClasses.add(name) : cellClasses.delete(name),
            contains: name => cellClasses.has(name),
        },
        querySelector: () => label,
        addEventListener(name, callback) { cellListeners[name] = callback; },
        emit(name, event = {}) { cellListeners[name]?.(event); },
    };
    return {
        cell, label, hidden: true,
        closest: () => cell,
        focus() { this.focused = true; this.emit("focus"); },
        blur() { this.focused = false; this.emit("blur"); },
        tagName, value: "old", title: "", options: [{ textContent: "Old" }],
        dataset: { field, groupId, savedValue: "old" },
        classList: { toggle: (name, on) => on ? classes.add(name) : classes.delete(name), contains: name => classes.has(name) },
        setAttribute() {},
        hasAttribute(name) { return name === "data-pending-value" && this.dataset.pendingValue !== undefined; },
        addEventListener(name, callback) { listeners[name] = callback; },
        emit(name, event = {}) { listeners[name]?.(event); },
        replaceChildren(...options) { this.options = options; },
    };
}

function start(inputs, fetch) {
    const timeouts = new Map();
    const windowListeners = {};
    let id = 0;
    const table = {
        dataset: { inlineUrl: "/fuel/equipment_group/0/inline", csrfToken: "token" },
        querySelectorAll: () => inputs,
    };
    vm.runInNewContext(source, {
        document: { readyState: "complete", getElementById: () => table },
        window: { addEventListener: (name, cb) => { windowListeners[name] = cb; } },
        URLSearchParams, fetch,
        Option: function (text, value) { this.textContent = text; this.value = value; },
        setTimeout: cb => { timeouts.set(++id, cb); return id; },
        clearTimeout: key => timeouts.delete(key),
    });
    return {
        flushDebounce() { const callbacks = [...timeouts.values()]; timeouts.clear(); callbacks.forEach(cb => cb()); },
        beforeUnload: event => windowListeners.beforeunload(event),
    };
}

test("text autosaves after debounce, posts CSRF, and marks only confirmed saves green", async () => {
    const cell = input();
    const requests = [];
    let finish;
    const ui = start([cell], (url, options) => {
        requests.push({ url, options });
        return new Promise(resolve => { finish = resolve; });
    });
    cell.value = "new";
    cell.emit("input");
    assert.equal(requests.length, 0);
    ui.flushDebounce();
    await tick();
    assert.equal(requests[0].url, "/fuel/equipment_group/1/inline");
    assert.equal(requests[0].options.body.get("csrf_token"), "token");
    assert.equal(requests[0].options.body.get("value"), "new");
    assert.equal(cell.classList.contains("seg-save-success"), false);
    finish(response({ success: true, value: "new" }));
    await tick();
    assert.equal(cell.classList.contains("seg-save-success"), true);
    assert.equal(cell.dataset.savedValue, "new");
});

test("failure stays red with unsaved text; leaving the cell retries and recovers", async () => {
    const cell = input();
    let calls = 0;
    const ui = start([cell], async () => ++calls === 1 ?
        response({ success: false, message: "Duplicate code" }, false) : response({ success: true, value: "new" }));
    cell.value = "new";
    cell.emit("change");
    await tick();
    assert.equal(cell.value, "new");
    assert.equal(cell.dataset.savedValue, "old");
    assert.equal(cell.classList.contains("seg-save-error"), true);
    assert.match(cell.title, /Duplicate code/);
    let warned = false;
    ui.beforeUnload({ preventDefault() { warned = true; } });
    assert.equal(warned, true);
    cell.emit("blur");
    await tick();
    assert.equal(calls, 2);
    assert.equal(cell.classList.contains("seg-save-error"), false);
    assert.equal(cell.classList.contains("seg-save-success"), true);
});

test("rapid edits are serialized per group, do not overwrite typing, and synchronize duplicate cells", async () => {
    const cell = input();
    const duplicate = input();
    const requests = [];
    start([cell, duplicate], (url, options) => new Promise(resolve => requests.push({ resolve, options })));
    cell.value = "first";
    cell.emit("change");
    await tick();
    cell.value = "second";
    cell.emit("change");
    cell.emit("blur");
    await tick();
    assert.equal(requests.length, 1);
    requests[0].resolve(response({ success: true, value: "first" }));
    await tick();
    assert.equal(cell.value, "second");
    assert.equal(cell.classList.contains("seg-save-success"), false);
    assert.equal(requests.length, 2);
    assert.equal(requests[1].options.body.get("value"), "second");
    requests[1].resolve(response({ success: true, value: "second" }));
    await tick();
    assert.equal(cell.value, "second");
    assert.equal(duplicate.value, "second");
    assert.equal(cell.classList.contains("seg-save-success"), true);
});

test("selects load card choices once and save immediately on change", async () => {
    const cell = input("d", "1", "SELECT");
    cell.value = "0";
    cell.dataset.savedValue = "0";
    const requests = [];
    start([cell], async (url, options) => {
        requests.push(options);
        return response(options?.method === "POST" ? { success: true, value: "9" } :
            { success: true, choices: { d: [[0, "New"], [1, "Existing"], [9, "Demolished"]] } });
    });
    await tick();
    assert.equal(cell.options.length, 3);
    assert.equal(cell.value, "0");
    assert.equal(cell.disabled, false);
    cell.value = "9";
    cell.emit("change");
    await tick();
    assert.equal(requests.length, 2);
    assert.equal(requests[1].body.get("value"), "9");
    assert.equal(cell.classList.contains("seg-save-success"), true);
});

test("login redirects cannot be mistaken for successful saves", async () => {
    const cell = input();
    start([cell], async () => ({ redirected: true }));
    cell.value = "new";
    cell.emit("change");
    await tick();
    assert.equal(cell.classList.contains("seg-save-error"), true);
    assert.equal(cell.dataset.savedValue, "old");
});

test("failed dictionary loading can be retried by focusing the select", async () => {
    const cell = input("d", "1", "SELECT");
    cell.value = "1";
    let calls = 0;
    start([cell], async () => {
        if (++calls === 1) throw new Error("Network unavailable");
        return response({ success: true, choices: { d: [["", "New"], [1, "Existing"]] } });
    });
    await tick();
    assert.equal(cell.classList.contains("seg-save-error"), true);
    assert.equal(cell.disabled, false);
    cell.emit("focus");
    await tick();
    assert.equal(calls, 2);
    assert.equal(cell.options.length, 2);
    assert.equal(cell.value, "1");
    assert.equal(cell.classList.contains("seg-save-error"), false);
});

test("returning to an earlier value does not confirm an older queued save", async () => {
    const cell = input();
    const requests = [];
    const ui = start([cell], () => new Promise(resolve => requests.push(resolve)));
    for (const value of ["first", "second", "first"]) {
        cell.value = value;
        cell.emit("change");
    }
    await tick();
    requests[0](response({ success: true, value: "first" }));
    await tick();
    assert.equal(cell.classList.contains("seg-save-success"), false);
    let warned = false;
    ui.beforeUnload({ preventDefault() { warned = true; } });
    assert.equal(warned, true);
    requests[1](response({ success: true, value: "second" }));
    await tick();
    assert.equal(cell.value, "first");
    requests[2](response({ success: true, value: "first" }));
    await tick();
    assert.equal(cell.classList.contains("seg-save-success"), true);
    assert.equal(cell.hasAttribute("data-pending-value"), false);
});

test("cells keep their original labels until clicked and Enter closes the text editor", async () => {
    const cell = input("name_ext", "1", "TEXTAREA");
    start([cell], async () => response({ success: true, value: "new" }));
    assert.equal(cell.hidden, true);
    assert.equal(cell.label.textContent, "Original label");
    cell.cell.emit("click");
    assert.equal(cell.hidden, false);
    assert.equal(cell.focused, true);
    assert.equal(cell.cell.classList.contains("seg-editing"), true);
    cell.value = "new";
    cell.emit("keydown", { key: "Enter", preventDefault() {} });
    assert.equal(cell.hidden, true);
    assert.equal(cell.label.textContent, "new");
    assert.equal(cell.label.tabIndex, 0);
    await tick();
    assert.equal(cell.cell.classList.contains("seg-save-success"), true);
});

test("keyboard activation and selected labels work without showing raw reference codes", async () => {
    const cell = input("d", "1", "SELECT");
    start([cell], async (url, options) => response(options?.method === "POST" ?
        { success: true, value: "9" } :
        { success: true, choices: { d: [["old", "Existing"], [9, "Demolished"]] } }));
    await tick();
    assert.equal(cell.label.textContent, "Original label");
    cell.label.emit("keydown", { key: " ", preventDefault() {} });
    assert.equal(cell.hidden, false);
    cell.value = "9";
    cell.emit("change");
    cell.emit("blur");
    await tick();
    assert.equal(cell.hidden, true);
    assert.equal(cell.label.textContent, "Demolished");
    assert.equal(cell.cell.classList.contains("seg-save-success"), true);
});
