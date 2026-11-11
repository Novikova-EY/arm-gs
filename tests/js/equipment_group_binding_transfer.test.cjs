const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/static/js/fuel/equipment_group_binding_transfer.js", "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = (data, ok = true) => ({
    ok, redirected: false, headers: { get: () => "application/json" }, json: async () => data,
});

function element() {
    const listeners = {};
    return {
        children: [], options: [], value: "", checked: false, disabled: false, hidden: false, style: {},
        addEventListener(name, callback) { listeners[name] = callback; },
        emit(name, event = {}) { return listeners[name]?.(event); },
        setAttribute() {},
        append(...items) { this.children.push(...items); },
        replaceChildren(...items) {
            this.children = items.length === 1 && items[0].children ? items[0].children : items;
            this.options = items;
        },
        add(option) { this.options.push(option); },
        querySelectorAll() { return []; },
    };
}

const rows = [
    { key: "machine:1", kind: "machine", status: "ready", station: "Station", equipment: "1", source_group: "Source", current_group: "Target", reason: "Ready" },
    { key: "machine:2", kind: "machine", status: "conflict", station: "Station", equipment: "2", source_group: "Other", current_group: "Existing", reason: "Conflict" },
    { key: "machine:3", kind: "machine", status: "blocked", station: "Station", equipment: "3", source_group: "Missing", current_group: "", reason: "Blocked" },
].map((row, index) => ({ ...row,
    current_group_external_code: "target-group-" + index, source_group_external_code: "source-group-" + index,
    current_type_ref_uuid: "target-type-" + index, source_type_ref_uuid: "source-type-" + index,
    current_station_link: "Target station link " + index, source_station_link: "Source station link " + index,
}));

function start(fetch, search = "") {
    const fields = Object.fromEntries([
        "Source", "Target", "Create", "Message", "Results", "Confirmation", "Download", "Confirm", "Preview",
        "Apply", "Select", "Clear", "Rows", "Filter", "Search", "Previous", "Next", "Selection", "Summary", "Reload", "Back",
        "Destination", "Scope", "Repeat",
    ].map(name => [name, element()]));
    fields.Source.options = [{ textContent: "Choose" }];
    for (const field of [fields.Source, fields.Destination]) {
        Object.defineProperty(field, "selectedOptions", {
            get: () => field.options.filter(option => String(option.value) === field.value),
        });
    }
    const downloads = [];
    const blobs = [];
    const revoked = [];
    fields.Filter.value = "changes";
    fields.Reload.hidden = true;
    const page = element();
    const windowEvents = element();
    const navigation = [];
    page.dataset = { url: "/transfer", csrfToken: "csrf", catalogUrl: "/catalog" };
    vm.runInNewContext(source, {
        document: {
            getElementById: id => id === "bindingTransferPage" ? page : fields[id.replace("bindingTransfer", "")],
            addEventListener: (name, callback) => callback(),
            createElement: tag => {
                const node = element();
                if (tag === "a") node.click = () => downloads.push(node);
                return node;
            }, createDocumentFragment: element,
        },
        fetch, Option: function (text, value) { this.textContent = text; this.value = value; },
        window: { addEventListener: windowEvents.addEventListener, location: { search, assign(url) { navigation.push(url); } } }, Set, Blob, URLSearchParams,
        URL: { createObjectURL(blob) { blobs.push(blob); return "blob:report"; }, revokeObjectURL(url) { revoked.push(url); } },
        setTimeout(callback) { callback(); },
    });
    return { fields, page, windowEvents, navigation, downloads, blobs, revoked };
}

async function preview(ui) {
    await tick();
    ui.fields.Source.value = "1";
    ui.fields.Source.emit("change");
    await ui.fields.Preview.emit("click");
}

