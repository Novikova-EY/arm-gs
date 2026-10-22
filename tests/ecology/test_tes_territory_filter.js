const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../app/static/js/ecology/tes_territory_filter.js'), 'utf8');

function element(classes = []) {
    const listeners = {};
    const names = new Set(classes);
    return {
        hidden: false, checked: true, style: {}, colSpan: 1, rowSpan: 1,
        classList: {
            contains: name => names.has(name),
            toggle(name, on) { on ? names.add(name) : names.delete(name); }
        },
        addEventListener(name, fn) { (listeners[name] ??= []).push(fn); },
        fire(name, event = {}) { (listeners[name] ?? []).forEach(fn => fn(event)); },
        setAttribute(name, value) { this[name] = value; },
        focus() {}, contains(target) { return this === target; },
        getBoundingClientRect() { return {left: 10, bottom: 20}; }
    };
}

function setup(width, {extraWidths = [], storageKey, stored = new Map(), localStorage} = {}) {
    const options = ['vsego', 'centr', 'ural'].map(value => Object.assign(element(), {value}));
    const all = element(), apply = element(), reset = element();
    const menu = Object.assign(element(), {hidden: true, dataset: {storageKey}});
    menu.querySelectorAll = () => options;
    menu.querySelector = selector => ({
        '[data-territory-all]': all, '[data-territory-apply]': apply, '[data-territory-reset]': reset
    })[selector];
    function row(count, section, labelClass, span = 1) {
        const cells = Array.from({length: count}, (_, index) => {
            const cell = element(index === 0 && labelClass ? [labelClass] : []);
            cell.colSpan = index === 0 && labelClass ? 1 : span;
            return cell;
        });
        return {cells, parentElement: {tagName: section}};
    }
    const tables = [width, ...extraWidths].map(width => {
        const button = Object.assign(element(), {hidden: true});
        const caption = {}, icon = {};
        button.querySelector = selector => selector === 'span' ? caption : icon;
        const heading = row(4, 'THEAD', 'ot-label-col', width);
        heading.cells[0].rowSpan = width === 6 ? 3 : width === 2 ? 2 : 1;
        const subheading = row(width === 6 ? 6 : width * 3, 'THEAD', null);
        if (width === 6) {
            subheading.cells.forEach((cell, index) => {
                cell.colSpan = index % 2 === 0 ? 5 : 1;
                cell.rowSpan = index % 2 === 0 ? 1 : 2;
            });
        }
        const metrics = row(15, 'THEAD', null);
        const data = row(1 + width * 3, 'TBODY', 'ot-row-label');
        const summary = row(4, 'TBODY', 'ot-row-label', width);
        const separator = row(1, 'TBODY', null, 1 + width * 3);
        const columns = Array.from({length: 1 + width * 3}, () => element());
        const headers = width === 6 ? [heading, subheading, metrics] : width === 2 ? [heading, subheading] : [heading];
        const table = Object.assign(element(width === 6 ? ['ot-new-tes-volumes-table'] : []), {
            tHead: {rows: headers}, rows: [...headers, separator, data, summary],
            querySelectorAll: () => columns
        });
        button.closest = () => table;
        return {table, button, caption, heading, subheading, metrics, data, summary, separator, columns};
    });
    const document = Object.assign(element(), {
        body: {appendChild() {}},
        getElementById: id => id === 'otTerritoryFilterMenu' ? menu : null,
        querySelectorAll: () => tables.map(table => table.button)
    });
    const window = Object.assign(element(), {
        dispatchEvent() {}, innerWidth: 1200, innerHeight: 800,
        localStorage: localStorage ?? {
            getItem: key => stored.get(key) ?? null,
            setItem: (key, value) => stored.set(key, value),
            removeItem: key => stored.delete(key)
        }
    });
    const warnings = [];
    vm.runInNewContext(script, {document, window, Event: class {}, console: {warn: (...args) => warnings.push(args)}});
    return {options, all, apply, reset, menu, ...tables[0], tables, document, stored, warnings};
}

for (const width of [1, 2, 6]) {
    test(`multiple territories hide complete groups of ${width} columns, including summaries`, () => {
        const page = setup(width);
        page.button.fire('click');
        page.options[1].checked = false;
        page.options[1].fire('change');
        assert.equal(page.all.indeterminate, true);
        page.apply.fire('click');
        assert.deepEqual(page.heading.cells.map(cell => cell.hidden), [false, false, true, false]);
        assert.deepEqual(page.summary.cells.map(cell => cell.hidden), [false, false, true, false]);
        const expected = [false, ...Array(width).fill(false), ...Array(width).fill(true), ...Array(width).fill(false)];
        assert.deepEqual(page.data.cells.map(cell => cell.hidden), expected);
        assert.deepEqual(page.columns.map(cell => cell.hidden), expected);
        if (width === 2) assert.deepEqual(page.subheading.cells.map(cell => cell.hidden), expected.slice(1));
        if (width === 6) {
            assert.deepEqual(page.subheading.cells.map(cell => cell.hidden), [false, false, true, true, false, false]);
            assert.deepEqual(page.metrics.cells.map(cell => cell.hidden), [
                ...Array(5).fill(false), ...Array(5).fill(true), ...Array(5).fill(false)
            ]);
        }
        assert.equal(page.separator.cells[0].hidden, false);
        assert.equal(page.separator.cells[0].colSpan, 1 + width * 2);
        assert.equal(page.menu.hidden, true);
        assert.equal(page.caption.textContent, 'Выбрано: 2');
        if (width === 6) assert.equal(page.table.style.minWidth, '117rem');
        page.button.fire('click');
        page.reset.fire('click');
        assert.ok(page.columns.every(cell => !cell.hidden));
        assert.ok(page.data.cells.every(cell => !cell.hidden));
        assert.equal(page.caption.textContent, 'Все столбцы');
        assert.equal(page.separator.cells[0].colSpan, 1 + width * 3);
    });
}

