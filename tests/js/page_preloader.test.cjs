const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../../app/templates/base.html'), 'utf8');
const source = template.match(/<script>\s*(\(function \(\) \{\s*const preloader =[\s\S]*?)<\/script>/)[1];

function page(readyState = 'loading') {
    const windowEvents = new Map();
    const documentEvents = new Map();
    const formEvents = new Map();
    const bodyEvents = new Map();
    const frames = [];
    const preloader = { style: { display: 'flex' } };
    vm.runInNewContext(source, {
        window: { addEventListener: (name, handler) => windowEvents.set(name, handler) },
        document: {
            readyState,
            getElementById: () => preloader,
            addEventListener: (name, handler) => documentEvents.set(name, handler),
            body: { addEventListener: (name, handler) => bodyEvents.set(name, handler) },
            querySelectorAll: () => [{ addEventListener: (name, handler) => formEvents.set(name, handler) }]
        },
        requestAnimationFrame: handler => frames.push(handler)
    });
    return {
        preloader, windowEvents, documentEvents, formEvents, bodyEvents,
        flushFrames() { frames.splice(0).forEach(handler => handler()); }
    };
}

test('reveals parsed content without waiting for images or window.load', () => {
    const current = page();
    current.documentEvents.get('DOMContentLoaded')?.();
    assert.equal(current.preloader.style.display, 'none');
});

for (const readyState of ['interactive', 'complete']) {
    test(`reveals content when initialized after DOM parsing (${readyState})`, () => {
        assert.equal(page(readyState).preloader.style.display, 'none');
    });
}

test('restoring from browser history hides the navigation overlay', () => {
    const current = page();
    current.windowEvents.get('pageshow')({ persisted: true });
    assert.equal(current.preloader.style.display, 'none');
});

test('form navigation shows the overlay unless submission was canceled', () => {
    const current = page();
    current.preloader.style.display = 'none';
    current.formEvents.get('submit')({ defaultPrevented: true });
    current.flushFrames();
    assert.equal(current.preloader.style.display, 'none');
    current.formEvents.get('submit')({ defaultPrevented: false });
    current.flushFrames();
    assert.equal(current.preloader.style.display, 'flex');
});

test('normal links show the overlay but new tabs and anchors do not', () => {
    const current = page();
    for (const [href, target, expected] of [['/generation', '', 'flex'], ['/generation', '_blank', 'none'], ['#section', '', 'none']]) {
        current.preloader.style.display = 'none';
        const link = { target, getAttribute: () => href, hasAttribute: () => false };
        current.bodyEvents.get('click')({ target: { closest: () => link } });
        current.flushFrames();
        assert.equal(current.preloader.style.display, expected);
    }
});
