const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/energy_balance/ee_generation_station_live.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness(fetch) {
  const handlers = {};
  const classes = new Set();
  const cell = {classList: {
    add: name => classes.add(name), remove: (...names) => names.forEach(name => classes.delete(name)),
  }};
  const input = {
    value: '', defaultValue: '', dataset: {stationId: '2', period: '2026'}, title: '',
    closest: selector => selector === 'td' ? cell : input,
    setAttribute() {}, removeAttribute() {},
  };
  const table = {
    dataset: {stationSaveUrl: '/save', csrf: 'csrf', periodMode: 'years', selectedYear: ''},
    addEventListener: (name, fn) => { handlers[name] = fn; }, querySelectorAll: () => [],
  };
  let timer;
  vm.runInNewContext(source, {
    document: {getElementById: () => table, activeElement: input},
    window: {location: {href: '/page'}},
    DOMParser: class {parseFromString() { return {querySelectorAll: () => []}; }},
    fetch, setTimeout: fn => { timer = fn; return 1; }, clearTimeout: () => { timer = null; },
  });
  return {input, classes, change: () => handlers.change({target: input, type: 'change'}),
    type: value => { input.value = value; handlers.input({target: input, type: 'input'}); },
    flush: () => timer(),
  };
}

function response(ok, payload) {
  return {ok, json: async () => payload, text: async () => ''};
}

test('debounced save sends the exact decimal text and marks success green', async () => {
  const calls = [];
  const h = harness(async (url, options) => {
    calls.push({url, options});
    return response(true, {ok: true});
  });
  h.type('123,1234567890123456');
  assert.equal(calls.length, 0);
  h.flush();
  await tick();
  assert.equal(JSON.parse(calls[0].options.body).value, '123,1234567890123456');
  assert.equal(calls[0].options.headers['X-CSRFToken'], 'csrf');
  assert(h.classes.has('is-save-success'));
  assert(!h.classes.has('is-save-error'));
  assert.equal(calls[1].url, '/page');
});

test('failed save is red, retains input and can be retried', async () => {
  let fail = true;
  const h = harness(async () => response(!fail, {ok: !fail, error: 'Rejected'}));
  h.type('-1'); h.change();
  await tick();
  assert(h.classes.has('is-save-error'));
  assert.equal(h.input.value, '-1');
  assert.equal(h.input.title, 'Rejected');
  fail = false;
  h.change();
  await tick();
  assert(h.classes.has('is-save-success'));
  assert(!h.classes.has('is-save-error'));
});

test('serializes changes while a request is running so an older value cannot win', async () => {
  let finish;
  const values = [];
  const h = harness(async (url, options) => {
    if (!options) return response(true, {});
    values.push(JSON.parse(options.body).value);
    if (values.length === 1) await new Promise(resolve => { finish = resolve; });
    return response(true, {ok: true});
  });
  h.type('1'); h.change();
  h.type('2'); h.change();
  assert.deepEqual(values, ['1']);
  finish();
  await tick();
  assert.deepEqual(values, ['1', '2']);
  assert(h.classes.has('is-save-success'));
});

test('a network error gives a red outline without losing the value', async () => {
  const h = harness(async () => { throw new Error('Network offline'); });
  h.type('5'); h.change();
  await tick();
  assert(h.classes.has('is-save-error'));
  assert.equal(h.input.value, '5');
});
