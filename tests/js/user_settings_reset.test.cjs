const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../../app/static/js/common/user_settings_reset.js'), 'utf8');

function storage(entries = {}) {
    const values = new Map(Object.entries(entries));
    return {
        get length() { return values.size; },
        key(index) { return Array.from(values.keys())[index]; },
        getItem(key) { return values.get(key) ?? null; },
        setItem(key, value) { values.set(key, value); },
        removeItem(key) { values.delete(key); }
    };
}

function run(local, session, token = 'reset-1', userId = '2') {
    vm.runInNewContext(source, {
        document: { getElementById() { return { textContent: JSON.stringify({ userId, token }) }; } },
        localStorage: local,
        sessionStorage: session,
        console: { warn() {} }
    });
}

test('clears only known display settings, preserving jobs and unrelated data', () => {
    const entries = {
        rounding_digits: '5',
        'pdEcSummaryNtDetail_oes': '1',
        powerDemandSummaryOesVisibleRowKeysV4: '[]',
        'armGs.ltEiRowGroupState:/intensity': '{}',
        'ecology.calculation_summary.territories': '[1]',
        'fuel-db-import:2': 'running-job',
        unrelated: 'keep',
        csrf_token: 'keep-token'
    };
    const local = storage(entries);
    const session = storage(entries);
    run(local, session);
    for (const area of [local, session]) {
        assert.equal(area.getItem('rounding_digits'), null);
        assert.equal(area.getItem('pdEcSummaryNtDetail_oes'), null);
        assert.equal(area.getItem('powerDemandSummaryOesVisibleRowKeysV4'), null);
        assert.equal(area.getItem('armGs.ltEiRowGroupState:/intensity'), null);
        assert.equal(area.getItem('ecology.calculation_summary.territories'), null);
        assert.equal(area.getItem('fuel-db-import:2'), 'running-job');
        assert.equal(area.getItem('unrelated'), 'keep');
        assert.equal(area.getItem('csrf_token'), 'keep-token');
    }
});

test('applies once per browser and per tab, then again for a new reset', () => {
    const local = storage({ rounding_digits: '5' });
    const firstTab = storage({ rounding_digits: '5' });
    run(local, firstTab);
    local.setItem('rounding_digits', '3');
    firstTab.setItem('rounding_digits', '4');
    run(local, firstTab);
    assert.equal(local.getItem('rounding_digits'), '3');
    assert.equal(firstTab.getItem('rounding_digits'), '4');
    const secondTab = storage({ rounding_digits: '6' });
    run(local, secondTab);
    assert.equal(local.getItem('rounding_digits'), '3');
    assert.equal(secondTab.getItem('rounding_digits'), null);
    run(local, firstTab, 'reset-2');
    assert.equal(local.getItem('rounding_digits'), null);
    assert.equal(firstTab.getItem('rounding_digits'), null);
});

test('does not reset another account without a command', () => {
    const local = storage({ rounding_digits: '5', 'armGs.settingsReset:2': 'reset-1' });
    const session = storage({ rounding_digits: '3' });
    run(local, session, '', '3');
    assert.equal(local.getItem('rounding_digits'), '5');
    assert.equal(session.getItem('rounding_digits'), '3');
});

test('blocked storage does not prevent the rest of the page from loading', () => {
    const blocked = { getItem() { throw new Error('storage disabled'); } };
    assert.doesNotThrow(() => run(blocked, blocked));
});
