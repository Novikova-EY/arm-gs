const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../app/static/js/ecology/tes_territory_filter.js'), 'utf8');

function element() {
    const listeners = {}, classes = new Set();
    return {
        hidden: false, checked: false, value: '', dataset: {}, style: {}, children: [],
        classList: {
            contains: name => classes.has(name),
            toggle(name, on) { on ? classes.add(name) : classes.delete(name); }
        },
        append(...children) {
            children.forEach(child => { child.parentElement = this; this.children.push(child); });
        },
        appendChild(child) { this.append(child); },
        get textContent() { return this.children.map(child => child.textContent).join(''); },
        setAttribute(name, value) { this[name] = value; },
        addEventListener(name, handler) { (listeners[name] ??= []).push(handler); },
        fire(name, event = {}) { (listeners[name] ?? []).forEach(handler => handler(event)); },
        focus() { this.focused = true; },
        contains(target) { return this === target || this.children.some(child => child.contains?.(target)); },
        getBoundingClientRect() { return {left: 10, bottom: 20}; },
        offsetWidth: 300, offsetHeight: 400
    };
}

function setup() {
    const all = element(), apply = element(), reset = element(), search = element(), values = element();
    const menu = Object.assign(element(), {hidden: true});
    menu.append(search, all, values, apply, reset);
    menu.querySelector = selector => ({
        '[data-fuel-values]': values, '[data-fuel-all]': all, '[data-fuel-search]': search,
        '[data-fuel-apply]': apply, '[data-fuel-reset]': reset
    })[selector];
    menu.querySelectorAll = () => values.children.map(label => label.children[0]);
    const tables = [0, 1, 2].map(index => {
        const rows = [['b', 'Всего'], ['gas', 'Природный газ'], ['coal', 'Уголь'],
            ...(index === 2 ? [['oil', 'Мазут']] : [])].map(([key, textContent]) => Object.assign(element(), {
            dataset: {rowKey: key}, cells: [{textContent}, {hidden: true, textContent: '123'}]
        }));
        const table = Object.assign(element(), {querySelectorAll: () => rows});
        const button = Object.assign(element(), {hidden: true, closest: () => table});
        const caption = {}, icon = {};
        button.querySelector = selector => selector === 'span' ? caption : icon;
        return {rows, button, table, caption};
    });
    const document = Object.assign(element(), {
        body: element(), createElement: element, createTextNode: textContent => ({textContent}),
        querySelectorAll: selector => selector === '[data-fuel-filter-button]' ? tables.map(t => t.button) : [],
        getElementById: id => id === 'otFuelFilterMenu' ? menu : null
    });
    const window = Object.assign(element(), {innerWidth: 1200, innerHeight: 800, dispatchEvent() {}});
    vm.runInNewContext(script, {document, window, Event: class {}});
    return {all, apply, reset, search, menu, tables, document, options: menu.querySelectorAll()};
}

test('fuel choices are deduplicated across all tables, including empty rows and extra fuels', () => {
    const page = setup();
    assert.deepEqual(page.options.map(option => option.value), ['b', 'gas', 'coal', 'oil']);
    assert.ok(page.tables.every(t => !t.button.hidden));
    page.tables[1].button.fire('click');
    page.options[1].checked = false;
    page.options[1].fire('change');
    assert.equal(page.all.indeterminate, true);
    assert.ok(page.tables.every(t => !t.rows[1].hidden), 'draft does not change rows');
    page.apply.fire('click');
    for (const {rows, caption, button} of page.tables) {
        assert.equal(rows[1].hidden, true);
        assert.equal(rows[0].hidden, false);
        assert.equal(rows[2].hidden, false);
        assert.ok(rows.every(row => row.cells[1].hidden), 'column filtering is preserved');
        assert.equal(rows[1].cells[1].textContent, '123', 'values are unchanged');
        assert.equal(caption.textContent, 'Выбрано: 3');
        assert.equal(button['aria-expanded'], 'false');
    }
    page.tables[0].button.fire('click');
    page.reset.fire('click');
    assert.ok(page.tables.every(t => t.rows.every(row => !row.hidden)));
    assert.equal(page.tables[0].caption.textContent, 'Все виды топлива');
});

test('search is case-insensitive, select-all changes matching options only', () => {
    const page = setup();
    page.tables[0].button.fire('click');
    page.search.value = '  ГАЗ  ';
    page.search.fire('input');
    assert.deepEqual(page.options.map(option => option.parentElement.hidden), [true, false, true, true]);
    page.all.checked = false;
    page.all.fire('change');
    assert.deepEqual(page.options.map(option => option.checked), [true, false, true, true]);
    page.search.value = 'несуществующее топливо';
    page.search.fire('input');
    assert.equal(page.all.checked, false);
    assert.equal(page.all.indeterminate, false);
    page.apply.fire('click');
    assert.ok(page.tables.every(t => t.rows[1].hidden));
    page.tables[0].button.fire('click');
    assert.equal(page.search.value, '');
    assert.ok(page.options.every(option => !option.parentElement.hidden));
});

test('Escape and outside click discard draft choices; empty selection can be reset', () => {
    const page = setup();
    page.tables[0].button.fire('click');
    page.all.checked = false;
    page.all.fire('change');
    page.document.fire('keydown', {key: 'Escape', preventDefault() {}});
    assert.equal(page.menu.hidden, true);
    page.tables[0].button.fire('click');
    assert.ok(page.options.every(option => option.checked));
    page.options[0].checked = false;
    page.document.fire('click', {target: element()});
    page.tables[1].button.fire('click');
    assert.ok(page.options.every(option => option.checked));
    page.all.checked = false;
    page.all.fire('change');
    page.apply.fire('click');
    assert.ok(page.tables.every(t => t.rows.every(row => row.hidden)));
    page.tables[2].button.fire('click');
    page.reset.fire('click');
    assert.ok(page.tables.every(t => t.rows.every(row => !row.hidden)));
});
