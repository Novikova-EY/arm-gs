const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../app/static/js/rational_structure/sticky_table_toolbar.js'), 'utf8');

function mount(heights) {
    const pages = heights.map(height => ({
        toolbar: { height, getBoundingClientRect() { return { height: this.height }; } },
        style: { values: {}, setProperty(key, value) { this.values[key] = value; } },
        querySelector(selector) { assert.equal(selector, '.rs-table-toolbar'); return this.toolbar; },
    }));
    const observers = [];
    vm.runInNewContext(script, {
        document: { querySelectorAll(selector) { assert.equal(selector, '.rs-sticky-toolbar-page'); return pages; } },
        ResizeObserver: class {
            constructor(callback) { this.callback = callback; observers.push(this); }
            observe(element) { this.element = element; }
        },
    });
    return { pages, observers };
}

test('sets an independent header offset from each toolbar height', () => {
    const { pages, observers } = mount([56, 92.5]);
    assert.equal(pages[0].style.values['--rs-table-toolbar-height'], '56px');
    assert.equal(pages[1].style.values['--rs-table-toolbar-height'], '92.5px');
    assert.equal(observers[0].element, pages[0].toolbar);
});

test('updates the offset when controls wrap or fonts change', () => {
    const { pages, observers } = mount([56]);
    pages[0].toolbar.height = 140;
    observers[0].callback();
    assert.equal(pages[0].style.values['--rs-table-toolbar-height'], '140px');
    pages[0].toolbar.height = 56;
    observers[0].callback();
    assert.equal(pages[0].style.values['--rs-table-toolbar-height'], '56px');
});

test('does not observe unrelated pages', () => {
    assert.equal(mount([]).observers.length, 0);
});
