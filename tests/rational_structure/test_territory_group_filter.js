const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
    constructor(dataset = {}) {
        this.dataset = dataset;
        this.children = [];
        this.handlers = {};
        this.attributes = {};
        this.hidden = false;
        this.checked = true;
        this.value = '';
        const classes = new Set();
        this.classList = {
            toggle(name, active) { if (active) classes.add(name); else classes.delete(name); },
            contains: name => classes.has(name),
        };
    }
    append(...children) { this.children.push(...children); }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    emit(name) { this.handlers[name]?.({currentTarget: this}); }
    click() { this.emit('click'); }
    getAttribute(name) { return this.attributes[name]; }
    setAttribute(name, value) { this.attributes[name] = value; }
    querySelector() { return null; }
    querySelectorAll() { return this.children; }
}

function fixture({extraGroup = false, metrics = false} = {}) {
    const controls = Object.fromEntries(['toggle', 'search', 'all', 'options', 'status', 'apply', 'reset']
        .map(name => [name, new Element()]));
    const filter = new Element();
    filter.querySelector = selector => controls[selector.slice('[data-equipment-filter-'.length, -1)];
    const emptyButton = new Element();
    emptyButton.setAttribute('aria-pressed', 'true');
    const rows = [];
    for (const block of ['b0', 'b1', 'b2', 'b3', 'check']) {
        for (const [id, label, raw, rollup] of [
            ['1', 'Группа А', '0', undefined], ['2', 'Группа Б', '5', undefined],
            [undefined, 'Без группы', '95', undefined], [undefined, 'Всего', '100', 'block'],
            [undefined, 'ТЭС', '100', 'type'], [undefined, 'АЭС', '0', 'type'],
            [undefined, 'ГЭС', '', 'type'],
        ]) {
            const row = new Element({equipmentBlock: block, equipmentFilterGroup: id,
                equipmentFilterLabel: label, equipmentRollup: rollup, equipmentUnit: 'МВт',
                equipmentGroup: ['Группа А', 'Группа Б', 'Без группы', 'ТЭС'].includes(label) ? `${block}_tes` : `${block}_${label}`,
                equipmentGenerationType: label === 'ТЭС' ? 'ТЭС' : label});
            row.append(new Element({rawValue: raw}));
            rows.push(row);
        }
        if (extraGroup) {
            const row = new Element({equipmentBlock: block, equipmentFilterGroup: '3', equipmentFilterLabel: 'Группа В',
                equipmentUnit: 'МВт', equipmentGroup: `${block}_tes`});
            row.append(new Element({rawValue: '10'}));
            rows.push(row);
        }
    }
    if (metrics) {
        for (const block of ['b0', 'b1', 'b2', 'b3', 'check']) {
            const originals = rows.filter(row => row.dataset.equipmentBlock === block);
            for (const original of originals.filter(row => row.dataset.equipmentFilterGroup || row.dataset.equipmentGenerationType === 'ТЭС')) {
                const count = new Element({...original.dataset, equipmentUnit: 'шт'});
                count.append(new Element({rawValue: original.dataset.equipmentFilterGroup === '1' ? '2' : '3'}));
                rows.push(count);
            }
            for (const unit of ['МВт', 'шт']) {
                const thermal = new Element({equipmentBlock: block, equipmentUnit: unit,
                    equipmentRollup: 'thermal', equipmentGroup: `${block}_thermal`, equipmentFilterLabel: 'Все ТЭС'});
                thermal.append(new Element({rawValue: '100'}));
                rows.push(thermal);
            }
            const storage = originals.find(row => row.dataset.equipmentFilterLabel === 'ГЭС');
            storage.children[0].dataset.rawValue = '50';
            storage.children[0].textContent = '50,0';
            storage.children[0].title = '50';
        }
    }
    const checks = rows.filter(row => row.dataset.equipmentBlock === 'check');
    const sources = ['b0', 'b1', 'b2', 'b3'].map(block => rows.filter(row => row.dataset.equipmentBlock === block));
    sources.forEach((block, blockIndex) => block.forEach((row, index) => { row.dataset.equipmentRowKey = `${blockIndex}_${index}`; }));
    checks.forEach((row, index) => {
        row.dataset.equipmentCheckSources = JSON.stringify(sources.map(block => block[index].dataset.equipmentRowKey));
        if (row.dataset.equipmentRollup) row.dataset.equipmentRollup = row.dataset.equipmentRollup === 'block' ? 'verification' : 'verification_type';
        delete row.dataset.equipmentGroup;
    });
    const editor = new Element();
    editor.dataset.rounding = '1';
    editor.querySelector = selector => ({'[data-equipment-filter]': filter, '#territory-empty-rows': emptyButton})[selector] || null;
    editor.querySelectorAll = selector => ({
        '[data-equipment-block]': rows,
        '[data-equipment-filter-group]': rows.filter(row => row.dataset.equipmentFilterGroup),
        '[data-value-row]': rows.filter(row => !row.dataset.equipmentRollup),
        '[data-equipment-group]': rows.filter(row => row.dataset.equipmentGroup),
        '[data-equipment-rollup]': rows.filter(row => row.dataset.equipmentRollup),
        '[data-equipment-row-key]': rows.filter(row => row.dataset.equipmentRowKey),
        '[data-equipment-check-sources]': checks,
    })[selector] || [];
    vm.runInNewContext(fs.readFileSync('app/static/js/rational_structure/territory_cells.js', 'utf8'), {
        document: {querySelector: () => editor, createElement: () => new Element()},
        window: {addEventListener() {}}, Intl,
    });
    const choose = ids => {
        filter.emit('show.bs.dropdown');
        controls.options.children.forEach((label, index) => { label.children[0].checked = ids.includes(String(index + 1)); });
        controls.apply.click();
    };
    return {controls, rows, filter, emptyButton, choose};
}

