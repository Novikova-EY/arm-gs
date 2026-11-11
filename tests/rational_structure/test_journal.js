const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/static/js/rational_structure/journal.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function element(properties = {}) {
    const handlers = {};
    return Object.assign({
        disabled: false, hidden: false, textContent: '',
        addEventListener: (event, handler) => { handlers[event] = handler; },
        emit: event => handlers[event]?.(),
    }, properties);
}

function fixture(responses) {
    const rows = [];
    const body = {
        appendChild: row => rows.push(row),
        replaceChildren: () => { rows.length = 0; },
    };
    const table = { tBodies: [body] };
    const button = element();
    const events = element({ checked: false });
    const status = element();
    const journal = element({ open: false, dataset: { logsUrl: '/rational_structure/logs' },
        querySelector: selector => ({ table, '.rs-journal-more': button,
            '.rs-journal-page-events': events, '.rs-journal-status': status })[selector],
    });
    const calls = [];
    vm.runInNewContext(source, {
        document: {
            addEventListener: (event, handler) => handler(),
            querySelector: () => journal,
        },
        window: { location: { origin: 'http://localhost' } },
        URL,
        ChangeLogTable: { rowFromLog: log => log, applyFilters: () => {} },
        fetch: async url => {
            calls.push(new URL(url));
            const result = responses.shift();
            if (result instanceof Error) throw result;
            return { ok: true, json: async () => result };
        },
    });
    return { rows, button, events, status, calls, journal,
        open() { journal.open = true; journal.emit('toggle'); },
    };
}

test('journal loads lazily and requests the next page without duplicating rows', async () => {
    const ui = fixture([
        { logs: [{ action: 'Первое' }, { action: 'Второе' }], has_more: true },
        { logs: [{ action: 'Третье' }], has_more: false },
    ]);
    assert.equal(ui.calls.length, 0);
    ui.open();
    assert.equal(ui.button.disabled, true);
    await tick();
    assert.deepEqual(ui.rows.map(row => row.action), ['Первое', 'Второе']);
    assert.equal(ui.button.hidden, false);
    ui.button.emit('click');
    await tick();
    assert.equal(ui.calls[1].searchParams.get('offset'), '2');
    assert.equal(ui.rows.length, 3);
    assert.equal(ui.button.hidden, true);
    ui.open();
    await tick();
    assert.equal(ui.calls.length, 2);
});

test('showing visits resets pagination and replaces the previously shown entries', async () => {
    const ui = fixture([
        { logs: [{ action: 'Изменение' }], has_more: false },
        { logs: [{ action: 'Открыта страница' }], has_more: false },
    ]);
    ui.open();
    await tick();
    ui.events.checked = true;
    ui.events.emit('change');
    await tick();
    assert.equal(ui.calls[1].searchParams.get('offset'), '0');
    assert.equal(ui.calls[1].searchParams.get('show_page_events'), 'true');
    assert.deepEqual(ui.rows.map(row => row.action), ['Открыта страница']);
});

test('a failed request can be retried without losing rows or advancing the offset', async () => {
    const ui = fixture([
        { logs: [{ action: 'Сохраненная запись' }], has_more: true },
        new Error('network failure'),
        { logs: [{ action: 'Следующая запись' }], has_more: false },
    ]);
    ui.open();
    await tick();
    ui.button.emit('click');
    await tick();
    assert.equal(ui.rows.length, 1);
    assert.match(ui.status.textContent, /Не удалось/);
    assert.equal(ui.button.disabled, false);
    ui.button.emit('click');
    await tick();
    assert.equal(ui.calls[2].searchParams.get('offset'), '1');
    assert.equal(ui.rows.length, 2);
    assert.equal(ui.button.hidden, true);
});