function backend(calls, applyReply = response({ success: true, result: { machines: 1, groups: 0, links: 0, station_links: 0 } }), planRows = rows) {
    return async (url, options) => {
        const body = options.body ? JSON.parse(options.body) : null;
        calls.push({ body, options });
        if (!body) return response({ success: true, target: { id: 2, name: "Current" }, sources: [{ id: 1, name: "Source" }],
            versions: [{ id: 1, name: "Source" }, { id: 2, name: "Current" }, { id: 3, name: "Archive" }] });
        if (body.action === "preview") return response({ success: true, token: "signed", plan: {
            rows: planRows, counts: planRows.reduce((counts, row) => {
                counts[row.status] = (counts[row.status] || 0) + 1;
                return counts;
            }, {}),
        } });
        if (body.action === "report") return {
            ok: true, redirected: false,
            headers: { get: () => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
            blob: async () => new Blob(["xlsx"]),
        };
        return applyReply;
    };
}

test("standalone page loads versions automatically without modal events", async () => {
    const calls = [];
    const ui = start(backend(calls));
    await tick();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].body, null);
    assert.equal(ui.fields.Target.textContent, "Current");
    assert.equal(ui.fields.Source.options.length, 3);
    assert.equal(ui.fields.Source.disabled, false);
    assert.equal(ui.fields.Preview.disabled, true);
    assert.equal(ui.fields.Apply.disabled, true);
});

test("preview writes nothing and selects only safe rows; apply requires confirmation", async () => {
    const calls = [];
    const ui = start(backend(calls));
    await preview(ui);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].body.action, "preview");
    assert.match(ui.fields.Message.textContent, /без ограничения по времени/);
    assert.doesNotMatch(ui.fields.Message.textContent, /15 минут/);
    assert.equal(ui.fields.Rows.children[0].children[0].children[0].checked, true);
    assert.equal(ui.fields.Rows.children[1].children[0].children[0].checked, false);
    assert.equal(ui.fields.Rows.children[2].children[0].children.length, 0);
    assert.equal(ui.fields.Apply.disabled, true);
    ui.fields.Confirm.checked = true;
    ui.fields.Confirm.emit("change");
    assert.equal(ui.fields.Apply.disabled, false);
    await ui.fields.Apply.emit("click");
    assert.deepEqual(calls[2].body, { action: "apply", token: "signed", keys: ["machine:1"] });
    assert.equal(calls[2].options.headers["X-CSRF-Token"], "csrf");
    assert.equal(ui.fields.Apply.disabled, true);
    assert.equal(ui.fields.Reload.hidden, false);
    assert.match(ui.fields.Message.textContent, /связей станций с типами: 0/);
    ui.fields.Reload.emit("click");
    assert.deepEqual(ui.navigation, ["/catalog"]);
});

test("manual replacements reset confirmation and remain excluded from safe bulk selection", async () => {
    const ui = start(backend([]));
    await preview(ui);
    ui.fields.Confirm.checked = true;
    const replacement = ui.fields.Rows.children[1].children[0].children[0];
    replacement.checked = true;
    replacement.emit("change");
    assert.equal(ui.fields.Confirm.checked, false);
    assert.match(ui.fields.Selection.textContent, /Выбрано: 2, из них замен: 1/);
    ui.fields.Clear.emit("click");
    ui.fields.Select.emit("click");
    assert.match(ui.fields.Selection.textContent, /Выбрано: 1, из них замен: 0/);
});

test("type replacements and standalone station links are selected independently of blocked final groups", async () => {
    const calls = [];
    const planRows = [
        { ...rows[0], key: "type:1", kind: "type", equipment: "Тип агрегата: 1", reason: "Заменить тип агрегата типом из источника" },
        { ...rows[2], key: "machine:1", equipment: "1", reason: "Группа отсутствует" },
        { ...rows[0], key: "station_link:1", kind: "station_link", equipment: "Связь станции с типом" },
        rows[1],
    ];
    const ui = start(backend(calls, undefined, planRows));
    await preview(ui);
    assert.equal(ui.fields.Rows.children[0].children[0].children[0].checked, true);
    assert.equal(ui.fields.Rows.children[1].children[0].children.length, 0);
    assert.equal(ui.fields.Rows.children[2].children[0].children[0].checked, true);
    assert.equal(ui.fields.Rows.children[3].children[0].children[0].checked, false);
    assert.match(ui.fields.Summary.textContent, /Можно перенести: 2/);
    assert.equal(ui.fields.Apply.disabled, true);
    ui.fields.Clear.emit("click");
    ui.fields.Select.emit("click");
    ui.fields.Confirm.checked = true;
    ui.fields.Confirm.emit("change");
    assert.equal(ui.fields.Apply.disabled, false);
    await ui.fields.Apply.emit("click");
    assert.deepEqual(calls.at(-1).body.keys, ["type:1", "station_link:1"]);
});

