const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/static/js/rational_structure/equipment_runtime.js', 'utf8');

function classList(initial = []) {
    const classes = new Set(initial);
    return {
        contains: name => classes.has(name),
        toggle(name, force = !classes.has(name)) {
            if (force) classes.add(name);
            else classes.delete(name);
            return force;
        },
    };
}

function setup(button) {
    vm.runInNewContext(source, {
        window: {},
        document: {
            getElementById: id => {
                assert.equal(id, 'rs-runtime-calculation-toggle');
                return button;
            },
        },
    });
}

test('calculation columns start hidden and toggle without submitting or persisting state', () => {
    const page = {
        classList: classList(['rs-runtime-results-hidden']),
    };
    const attributes = { 'aria-pressed': 'false' };
    let click;
    const button = {
        classList: classList(),
        closest: selector => {
            assert.equal(selector, '.rs-data-page');
            return page;
        },
        setAttribute: (name, value) => { attributes[name] = value; },
        addEventListener: (event, handler) => {
            assert.equal(event, 'click');
            click = handler;
        },
    };
    setup(button);
    assert.equal(page.classList.contains('rs-runtime-results-hidden'), true);
    assert.equal(button.classList.contains('active'), false);
    assert.equal(attributes['aria-pressed'], 'false');
    click();
    assert.equal(page.classList.contains('rs-runtime-results-hidden'), false);
    assert.equal(button.classList.contains('active'), true);
    assert.equal(attributes['aria-pressed'], 'true');
    click();
    assert.equal(page.classList.contains('rs-runtime-results-hidden'), true);
    assert.equal(button.classList.contains('active'), false);
    assert.equal(attributes['aria-pressed'], 'false');
});

test('summary and unrelated pages do not need a calculation button', () => {
    assert.doesNotThrow(() => setup(null));
});