const excluded = row => row.classList.contains('territory-group-filter-hidden');

test('one zero group applies to all blocks and verification, keeping its rows and hiding recalculated zero totals', () => {
    const ui = fixture();
    assert.equal(ui.controls.options.children.length, 2);
    ui.choose(['1']);
    for (const block of ['b0', 'b1', 'b2', 'b3', 'check']) {
        const rows = ui.rows.filter(row => row.dataset.equipmentBlock === block);
        assert.deepEqual(rows.map(excluded), [false, true, true, true, true, true, true]);
        assert.equal(Number(rows[3].children[0].dataset.rawValue), 0);
    }
    ui.emptyButton.click();
    assert.ok(ui.rows.filter(row => row.dataset.equipmentFilterGroup === '1').every(row => !row.hidden));
    assert.equal(ui.controls.status.textContent, '1');
});

test('multiple groups, no groups and reset restore the appropriate rows without changing other visibility classes', () => {
    const ui = fixture({extraGroup: true});
    const row = ui.rows[0];
    for (const name of ['territory-count-hidden', 'territory-transfer-hidden', 'territory-verification-hidden']) {
        row.classList.toggle(name, true);
    }
    ui.choose([]);
    assert.ok(ui.rows.filter(row => !row.dataset.equipmentRollup).every(excluded));
    ui.choose(['1', '2']);
    assert.equal(ui.controls.status.textContent, '2');
    assert.ok(ui.rows.filter(row => ['1', '2'].includes(row.dataset.equipmentFilterGroup)).every(row => !excluded(row)));
    assert.ok(ui.rows.filter(row => row.dataset.equipmentFilterGroup === '3').every(excluded));
    ui.choose(['1', '2', '3']);
    assert.ok(ui.rows.every(row => !excluded(row)));
    ui.choose(['2']);
    ui.controls.reset.click();
    assert.ok(ui.rows.every(row => !excluded(row)));
    assert.equal(ui.controls.status.textContent, '');
    for (const name of ['territory-count-hidden', 'territory-transfer-hidden', 'territory-verification-hidden']) {
        assert.ok(row.classList.contains(name));
    }
    ui.filter.emit('show.bs.dropdown');
    assert.ok(ui.controls.options.children.every(label => label.children[0].checked));
});

test('search is case insensitive, select all affects only found groups, reopening discards unapplied changes', () => {
    const ui = fixture();
    ui.filter.emit('show.bs.dropdown');
    ui.controls.all.checked = false;
    ui.controls.all.emit('change');
    ui.controls.search.value = ' группа б ';
    ui.controls.search.emit('input');
    assert.deepEqual(ui.controls.options.children.map(label => label.hidden), [true, false]);
    ui.controls.all.checked = true;
    ui.controls.all.emit('change');
    ui.controls.apply.click();
    assert.ok(ui.rows.filter(row => row.dataset.equipmentFilterGroup === '1').every(excluded));
    assert.ok(ui.rows.filter(row => row.dataset.equipmentFilterGroup === '2').every(row => !excluded(row)));
    ui.controls.options.children[0].children[0].checked = true;
    ui.filter.emit('show.bs.dropdown');
    assert.equal(ui.controls.search.value, '');
    assert.deepEqual(ui.controls.options.children.map(label => label.children[0].checked), [false, true]);
});