test("changing source or creation policy invalidates the preview", async () => {
    const ui = start(backend([]));
    await preview(ui);
    ui.fields.Create.checked = true;
    ui.fields.Create.emit("change");
    assert.equal(ui.fields.Results.hidden, true);
    assert.equal(ui.fields.Apply.disabled, true);
    await ui.fields.Preview.emit("click");
    ui.fields.Source.emit("change");
    assert.equal(ui.fields.Results.hidden, true);
});

test("a stale or failed apply cannot be retried without a fresh preview", async () => {
    const ui = start(backend([], response({ success: false, message: "Data changed" }, false)));
    await preview(ui);
    ui.fields.Confirm.checked = true;
    await ui.fields.Apply.emit("click");
    assert.match(ui.fields.Message.textContent, /Data changed/);
    assert.equal(ui.fields.Apply.disabled, true);
    assert.equal(ui.fields.Preview.disabled, false);
    assert.equal(ui.fields.Reload.hidden, true);
});

test("search and status filter keep selection but render only matching rows", async () => {
    const ui = start(backend([]));
    await preview(ui);
    ui.fields.Filter.value = "conflict";
    ui.fields.Filter.emit("change");
    assert.equal(ui.fields.Rows.children.length, 1);
    assert.equal(ui.fields.Rows.children[0].className, "table-warning");
    ui.fields.Search.value = "does not exist";
    ui.fields.Search.emit("input");
    assert.equal(ui.fields.Rows.children.length, 0);
    assert.match(ui.fields.Selection.textContent, /Выбрано: 1/);
});

test("navigation warns while a request is pending, and controls recover after failure", async () => {
    let finish;
    const ui = start(() => new Promise(resolve => { finish = resolve; }));
    let prevented = 0;
    const event = { preventDefault() { prevented++; } };
    ui.windowEvents.emit("beforeunload", event);
    ui.fields.Back.emit("click", event);
    assert.equal(prevented, 2);
    assert.equal(event.returnValue, "");
    assert.equal(ui.fields.Source.disabled, true);
    finish(response({ success: false, message: "Unavailable" }, false));
    await tick();
    assert.match(ui.fields.Message.textContent, /Unavailable/);
    assert.equal(ui.fields.Create.disabled, false);
    ui.windowEvents.emit("beforeunload", event);
    ui.fields.Back.emit("click", event);
    assert.equal(prevented, 2);
});

test("comparison columns render identifiers and station links and are searchable", async () => {
    const ui = start(backend([]));
    await preview(ui);
    const cells = ui.fields.Rows.children[0].children;
    assert.equal(cells.length, 11);
    assert.equal(cells[4].textContent, "target-group-0");
    assert.equal(cells[5].textContent, "source-group-0");
    assert.equal(cells[6].textContent, "target-type-0");
    assert.equal(cells[7].textContent, "source-type-0");
    assert.equal(cells[8].textContent, "Target station link 0");
    assert.equal(cells[9].textContent, "Source station link 0");
    ui.fields.Search.value = "source-type-1";
    ui.fields.Search.emit("input");
    assert.equal(ui.fields.Rows.children.length, 1);
    assert.equal(ui.fields.Rows.children[0].className, "table-warning");
});

test("Excel download includes the entire preview, selection and completion state", async () => {
    const calls = [];
    const ui = start(backend(calls));
    await preview(ui);
    ui.fields.Filter.value = "blocked";
    ui.fields.Filter.emit("change");
    await ui.fields.Download.emit("click");
    let download = calls.at(-1);
    assert.equal(download.body.action, "report");
    assert.equal(download.options.headers["X-CSRF-Token"], "csrf");
    assert.equal(download.body.report.rows.length, 3);
    assert.deepEqual(download.body.report.selected_keys, ["machine:1"]);
    assert.equal(download.body.report.source, "Source");
    assert.equal(download.body.report.target, "Current");
    assert.equal(download.body.report.completed, false);
    assert.equal(ui.downloads[0].download, "equipment_group_binding_transfer.xlsx");
    assert.equal(ui.downloads[0].href, "blob:report");
    assert.equal(await ui.blobs[0].text(), "xlsx");
    assert.deepEqual(ui.revoked, ["blob:report"]);
    assert.equal(ui.fields.Download.disabled, false);
    ui.fields.Confirm.checked = true;
    await ui.fields.Apply.emit("click");
    await ui.fields.Download.emit("click");
    download = calls.at(-1);
    assert.equal(download.body.report.completed, true);
    assert.equal(ui.fields.Apply.disabled, true);
});

