const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../../app/templates/ecology/operating_tes/operating_tes_table.html'), 'utf8');
const start = template.indexOf('    const emptyBtn =');
const end = template.indexOf('    const getFieldValue', start);
assert.notEqual(start, -1);
assert.notEqual(end, -1);

function classList(initial) {
    const names = new Set(initial);
    return {
        contains: name => names.has(name),
        toggle(name, on) { on ? names.add(name) : names.delete(name); }
    };
}

for (const count of [1, 3, 4]) {
    test(`empty-row toggle updates all ${count} tables without requiring a primary table`, () => {
        const tables = Array.from({length: count}, () => ({classList: classList(['ot-hide-empty'])}));
        let click;
        const button = {
            pressed: 'false', classList: classList(['btn-outline-primary']),
            getAttribute() { return this.pressed; },
            setAttribute(name, value) { this.pressed = value; },
            addEventListener(name, handler) { click = handler; }
        };
        const document = {
            getElementById: () => button,
            querySelectorAll: () => tables
        };
        vm.runInNewContext(template.slice(start, end), {document});
        for (const shown of [true, false, true]) {
            click();
            assert.equal(button.pressed, String(shown));
            assert.equal(button.classList.contains('btn-primary'), shown);
            assert.equal(button.classList.contains('btn-outline-primary'), !shown);
            for (const table of tables) assert.equal(table.classList.contains('ot-hide-empty'), !shown);
        }
    });
}
