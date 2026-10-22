const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../../app/templates/ecology/analysis/gis_tes_fuel_comparison.html'), 'utf8');
const keys = ['normir_ZV_na_energ', 'normir_TVERD_na_energ', 'normir_SO2_na_energ', 'normir_NOx_na_energ'];

function setup(values, {slug = 'zv-vse', displayed = values} = {}) {
    const cells = Object.fromEntries(keys.map((key, index) => {
        const classes = new Set();
        return [key, {
            title: values[index] ?? '',
            textContent: displayed[index] ?? '',
            classList: {
                toggle(name, active) { active ? classes.add(name) : classes.delete(name); },
                contains(name) { return classes.has(name); }
            },
            querySelector() { return null; },
            removeAttribute(name) { if (name === 'title') this.title = ''; }
        }];
    }));
    const tr = {querySelector(selector) { return cells[selector.match(/data-col-key="([^"]+)"/)[1]] ?? null; }};
    const context = vm.createContext({table: {dataset: {sheetSlug: slug}}});
    const names = ['parseNum', 'formatNum', 'safeSum', 'validateZvEnergySum', 'applyRelatedValues'];
    const functions = names.map(name => {
        const start = template.indexOf('    const ' + name + ' = function');
        assert.notEqual(start, -1, name);
        const end = template.indexOf('\n    };', start) + '\n    };'.length;
        return template.slice(start, end);
    }).join('\n');
    vm.runInContext('const ROUNDING_CHOICES = [-1, 0, 1, 2, 3];\n' + functions +
        '\nglobalThis.validate = validateZvEnergySum; globalThis.apply = applyRelatedValues;', context);
    return {cells, total: cells[keys[0]], validate: () => context.validate(tr), apply: values => context.apply(tr, values)};
}

test('mismatch is red with ingredient sum and difference in the comment', () => {
    const row = setup(['10', '1', '2', '3']);
    row.validate();
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), true);
    assert.match(row.total.title, /^10\nНе совпадает/);
    assert.match(row.total.title, /твердое топливо \+ сера \+ азот = 6/);
    assert.match(row.total.title, /Разница \(значение − сумма\): 4/);
    assert.equal(row.total.textContent, '10');
});

test('matching sums, zero and floating point noise do not warn', () => {
    for (const values of [['6', '1', '2', '3'], ['0', '0', '0', '0'], ['0,3', '0,1', '0,2', '0'], ['1', '0,333333333333333', '0,333333333333333', '0,333333333333333']]) {
        const row = setup(values);
        row.validate();
        assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
        assert.equal(row.total.title, values[0]);
    }
});

test('full values are checked rather than independently rounded displays', () => {
    const matching = setup(['0,12', '0,04', '0,04', '0,04'], {displayed: ['0,1', '0', '0', '0']});
    matching.validate();
    assert.equal(matching.total.classList.contains('cmp-zv-sum-mismatch'), false);
    const different = setup(['0,14', '0,04', '0,04', '0,04'], {displayed: ['0,1', '0', '0', '0']});
    different.validate();
    assert.equal(different.total.classList.contains('cmp-zv-sum-mismatch'), true);
});

test('blank parts count as zero, but absent total or all parts do not warn', () => {
    for (const values of [['3', '', '1', '2'], ['', '1', '2', '3'], ['5', '', '', ''], ['', '', '', '']]) {
        const row = setup(values);
        row.validate();
        assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
    }
    const row = setup(['0', '', '1', '']);
    row.validate();
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), true);
});

test('Russian thousands separators are supported', () => {
    const row = setup(['1 234,5', '1\u00a0000', '200', '34,5']);
    row.validate();
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
});

test('other analysis pages are unaffected', () => {
    for (const slug of ['zv-bez-kot', 'pg-vse', 'pg-bez-kot']) {
        const row = setup(['10', '1', '2', '3'], {slug});
        row.validate();
        assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
        assert.equal(row.total.title, '10');
    }
});

test('saved related values refresh and clear warnings without reloading', () => {
    const row = setup(['10', '1', '2', '3']);
    row.validate();
    row.validate();
    assert.equal(row.total.title.match(/Не совпадает/g).length, 1);
    row.apply({normir_ZV_na_energ: {text: '6', title: '6'}});
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
    assert.equal(row.total.title, '6');
    row.apply({normir_SO2_na_energ: {text: '4', title: '4'}});
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), true);
    assert.match(row.total.title, /азот = 8/);
    row.apply({normir_SO2_na_energ: {text: '2', title: '2'}});
    assert.equal(row.total.classList.contains('cmp-zv-sum-mismatch'), false);
    assert.equal(row.total.title, '6');
});