test("failed Excel download shows an error without invalidating the transfer plan", async () => {
    const normal = backend([]);
    const ui = start((url, options) => JSON.parse(options.body || "null")?.action === "report"
        ? response({ success: false, message: "Export unavailable" }, false) : normal(url, options));
    await preview(ui);
    await ui.fields.Download.emit("click");
    assert.match(ui.fields.Message.textContent, /Export unavailable/);
    assert.equal(ui.downloads.length, 0);
    assert.equal(ui.fields.Download.disabled, false);
    ui.fields.Confirm.checked = true;
    ui.fields.Confirm.emit("change");
    assert.equal(ui.fields.Apply.disabled, false);
});

test("group link initializes existing transfer plan without analyzing or writing automatically", async () => {
    const calls = [];
    const ui = start(backend(calls), "?source_version_id=1&destination_version_id=3&group_id=1958&create_missing=1");
    await tick();
    assert.equal(calls.length, 1);
    assert.equal(ui.fields.Source.value, "1");
    assert.equal(ui.fields.Source.disabled, true);
    assert.equal(ui.fields.Destination.value, "3");
    assert.equal(ui.fields.Target.textContent, "Archive");
    assert.equal(ui.fields.Create.checked, true);
    assert.equal(ui.fields.Scope.hidden, false);
    assert.equal(ui.fields.Preview.disabled, false);
    await ui.fields.Preview.emit("click");
    assert.deepEqual(calls.at(-1).body, {
        action: "preview", source_version_id: 1, destination_version_id: 3, create_missing: true, group_id: 1958,
    });
});

test("next destination requires a fresh preview and confirmation", async () => {
    const calls = [];
    const ui = start(backend(calls), "?source_version_id=1&destination_version_id=2&group_id=1958&create_missing=1");
    await tick();
    await ui.fields.Preview.emit("click");
    ui.fields.Confirm.checked = true;
    await ui.fields.Apply.emit("click");
    assert.equal(ui.fields.Repeat.hidden, false);
    ui.fields.Repeat.emit("click");
    assert.equal(ui.fields.Apply.disabled, true);
    assert.equal(ui.fields.Confirm.checked, false);
    assert.equal(ui.fields.Results.hidden, true);
    ui.fields.Destination.value = "3";
    ui.fields.Destination.emit("change");
    assert.equal(ui.fields.Target.textContent, "Archive");
    assert.equal(ui.fields.Apply.disabled, true);
    await ui.fields.Preview.emit("click");
    assert.equal(calls.at(-1).body.destination_version_id, 3);
    assert.equal(calls.at(-1).body.group_id, 1958);
});

test("changing destination invalidates a displayed plan", async () => {
    const ui = start(backend([]));
    await preview(ui);
    ui.fields.Confirm.checked = true;
    ui.fields.Destination.value = "3";
    ui.fields.Destination.emit("change");
    assert.equal(ui.fields.Results.hidden, true);
    assert.equal(ui.fields.Confirm.checked, false);
    assert.equal(ui.fields.Apply.disabled, true);
});

test("invalid group link cannot fall back to transferring every group", async () => {
    for (const query of ["?group_id=bad", "?group_id=0", "?group_id=1&source_version_id=99", "?group_id=1&source_version_id=2&destination_version_id=2"]) {
        const calls = [];
        const ui = start(backend(calls), query);
        await tick();
        assert.equal(calls.length, 1);
        assert.equal(ui.fields.Message.className, "alert alert-danger");
        assert.equal(ui.fields.Preview.disabled, true);
        assert.equal(ui.fields.Apply.disabled, true);
    }
});
