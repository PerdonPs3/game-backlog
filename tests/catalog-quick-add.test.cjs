const { test } = require('node:test');
const assert = require('node:assert/strict');
const { runInNewContext } = require('node:vm');
const { readFileSync } = require('node:fs');
const script = readFileSync('app/static/catalog-quick-add.js', 'utf8');
function setup(fetcher, url = '/account/form-token') {
    const feedback = { hidden: true }, token = { value: 'stale' };
    const form = { dataset: { tokenUrl: url }, attrs: {}, submitted: 0,
        querySelector: selector => selector === '[data-quick-feedback]' ? feedback : token,
        addEventListener(_, listener) { this.listener = listener; },
        setAttribute(key,value) { this.attrs[key] = value; }, removeAttribute(key) { delete this.attrs[key]; },
        requestSubmit(submitter) { const event = { submitter, prevented: false, preventDefault() { this.prevented = true; } }; this.listener(event); if (!event.prevented) this.submitted++; },
    };
    runInNewContext(script, { document: { querySelectorAll: () => [form] }, fetch: fetcher, AbortSignal: { timeout: () => 'timeout-signal' } });
    return { form, feedback, token, submit: () => form.listener({ submitter: {}, preventDefault() {} }) };
}
test('refreshes the same-origin token before one native submission and coalesces double clicks', async () => {
    let resolve, calls = 0;
    const ui = setup((url, options) => { calls++; assert.equal(url, '/account/form-token'); assert.equal(options.credentials, 'same-origin'); return new Promise(done => { resolve = done; }); });
    const pending = ui.submit(); await ui.submit(); assert.equal(calls, 1); assert.equal(ui.form.submitted, 0);
    resolve({ ok: true, json: async () => ({ csrf_token: 'fresh' }) }); await pending;
    assert.equal(ui.token.value, 'fresh'); assert.equal(ui.form.submitted, 1);
    assert.equal(ui.form.attrs['aria-busy'], undefined);
});
test('expired login and network errors leave an actionable message without posting', async () => {
    const ui = setup(async () => ({ ok: false, status: 401, json: async () => ({}) }));
    await ui.submit(); assert.equal(ui.form.submitted, 0); assert.match(ui.feedback.textContent, /sign in again/);
    const offline = setup(async () => { throw new Error('private connection details'); });
    await offline.submit(); assert.equal(offline.form.submitted, 0); assert.match(offline.feedback.textContent, /try again/); assert.doesNotMatch(offline.feedback.textContent, /private/);
});
test('offline single-user mode retains the normal form submission', () => {
    const ui = setup(() => { throw new Error('Must not fetch'); }, ''); assert.equal(ui.form.listener, undefined);
});
