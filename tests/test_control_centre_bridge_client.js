const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync('ddlc-control-centre-integrated.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function extractBridgeFetch() {
  const start = script.indexOf('async function bridgeFetch(');
  assert.notEqual(start, -1);
    const open = script.indexOf('){', start) + 1;
  let depth = 0;
  for (let index = open; index < script.length; index++) {
    if (script[index] === '{') depth++;
    if (script[index] === '}' && --depth === 0) return script.slice(start, index + 1);
  }
  throw new Error('bridgeFetch has no closing brace');
}

const bridgeFetchSource = extractBridgeFetch();

function makeClient({ fileMode = false, timedOut = false } = {}) {
  const controller = {
    signal: { aborted: false },
    abort() { this.signal.aborted = true; },
  };
  const context = {
    FILE_MODE: fileMode,
    BRIDGE_ORIGIN: 'http://127.0.0.1:8765',
    BRIDGE_TOKEN: fileMode ? '__DDLC_CC_TOKEN__' : 'private-test-token',
    AbortController: function AbortController() { return controller; },
    setTimeout(callback) { if (timedOut) callback(); return 1; },
    clearTimeout() {},
    fetch(_url, options) {
      if (options.signal.aborted) return Promise.reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
      return Promise.resolve({ ok: true });
    },
  };
  return vm.runInNewContext(`(${bridgeFetchSource})`, context);
}

test('file mode rejects bridge calls with a setup message before network access', async () => {
  await assert.rejects(makeClient({ fileMode: true })('/status'), /opened with file:\/\//);
});

test('bridge timeout becomes an actionable error instead of hanging', async () => {
  await assert.rejects(makeClient({ timedOut: true })('/status'), /timed out after 4 seconds/);
});

test('hosted bridge request includes a token and returns the response', async () => {
  const urls = [];
  const client = vm.runInNewContext(`(${bridgeFetchSource})`, {
    FILE_MODE: false,
    BRIDGE_ORIGIN: 'https://workspace-8765.app.github.dev',
    BRIDGE_TOKEN: 'private-test-token',
    AbortController: globalThis.AbortController,
    setTimeout,
    clearTimeout,
    fetch(url) { urls.push(url); return Promise.resolve({ ok: true, status: 200 }); },
    urls,
  });
  const response = await client('/status');
  assert.equal(response.status, 200);
  assert.match(urls[0], /token=private-test-token/);
  assert.match(urls[0], /^https:\/\/workspace-8765\.app\.github\.dev\/status/);
});
