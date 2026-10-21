const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync('ddlc-control-centre-integrated.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);

function loadFunction(name) {
<<<<<<< HEAD
  const start = script.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} function is present`);
  const open = script.indexOf('{', start);
  let depth = 0;
  for (let index = open; index < script.length; index++) {
    if (script[index] === '{') depth++;
    if (script[index] === '}' && --depth === 0) {
          return vm.runInNewContext(`(${script.slice(start, index + 1)})`, {
            ACT_TARGETS: { 'act 1': 'ch0_main', 'act 2': 'ch21_main', 'act 3': 'ch30_main', 'act 4': 'ch40_main' },
          });
    }
  }
  throw new Error(`${name} function has no closing brace`);
=======
  const match = script.match(new RegExp(`function ${name}\\([^)]*\\)\\{[\\s\\S]*?\\n\\}`));
  assert.ok(match, `${name} function is present`);
  return vm.runInNewContext(`(${match[0]})`);
>>>>>>> origin/main
}

const detectPackage = loadFunction('detectPackage');
const resolveRunRequest = loadFunction('resolveRunRequest');
<<<<<<< HEAD
const canNavigate = loadFunction('canNavigate');

test('Run Type and custom upload controls are present', () => {
=======

 test('Run Type and custom upload controls are present', () => {
>>>>>>> origin/main
  assert.match(html, /id="runTypeBtn"/);
  assert.match(html, /id="runRecommended"/);
  assert.match(html, /id="uploadCustom"/);
  assert.match(html, /The Integrated commands will be unsupported unless you get our official \.zip/);
  assert.match(html, /accept="\.zip,application\/zip"/);
<<<<<<< HEAD
  assert.match(html, /\/launch\/recommended/);
  assert.match(html, /__DDLC_CC_TOKEN__/);
=======
>>>>>>> origin/main
});

test('detects browser, desktop Ren’Py, and unknown packages separately', () => {
  assert.equal(detectPackage([{ name: 'index.html' }, { name: 'game.js' }]).type, 'browser-port');
  assert.equal(detectPackage([{ name: 'DDLC.sh' }, { name: 'game/scripts.rpa' }]).type, 'desktop-renpy');
  assert.equal(detectPackage([{ name: 'notes.txt' }]).type, 'unknown');
});

<<<<<<< HEAD
test('run resolves only a supported browser entry point', () => {
=======
test('run resolves the entry point and rejects invalid or unsupported names', () => {
>>>>>>> origin/main
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
<<<<<<< HEAD

test('navigation requires labels reported by the running game', () => {
  assert.equal(canNavigate('scene list', []), true);
  assert.equal(canNavigate('scene safe_label', ['safe_label']), true);
  assert.equal(canNavigate('scene missing_label', ['safe_label']), false);
  assert.equal(canNavigate('act 1', ['ch0_main']), true);
  assert.equal(canNavigate('act 2', ['ch0_main']), false);
});

test('bridge and ZIP handlers are declared once', () => {
  for (const name of ['bridgeFetch', 'refreshBridgeStatus', 'readBridgeResults', 'readZip', 'renderFiles']) {
    const declarations = script.match(new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\(`, 'g')) || [];
    assert.equal(declarations.length, 1, `${name} should have one declaration`);
  }
});
=======
>>>>>>> origin/main
