const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync('ddlc-control-centre-integrated.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);

function loadFunction(name) {
  const match = script.match(new RegExp(`function ${name}\\([^)]*\\)\\{[\\s\\S]*?\\n\\}`));
  assert.ok(match, `${name} function is present`);
  return vm.runInNewContext(`(${match[0]})`);
}

const detectPackage = loadFunction('detectPackage');
const resolveRunRequest = loadFunction('resolveRunRequest');

 test('Run Type and custom upload controls are present', () => {
  assert.match(html, /id="runTypeBtn"/);
  assert.match(html, /id="runRecommended"/);
  assert.match(html, /id="uploadCustom"/);
  assert.match(html, /The Integrated commands will be unsupported unless you get our official \.zip/);
  assert.match(html, /accept="\.zip,application\/zip"/);
});

test('detects browser, desktop Ren’Py, and unknown packages separately', () => {
  assert.equal(detectPackage([{ name: 'index.html' }, { name: 'game.js' }]).type, 'browser-port');
  assert.equal(detectPackage([{ name: 'DDLC.sh' }, { name: 'game/scripts.rpa' }]).type, 'desktop-renpy');
  assert.equal(detectPackage([{ name: 'notes.txt' }]).type, 'unknown');
});

test('run resolves the entry point and rejects invalid or unsupported names', () => {
  const entries = [{ name: 'index.html' }, { name: 'assets/game.js' }];
  const browser = detectPackage(entries);
  const validRun = resolveRunRequest('index.html', entries, browser);
  assert.equal(validRun.kind, 'launch');
  assert.equal(validRun.path, 'index.html');
  assert.equal(resolveRunRequest('missing.html', entries, browser).kind, 'not-found');
  assert.equal(resolveRunRequest('assets/game.js', entries, browser).kind, 'unsupported');
  const desktopEntries = [{ name: 'DDLC.exe' }, { name: 'game/scripts.rpa' }];
  assert.equal(resolveRunRequest('DDLC.exe', desktopEntries, detectPackage(desktopEntries)).kind, 'unsupported');
});