function findRow(ui, block, label, unit = 'МВт') {
    return ui.rows.find(row => row.dataset.equipmentBlock === block
        && row.dataset.equipmentFilterLabel === label && row.dataset.equipmentUnit === unit);
}

const raw = row => row.children[0].dataset.rawValue;

test('filtered totals sum selected groups exactly by year and unit, including thermal totals and signed verification', () => {
    const ui = fixture({extraGroup: true, metrics: true});
    for (const [index, block] of ['b0', 'b1', 'b2', 'b3'].entries()) {
        const first = findRow(ui, block, 'Группа А');
        const second = findRow(ui, block, 'Группа Б');
        first.children[0].dataset.rawValue = ['0.1', '0', '0', '0.1'][index];
        second.children[0].dataset.rawValue = ['0.2', '0.01', '0.02', '0.1'][index];
        first.append(new Element({rawValue: '0.0000000001'}));
        second.append(new Element({rawValue: '0.0000000002'}));
        for (const row of ui.rows.filter(row => row.dataset.equipmentBlock === block
            && row.dataset.equipmentUnit === 'МВт' && row !== first && row !== second)) {
            row.append(new Element({rawValue: '100'}));
        }
    }
    for (const row of ui.rows.filter(row => row.dataset.equipmentBlock === 'check' && row.dataset.equipmentUnit === 'МВт')) {
        row.append(new Element({rawValue: '0'}));
    }
    ui.choose(['1', '2']);
    for (const [index, block] of ['b0', 'b1', 'b2', 'b3'].entries()) {
        for (const label of ['ТЭС', 'Все ТЭС', 'Всего']) {
            const summary = findRow(ui, block, label);
            assert.equal(raw(summary), ['0.3', '0.01', '0.02', '0.2'][index]);
            assert.equal(summary.children[1].dataset.rawValue, '0.0000000003');
        }
        for (const label of ['ТЭС', 'Все ТЭС']) {
            const count = findRow(ui, block, label, 'шт');
            assert.equal(raw(count), '5');
            assert.equal(count.children[0].textContent, '5');
        }
        assert.equal(raw(findRow(ui, block, 'ГЭС')), '');
        assert.ok(excluded(findRow(ui, block, 'ГЭС')));
    }
    for (const label of ['ТЭС', 'Все ТЭС', 'Всего']) {
        const check = findRow(ui, 'check', label);
        assert.equal(raw(check), '0.07');
        assert.equal(check.children[1].dataset.rawValue, '-0.0000000006');
        assert.ok(check.children[0].classList.contains('territory-verification-error'));
    }
    assert.equal(raw(findRow(ui, 'check', 'Все ТЭС', 'шт')), '-10');
    assert.equal(raw(findRow(ui, 'b0', 'Группа В')), '10');
});

test('changing selection does not accumulate sums and reset restores full totals including types without group leaves', () => {
    const ui = fixture({extraGroup: true, metrics: true});
    ui.choose(['2']);
    assert.equal(raw(findRow(ui, 'b0', 'Всего')), '5');
    assert.equal(raw(findRow(ui, 'b0', 'ГЭС')), '');
    ui.choose(['3']);
    assert.equal(raw(findRow(ui, 'b0', 'Всего')), '10');
    ui.choose([]);
    assert.ok(ui.rows.filter(row => row.dataset.equipmentRollup).every(excluded));
    ui.controls.reset.click();
    for (const block of ['b0', 'b1', 'b2', 'b3']) {
        assert.equal(raw(findRow(ui, block, 'ГЭС')), '50');
        assert.equal(findRow(ui, block, 'ГЭС').children[0].textContent, '50,0');
        assert.equal(findRow(ui, block, 'ГЭС').children[0].title, '50');
        assert.equal(raw(findRow(ui, block, 'ТЭС')), '110');
        assert.equal(raw(findRow(ui, block, 'Все ТЭС')), '110');
        assert.equal(raw(findRow(ui, block, 'Всего')), '160');
    }
    assert.equal(raw(findRow(ui, 'check', 'Всего')), '-320');
    ui.choose(['2']);
    ui.choose(['1', '2', '3']);
    assert.equal(raw(findRow(ui, 'b0', 'Всего')), '160');
});
