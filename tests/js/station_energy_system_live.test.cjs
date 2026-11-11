const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const templatePath = path.join(
    __dirname,
    '../../app/templates/generation/stations/station_details.html'
);
const template = fs.readFileSync(templatePath, 'utf8');

function createEnergySystemUpdater({ resSelect, resAutoMap, elements }) {
    const start = template.indexOf('        function updateEnergySystemFromRes() {');
    const end = template.indexOf('\n        if (resSelect) {', start);
    assert.notEqual(start, -1, 'RES change handler should exist in the station template');
    assert.notEqual(end, -1, 'RES change handler should have a boundary in the station template');

    const source = template.slice(start, end);
    return new Function(
        'document',
        'resSelect',
        'resAutoMap',
        'setTimeout',
        `${source}; return updateEnergySystemFromRes;`
    )(
        { getElementById: id => elements[id] || null },
        resSelect,
        resAutoMap,
        () => 0
    );
}

test('regional energy system change updates OES and energy-system part immediately', () => {
    const elements = {
        union_energy_system: { innerText: 'не указано', style: {} },
        energy_system_type: { innerText: 'Децентрализованная зона', style: {} },
    };
    const resSelect = { value: '42' };
    const update = createEnergySystemUpdater({
        resSelect,
        elements,
        resAutoMap: {
            '0': {
                union_energy_system: 'не указано',
                energy_system_type: 'Децентрализованная зона',
            },
            '42': {
                union_energy_system: 'ОЭС Урала',
                energy_system_type: 'ЕЭС России',
            },
        },
    });

    update();

    assert.equal(elements.union_energy_system.innerText, 'ОЭС Урала');
    assert.equal(elements.energy_system_type.innerText, 'ЕЭС России');
});

test('selecting unspecified RES restores decentralized-zone label immediately', () => {
    const elements = {
        union_energy_system: { innerText: 'ОЭС Урала', style: {} },
        energy_system_type: { innerText: 'ЕЭС России', style: {} },
    };
    const resSelect = { value: '0' };
    const update = createEnergySystemUpdater({
        resSelect,
        elements,
        resAutoMap: {
            '0': {
                union_energy_system: 'не указано',
                energy_system_type: 'Децентрализованная зона',
            },
            '42': {
                union_energy_system: 'ОЭС Урала',
                energy_system_type: 'ЕЭС России',
            },
        },
    });

    update();

    assert.equal(elements.union_energy_system.innerText, 'не указано');
    assert.equal(elements.energy_system_type.innerText, 'Децентрализованная зона');
});
