const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/rational_structure/calculated_values.js', 'utf8');

function panel(key) {
    const handlers = {};
    const attributes = {};
    const classes = new Set();
    const button = {
        dataset: {url: `/rational_structure/calculated_values/${key}`}, disabled: false,
        addEventListener: (event, handler) => { handlers[event] = handler; },
        click: () => handlers.click(),
    };
    const content = {
        innerHTML: `empty-${key}`,
        setAttribute: (key, value) => { attributes[key] = value; },
    };
    const status = {
        textContent: '',
        classList: {add: key => classes.add(key), remove: key => classes.delete(key)},
    };
    return {
        button, content, status, attributes, classes,
        querySelector: selector => ({
            '[data-load-results]': button,
            '[data-result-content]': content,
            '[data-result-status]': status,
        })[selector],
    };
}

function fixture(fetcher) {
    const panels = [panel('technologies'), panel('powers')];
    const calls = [];
    vm.runInNewContext(source, {
        document: {querySelectorAll: () => panels}, TypeError, SyntaxError,
        fetch: async (url, options) => {
            calls.push({url, options});
            return fetcher(url, options);
        },
    });
    return {panels, calls};
}

function response(payload, {ok = true, status = 200, contentType = 'application/json', redirected = false} = {}) {
    return {ok, status, redirected, headers: {get: () => contentType}, json: async () => payload};
}

test('tables do not request data until clicked; each button updates only its own table', async () => {
    const ui = fixture(async url => response({html: `<table>${url}</table>`}));
    assert.equal(ui.calls.length, 0);
    await ui.panels[0].button.click();
    assert.equal(ui.calls.length, 1);
    assert.equal(ui.calls[0].url, '/rational_structure/calculated_values/technologies');
    assert.equal(ui.calls[0].options.headers.Accept, 'application/json');
    assert.equal(ui.calls[0].options.credentials, 'same-origin');
    assert.equal(ui.calls[0].options.cache, 'no-store');
    assert.match(ui.panels[0].content.innerHTML, /technologies/);
    assert.equal(ui.panels[1].content.innerHTML, 'empty-powers');
    assert.match(ui.panels[0].status.textContent, /Таблица обновлена/);
    await ui.panels[1].button.click();
    assert.match(ui.panels[1].content.innerHTML, /powers/);
    assert.match(ui.panels[0].content.innerHTML, /technologies/);
});

test('loading disables repeated clicks but allows loading the other table concurrently', async () => {
    const pending = [];
    const ui = fixture(() => new Promise(resolve => pending.push(resolve)));
    const first = ui.panels[0].button.click();
    assert.equal(ui.panels[0].button.disabled, true);
    assert.equal(ui.panels[0].attributes['aria-busy'], 'true');
    assert.match(ui.panels[0].status.textContent, /Загрузка данных/);
    await ui.panels[0].button.click();
    assert.equal(ui.calls.length, 1);
    const second = ui.panels[1].button.click();
    assert.equal(ui.calls.length, 2);
    pending.forEach(resolve => resolve(response({html: 'loaded'})));
    await Promise.all([first, second]);
    for (const panel of ui.panels) {
        assert.equal(panel.button.disabled, false);
        assert.equal(panel.attributes['aria-busy'], 'false');
    }
});

test('API errors preserve existing data and allow a successful retry without duplicate rows', async () => {
    let count = 0;
    const ui = fixture(async () => ++count === 2
        ? response({error: 'API вернул ошибку HTTP 404.'}, {ok: false, status: 502})
        : response({html: `<table>result-${count}</table>`}));
    const table = ui.panels[0];
    await table.button.click();
    assert.equal(table.content.innerHTML, '<table>result-1</table>');
    await table.button.click();
    assert.equal(table.content.innerHTML, '<table>result-1</table>');
    assert.equal(table.classes.has('text-danger'), true);
    assert.match(table.status.textContent, /HTTP 404/);
    assert.equal(table.button.disabled, false);
    assert.equal(table.attributes['aria-busy'], 'false');
    await table.button.click();
    assert.equal(table.content.innerHTML, '<table>result-3</table>');
    assert.equal(table.classes.has('text-danger'), false);
});

for (const [name, fetcher, expected] of [
    ['network failure', async () => { throw new TypeError('Failed to fetch'); }, /Проверьте соединение/],
    ['login redirect', async () => response({}, {redirected: true}), /Сеанс завершен/],
    ['unauthorized', async () => response({}, {ok: false, status: 401}), /Сеанс завершен/],
    ['non-JSON response', async () => response({}, {contentType: 'text/html'}), /неожиданный ответ/],
    ['missing HTML', async () => response({}), /некорректные данные/],
    ['invalid JSON', async () => ({...response({}), json: async () => { throw new SyntaxError('Invalid JSON'); }}), /некорректный JSON/],
]) {
    test(`${name} does not replace a table and re-enables the button`, async () => {
        const ui = fixture(fetcher);
        const table = ui.panels[0];
        await table.button.click();
        assert.match(table.status.textContent, expected);
        assert.equal(table.content.innerHTML, 'empty-technologies');
        assert.equal(table.button.disabled, false);
        assert.equal(table.attributes['aria-busy'], 'false');
        assert.equal(table.classes.has('text-danger'), true);
        assert.equal(ui.panels[1].status.textContent, '');
    });
}
