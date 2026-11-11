const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/fuel/fuel_db_import.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function element(properties = {}) {
    const handlers = {};
    const classes = new Set();
    return Object.assign({
        hidden: true, textContent: '', innerHTML: 'Импорт из Excel', disabled: false,
        classList: {add: key => classes.add(key), remove: (...keys) => keys.forEach(key => classes.delete(key))},
        addEventListener: (event, handler) => { handlers[event] = handler; },
        emit: event => handlers[event]?.({preventDefault() {}}),
    }, properties);
}

function job(properties = {}) {
    return {id: 'job-1', status: 'running', detail: 'Обновление групп', filename: 'file.xlsx',
        database_version_id: 37, current: 25, total: 100, redirect_url: '/fuel/stations_equipment_groups?oes=311',
        error: null, result: null, ...properties};
}

function response(payload, {status = 200, redirected = false} = {}) {
    return {ok: status < 400, status, redirected, json: async () => payload};
}

function fixture(fetcher, {saved = null, initial = '', withForm = true} = {}) {
    const storage = new Map(saved ? [['fuel-db-import:7', saved]] : []);
    const timers = [];
    const calls = [];
    const button = element({type: 'button'});
    const input = element({files: [{name: 'file.xlsx'}], value: '', hasAttribute: () => true, click() {}});
    const form = element({action: '/upload', requestSubmit: () => form.emit('submit')});
    const status = element();
    const detail = element();
    const file = element();
    const progress = element();
    const result = element();
    const refresh = element();
    const collapse = element();
    const widget = {
        dataset: {owner: '7', initialJob: initial, activeUrl: '/active', statusUrl: '/status/JOB_ID'},
        closest: () => collapse,
        querySelector: selector => ({
            '#importFuelDbForm': withForm ? form : null, '#importFuelDbBtn': withForm ? button : null,
            '#importFuelDbFile': withForm ? input : null, '#fuelDbImportStatus': status,
            '[data-import-detail]': detail, '[data-import-file]': file,
            '[data-import-progress]': progress, '[data-import-result]': result, '[data-import-refresh]': refresh,
        })[selector],
    };
    class FormData {
        constructor(value) { this.form = value; }
    }
    vm.runInNewContext(source, {
        document: {getElementById: () => widget}, FormData, console,
        sessionStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
        window: {setTimeout: handler => timers.push(handler)},
        fetch: async (url, options) => { calls.push({url, options}); return fetcher(url, options); },
    });
    return {button, input, form, status, detail, file, progress, result, refresh, calls, timers, storage, widget};
}

test('upload is sent by AJAX, shows progress and keeps filters in the form', async () => {
    let uploaded = false;
    let finished = false;
    const ui = fixture(async url => {
        if (url === '/active') return response({ok: true, job: null});
        if (url === '/upload') { uploaded = true; return response({ok: true, job: job()}, {status: 202}); }
        return response({ok: true, job: finished ? job({status: 'done', result: {message: 'Обновлено 496 строк'}}) : job()});
    });
    await tick();
    assert.equal(ui.button.disabled, false);
    await ui.form.emit('submit');
    assert.equal(uploaded, true);
    assert.equal(ui.calls.find(call => call.url === '/upload').options.body.form, ui.form);
    assert.equal(ui.button.disabled, true);
    assert.match(ui.progress.textContent, /25 из 100/);
    assert.match(ui.file.textContent, /Версия БД: 37/);
    assert.equal(ui.storage.get('fuel-db-import:7'), 'job-1');
    await ui.form.emit('submit');
    assert.equal(ui.calls.filter(call => call.url === '/upload').length, 1);
    finished = true;
    await ui.timers.shift()();
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.result.textContent, 'Обновлено 496 строк');
    assert.equal(ui.refresh.href, '/fuel/stations_equipment_groups?oes=311');
    assert.equal(ui.refresh.hidden, false);
    assert.equal(ui.storage.size, 0);
});

test('reload resumes the existing active job without uploading a file again', async () => {
    const ui = fixture(async url => response({ok: true, job: job()}));
    await tick();
    assert.deepEqual(ui.calls.map(call => call.url), ['/active', '/status/job-1']);
    assert.equal(ui.button.disabled, true);
    assert.equal(ui.status.hidden, false);
    assert.equal(ui.timers.length, 1);
});

test('temporary polling failures do not enable a second import and recover', async () => {
    let attempts = 0;
    const ui = fixture(async url => {
        if (url === '/active') return response({ok: true, job: job()});
        if (++attempts === 1) throw new TypeError('network');
        return response({ok: true, job: job({status: 'done', result: {message: 'Готово'}})});
    });
    await tick();
    assert.equal(ui.button.disabled, true);
    assert.match(ui.detail.textContent, /не отменен/);
    await ui.timers.shift()();
    assert.equal(ui.result.textContent, 'Готово');
    assert.equal(ui.button.disabled, false);
});

test('a lost upload acknowledgement checks the active job rather than resending', async () => {
    let submitted = false;
    const ui = fixture(async url => {
        if (url === '/active') return response({ok: true, job: submitted ? job() : null});
        if (url === '/upload') { submitted = true; throw new TypeError('connection reset'); }
        return response({ok: true, job: job()});
    });
    await tick();
    await ui.form.emit('submit');
    assert.match(ui.detail.textContent, /Проверяем задание/);
    assert.equal(ui.button.disabled, true);
    await ui.timers.shift()();
    assert.equal(ui.calls.filter(call => call.url === '/upload').length, 1);
    assert.equal(ui.progress.textContent, 'На текущем этапе: 25 из 100');
});

test('worker errors display text safely and allow another upload', async () => {
    const ui = fixture(async () => response({ok: true, job: job({status: 'error', error: '<img src=x>Ошибка Excel'})}));
    await tick();
    assert.equal(ui.result.textContent, '<img src=x>Ошибка Excel');
    assert.equal(ui.refresh.hidden, true);
    assert.equal(ui.button.disabled, false);
});

test('an expired stored job is cleared without an endless recovery loop', async () => {
    const ui = fixture(async url => url === '/active'
        ? response({ok: true, job: null}) : {...response({}, {status: 404}), json: async () => { throw new SyntaxError('HTML 404 page'); }},
        {initial: 'old-job'});
    await tick();
    await tick();
    assert.equal(ui.calls.length, 3);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.storage.size, 0);
    assert.equal(ui.timers.length, 0);
});

test('the standalone status page can finish without upload form elements', async () => {
    const ui = fixture(async url => response({ok: true, job: url === '/active' ? null : job({status: 'done', result: {message: 'Готово'}})}),
        {initial: 'job-1', withForm: false});
    await tick();
    assert.equal(ui.result.textContent, 'Готово');
    assert.equal(ui.refresh.hidden, false);
});