test('all columns can be deselected while fuel labels remain visible; reset restores them', () => {
    const page = setup(2);
    page.button.fire('click');
    page.all.checked = false;
    page.all.fire('change');
    page.apply.fire('click');
    assert.deepEqual(page.heading.cells.map(cell => cell.hidden), [false, true, true, true]);
    assert.ok(page.data.cells.slice(1).every(cell => cell.hidden));
    assert.equal(page.data.cells[0].hidden, false);
    page.button.fire('click');
    page.reset.fire('click');
    assert.ok(page.data.cells.every(cell => !cell.hidden));
});

test('Escape cancels uncommitted changes', () => {
    const page = setup(2);
    page.button.fire('click');
    page.options[0].checked = false;
    page.document.fire('keydown', {key: 'Escape', preventDefault() {}});
    assert.equal(page.menu.hidden, true);
    assert.ok(page.data.cells.every(cell => !cell.hidden));
    page.button.fire('click');
    assert.ok(page.options.every(option => option.checked));
});

test('a filter opened in any table updates all tables and their buttons', () => {
    const page = setup(1, {extraWidths: [1, 1, 1]});
    page.tables[2].button.fire('click');
    page.options[1].checked = false;
    page.apply.fire('click');
    for (const table of page.tables) {
        assert.deepEqual(table.data.cells.map(cell => cell.hidden), [false, false, true, false]);
        assert.equal(table.caption.textContent, 'Выбрано: 2');
        assert.equal(table.separator.cells[0].colSpan, 3);
        assert.equal(table.button['aria-expanded'], 'false');
    }
    page.tables[3].button.fire('click');
    assert.deepEqual(page.options.map(option => option.checked), [true, false, true]);
    assert.equal(page.tables[3].button['aria-expanded'], 'true');
    page.button.fire('click');
    assert.equal(page.tables[3].button['aria-expanded'], 'false');
    assert.equal(page.button['aria-expanded'], 'true');
    page.reset.fire('click');
    for (const table of page.tables) {
        assert.ok(table.data.cells.every(cell => !cell.hidden));
        assert.equal(table.caption.textContent, 'Все столбцы');
    }
});

test('selection persists between summary tabs with different column layouts and resets globally', () => {
    const stored = new Map();
    const storageKey = 'ecology.calculation_summary.territories';
    const first = setup(1, {extraWidths: [1, 1, 1], storageKey, stored});
    first.tables[1].button.fire('click');
    first.options[0].checked = false;
    first.options[1].checked = false;
    first.apply.fire('click');
    for (const width of [6, 1, 6, 1]) {
        const page = setup(width, {storageKey, stored});
        assert.deepEqual(page.data.cells.map(cell => cell.hidden), [
            false, ...Array(width * 2).fill(true), ...Array(width).fill(false)
        ]);
        assert.equal(page.caption.textContent, 'Выбрано: 1');
        page.button.fire('click');
        assert.deepEqual(page.options.map(option => option.checked), [false, false, true]);
    }
    const last = setup(1, {storageKey, stored});
    last.button.fire('click');
    last.reset.fire('click');
    assert.equal(stored.has(storageKey), false);
    assert.ok(setup(6, {storageKey, stored}).data.cells.every(cell => !cell.hidden));
});

test('an empty selection is preserved, while cancelling changes does not save them', () => {
    const stored = new Map();
    const storageKey = 'summary';
    const page = setup(1, {storageKey, stored});
    page.button.fire('click');
    page.all.checked = false;
    page.all.fire('change');
    page.apply.fire('click');
    assert.equal(stored.get(storageKey), '[]');
    const next = setup(6, {storageKey, stored});
    assert.equal(next.data.cells[0].hidden, false);
    assert.ok(next.data.cells.slice(1).every(cell => cell.hidden));
    assert.equal(next.separator.cells[0].colSpan, 1);
    next.button.fire('click');
    next.all.checked = true;
    next.all.fire('change');
    next.document.fire('keydown', {key: 'Escape', preventDefault() {}});
    assert.equal(stored.get(storageKey), '[]');
    assert.ok(next.data.cells.slice(1).every(cell => cell.hidden));
});

test('saved selection is scoped to summary pages and unknown territories are ignored', () => {
    const stored = new Map([['summary', '["ural","removed"]']]);
    const source = setup(6, {stored});
    assert.ok(source.data.cells.every(cell => !cell.hidden));
    const summary = setup(1, {storageKey: 'summary', stored});
    assert.deepEqual(summary.data.cells.map(cell => cell.hidden), [false, true, true, false]);
    assert.equal(summary.caption.textContent, 'Выбрано: 1');
});

for (const saved of ['invalid json', '{}', '[1]']) {
    test(`invalid saved selection falls back to all columns: ${saved}`, () => {
        const page = setup(1, {storageKey: 'summary', stored: new Map([['summary', saved]])});
        assert.ok(page.data.cells.every(cell => !cell.hidden));
        assert.equal(page.caption.textContent, 'Все столбцы');
    });
}

test('filter remains usable when browser storage is unavailable', () => {
    const denied = () => { const error = new Error('Storage denied'); error.name = 'SecurityError'; throw error; };
    const page = setup(1, {storageKey: 'summary', localStorage: {getItem: denied, setItem: denied}});
    page.button.fire('click');
    page.options[1].checked = false;
    page.apply.fire('click');
    assert.deepEqual(page.data.cells.map(cell => cell.hidden), [false, false, true, false]);
    assert.equal(page.warnings.length, 2);
});
