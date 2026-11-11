const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function input(value) {
    return {
        tagName: 'INPUT',
        value,
        defaultValue: value,
        dataset: {},
        matches(selector) { return selector === 'input'; },
    };
}

function cell(raw, kind, shown, editable = false) {
    const target = editable ? input(shown) : null;
    return {
        dataset: {roundingValue: raw, roundingKind: kind},
        textContent: shown,
        querySelector() { return target; },
        target,
    };
}

function coefficient(raw, shown, editable = false) {
    const target = editable ? input(shown) : null;
    return {
        dataset: {roundingValue: raw},
        textContent: shown,
        matches(selector) { return selector === 'input' && editable; },
        target,
    };
}

function select(value) {
    let change;
    return {
        value,
        addEventListener(name, handler) { if (name === 'change') change = handler; },
        change(value) { this.value = value; change(); },
    };
}

function startRounding({cells, coefficients, numberValue = '1', coefficientValue = '2'}) {
    const numberSelect = select(numberValue);
    const coefficientSelect = select(coefficientValue);
    const hidden = [
        {name: 'rounding_digits', value: numberValue},
        {name: 'coefficient_rounding_digits', value: coefficientValue},
        {name: 'preserve_qs', value: 'start_year=2020'},
    ];
    const table = {
        dataset: {},
        querySelectorAll(selector) {
            if (selector === 'td.summary-year-cell[data-rounding-value]') return cells;
            if (selector === 'td.summary-year-cell[data-rounding-kind="graph_point"][data-rounding-value]') {
                return cells.filter(item => item.dataset.roundingKind === 'graph_point');
            }
            if (selector === '.lt-ei-rounding-coefficient[data-rounding-value]') return coefficients;
            return [];
        },
    };
    const urlChanges = [];
    const documentListeners = new Map();
    const window = {
        location: {href: 'http://127.0.0.1:5000/electrical_intensity/electrical_intensity_fo/?start_year=2020'},
        history: {state: null, replaceState(_state, _title, url) {
            this.url = url;
            window.location.href = url;
            urlChanges.push(url);
        }},
    };
    const document = {
        getElementById(id) {
            if (id === 'powerDemandSummaryTable') return table;
            if (id === 'rounding_digits') return numberSelect;
            if (id === 'coefficient_rounding_digits') return coefficientSelect;
            return null;
        },
        querySelectorAll(selector) {
            return selector === 'input[type="hidden"][name="rounding_digits"],input[type="hidden"][name="coefficient_rounding_digits"],input[type="hidden"][name="preserve_qs"]'
                ? hidden
                : selector === 'input[type="hidden"][name="rounding_digits"]' ? hidden.filter(field => field.name === 'rounding_digits')
                : selector === 'input[type="hidden"][name="coefficient_rounding_digits"]' ? hidden.filter(field => field.name === 'coefficient_rounding_digits')
                : selector === 'input[type="hidden"][name="preserve_qs"]' ? hidden.filter(field => field.name === 'preserve_qs')
                : hidden;
        },
        addEventListener(name, handler) { documentListeners.set(name, handler); },
    };
    vm.runInNewContext(fs.readFileSync('app/static/js/electrical_intensity/rounding.js', 'utf8'), {
        document, window, URL, BigInt,
    });
    return {numberSelect, coefficientSelect, hidden, table, window, urlChanges, documentListeners};
}

test('rounding selectors update displayed values and URL without a reload', () => {
    const intensity = cell('1234.56789', 'intensity', '1\u00a0234,6');
    const graphPoint = cell('1.234567891', 'graph_point', '1,234567891');
    const editable = cell('12.34567', 'intensity', '12,3', true);
    const coef = coefficient('0.123456789', '0,1235');
    const ui = startRounding({cells: [intensity, graphPoint, editable], coefficients: [coef]});
    assert.equal(coef.textContent, '0,12');

    ui.numberSelect.change('3');
    assert.equal(intensity.textContent, '1\u00a0234,568');
    assert.equal(editable.target.value, '12,346');
    assert.equal(editable.target.defaultValue, '12,346');
    assert.equal(graphPoint.textContent, '1,23');
    assert.match(ui.window.history.url, /rounding_digits=3/);

    ui.coefficientSelect.change('2');
    assert.equal(coef.textContent, '0,12');
    assert.match(ui.window.history.url, /coefficient_rounding_digits=2/);
    assert.equal(ui.urlChanges.length, 2);
    assert.equal(ui.hidden.find(field => field.name === 'rounding_digits').value, '3');
    assert.equal(ui.hidden.find(field => field.name === 'coefficient_rounding_digits').value, '2');
    assert.match(ui.hidden.find(field => field.name === 'preserve_qs').value, /rounding_digits=3/);
    assert.match(ui.hidden.find(field => field.name === 'preserve_qs').value, /coefficient_rounding_digits=2/);
});

test('coefficient precision rounds graph-point X values independently of ordinary values', () => {
    const graphPoint = cell('0.08816372', 'graph_point', '0,08816372', true);
    const ui = startRounding({cells: [graphPoint], coefficients: []});

    assert.equal(graphPoint.target.value, '0,09');
    ui.coefficientSelect.change('3');
    assert.equal(graphPoint.target.value, '0,088');

    ui.numberSelect.change('5');
    assert.equal(graphPoint.target.value, '0,088');

    graphPoint.dataset.roundingValue = '0.7654321';
    graphPoint.target.value = '0,7654321';
    graphPoint.target.dataset.roundingRenderedValue = graphPoint.target.value;
    ui.documentListeners.get('lt-ei-graph-points-rendered')();
    assert.equal(graphPoint.target.value, '0,765');
});

test('changing precision leaves unsaved user edits untouched', () => {
    const editableCell = cell('12.34567', 'intensity', '12,3', true);
    const editableGraphPoint = cell('0.123456', 'graph_point', '0,12', true);
    const editableCoefficient = coefficient('0.123456', '0,1235', true);
    const ui = startRounding({cells: [editableCell, editableGraphPoint], coefficients: [editableCoefficient]});
    editableCell.target.value = '99,9';
    editableGraphPoint.target.value = '0,7777';
    editableCoefficient.target.value = '0,7777';

    ui.numberSelect.change('2');
    ui.coefficientSelect.change('3');

    assert.equal(editableCell.target.value, '99,9');
    assert.equal(editableGraphPoint.target.value, '0,7777');
    assert.equal(editableCoefficient.target.value, '0,7777');
    assert.equal(editableCell.target.defaultValue, '12,3');
    assert.equal(editableCoefficient.target.defaultValue, '0,1235');
});

test('electrical-intensity page loads the dynamic formatter, not a reload handler', () => {
    const source = fs.readFileSync('app/templates/electrical_intensity/electrical_intensity.html', 'utf8');
    assert.match(source, /electrical_intensity\/rounding\.js[^\n]+defer/);
    assert.doesNotMatch(source, /roundingSel\.addEventListener/);
    assert.doesNotMatch(source, /window\.location\.href\s*=\s*url\.toString\(\)/);
});

test('rounding controls retain exact values for unrounded and integer modes', () => {
    const cellValue = cell('-0.5005', 'reference', '0');
    const coefficientValue = coefficient('1.2300', '1,23');
    const ui = startRounding({cells: [cellValue], coefficients: [coefficientValue]});

    ui.numberSelect.change('-1');
    assert.equal(cellValue.textContent, '-1');
    ui.coefficientSelect.change('0');
    assert.equal(coefficientValue.textContent, '1,23');
});
