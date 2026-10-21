const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync('ddlc-control-centre-integrated.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

class Element {
  constructor(id = '', tagName = 'div') {
    this.id = id;
    this.tagName = tagName.toUpperCase();
    this.style = { display: '' };
    this.dataset = {};
    this.children = [];
    this.listeners = new Map();
    this.className = '';
    this.classList = {
      add: name => { this.className = `${this.className} ${name}`.trim(); },
      remove: name => { this.className = this.className.split(/\s+/).filter(item => item !== name).join(' '); },
      contains: name => this.className.split(/\s+/).includes(name),
    };
    this.value = '';
    this.files = [];
    this.hidden = false;
    this.clickCount = 0;
    this.focusCount = 0;
    this.scrollCount = 0;
    this.offsetLeft = 0;
    this.offsetTop = 0;
    this.scrollTop = 0;
    this._textContent = '';
    this._innerHTML = '';
  }

  set textContent(value) { this._textContent = String(value); this.children = []; }
  get textContent() { return this._textContent + this.children.map(child => child.textContent || '').join(''); }
  set innerHTML(value) { this._innerHTML = String(value); this.children = []; this._textContent = ''; }
  get innerHTML() { return this._innerHTML; }
  get innerText() { return this.textContent; }

  addEventListener(type, callback) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(callback);
  }

  async dispatch(type, supplied = {}) {
    const event = {
      target: this,
      key: supplied.key,
      clientX: supplied.clientX || 0,
      clientY: supplied.clientY || 0,
      pointerId: supplied.pointerId || 1,
      dataTransfer: supplied.dataTransfer,
      preventDefault() { this.defaultPrevented = true; },
      ...supplied,
    };
    const callbacks = [...(this.listeners.get(type) || [])];
    const results = callbacks.map(callback => callback(event));
    if (type === 'click' && typeof this.onclick === 'function') results.push(this.onclick(event));
    await Promise.all(results.map(result => Promise.resolve(result)));
    return event;
  }

  async click() { this.clickCount++; return this.dispatch('click'); }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.children.push(node); return node; }
  setAttribute() {}
  setPointerCapture() {}
  focus() { this.focusCount++; }
  scrollIntoView() { this.scrollCount++; }
  closest(selector) { return selector === '.commandarea' ? this.commandArea || null : null; }
  querySelectorAll(selector) { const className = selector.startsWith('.') ? selector.slice(1) : ''; return className ? this.children.filter(child => child.className.split(/\s+/).includes(className)) : []; }
  querySelector(selector) { return selector === 'code' ? this.children.find(child => child.tagName === 'CODE') || null : null; }
}

function makeZip(files) {
  const chunks = [];
  const central = [];
  let offset = 0;
  const crc32 = buffer => {
    let crc = 0xffffffff;
    for (const byte of buffer) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    return (crc ^ 0xffffffff) >>> 0;
  };
  for (const [name, contents] of Object.entries(files)) {
    const filename = Buffer.from(name);
    const data = Buffer.from(contents);
    const crc = crc32(data);
    const local = Buffer.alloc(30 + filename.length);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(filename.length, 26); filename.copy(local, 30);
    chunks.push(local, data);
    const header = Buffer.alloc(46 + filename.length);
    header.writeUInt32LE(0x02014b50, 0); header.writeUInt16LE(20, 4); header.writeUInt16LE(20, 6);
    header.writeUInt32LE(crc, 16); header.writeUInt32LE(data.length, 20); header.writeUInt32LE(data.length, 24);
    header.writeUInt16LE(filename.length, 28); header.writeUInt32LE(offset, 42); filename.copy(header, 46);
    central.push(header);
    offset += local.length + data.length;
  }
  const centralData = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(Object.keys(files).length, 8); end.writeUInt16LE(Object.keys(files).length, 10);
  end.writeUInt32LE(centralData.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...chunks, centralData, end]);
}

function bootApp() {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  const elements = new Map(ids.map(id => [id, new Element(id, /input/i.test(id) ? 'input' : 'div')]));
  const term = new Element('terminal');
  const pageCopy = new Element('page-copy', 'p');
  const commandArea = new Element('commandarea');
  const documentListeners = new Map();
  const document = {
    hidden: false,
    getElementById(id) { return elements.get(id) || null; },
    createElement(tag) { return new Element('', tag); },
    createTextNode(text) { return { textContent: String(text) }; },
    querySelector(selector) { return selector === '.terminal' ? term : selector === '.lowergrid .mini p' ? pageCopy : null; },
    addEventListener(type, callback) {
      if (!documentListeners.has(type)) documentListeners.set(type, []);
      documentListeners.get(type).push(callback);
    },
  };
  elements.get('cmdinput').commandArea = commandArea;
  const context = {
    document,
    location: { protocol: 'file:', origin: 'null' },
    navigator: { userAgent: 'ControlCentreTest' },
    localStorage: { removeItem() {} },
    innerWidth: 1024,
    innerHeight: 768,
    setInterval() { return 1; },
    setTimeout,
    clearTimeout,
    fetch: async () => { throw new Error('fetch should not run in file mode'); },
    URL,
    Blob,
    TextDecoder,
    DataView,
    Uint8Array,
    AbortController,
    btoa,
    atob,
    unescape,
    console,
  };
  vm.runInNewContext(script, context, { timeout: 1000 });
  return { elements, document, term, pageCopy, commandArea, documentListeners };
}

async function settle() { await new Promise(resolve => setImmediate(resolve)); }

 test('Run Type opens/closes and Upload Custom activates the ZIP picker', async () => {
  const app = bootApp();
  await app.elements.get('runTypeBtn').click();
  assert.equal(app.elements.get('runTypeDialog').style.display, 'flex');
  await app.elements.get('closeRunType').click();
  assert.equal(app.elements.get('runTypeDialog').style.display, 'none');
  await app.elements.get('runTypeBtn').click();
  await app.elements.get('uploadCustom').click();
  assert.equal(app.elements.get('zipInput').clickCount, 1);
  assert.equal(app.elements.get('runTypeDialog').style.display, 'none');
});

test('all visible buttons have an action handler', () => {
  const app = bootApp();
  const buttonIds = [...html.matchAll(/<button\b[^>]*\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(buttonIds.length, 17);
  for (const id of buttonIds) {
    const element = app.elements.get(id);
    assert.ok(element, `button #${id} has a DOM element`);
    assert.ok(typeof element.onclick === 'function' || element.listeners.has('click'), `button #${id} has a click action`);
  }
});

test('header, game, launch, and reset buttons perform visible actions', async () => {
    const app = bootApp();
    const output = app.elements.get('termout');
    for (const id of ['uploadTop', 'uploadMain', 'uploadSide']) await app.elements.get(id).click();
    assert.equal(app.elements.get('zipInput').clickCount, 3);
    await app.elements.get('helpBtn').click();
    assert.match(output.innerText, /AVAILABLE COMMANDS/);
    await app.elements.get('checkBtn').click();
      assert.match(output.innerText, /No game ZIP loaded/);
    await app.elements.get('sceneBtn').click();
    await app.elements.get('connectBtn').click();
    assert.match(output.innerText, /file:\/\//);
    await app.elements.get('runRecommended').click();
    await settle();
    assert.match(output.innerText, /Recommended launch failed/);
    await app.elements.get('resetBtn').click();
    assert.equal(app.elements.get('modalback').style.display, 'flex');
    await app.elements.get('cancelModal').click();
    assert.equal(app.elements.get('modalback').style.display, 'none');
    await app.elements.get('resetBtn').click();
    await app.elements.get('confirmModal').click();
    assert.equal(app.elements.get('modalback').style.display, 'none');
  });

test('terminal Enter executes, history works, invalid commands report errors, and clear works', async () => {
  const app = bootApp();
  const input = app.elements.get('cmdinput');
  const output = app.elements.get('termout');
  input.value = 'help';
  await input.dispatch('keydown', { key: 'Enter' });
  assert.match(output.innerText, /AVAILABLE COMMANDS/);
  assert.equal(input.value, '');
  input.value = 'history';
  await app.elements.get('runBtn').click();
  assert.match(output.innerText, /help/);
  input.value = 'not-a-real-command';
  await input.dispatch('keydown', { key: 'Enter' });
  assert.match(output.innerText, /Unknown command/);
  input.value = '';
  await app.elements.get('runBtn').click();
  await app.elements.get('runBtn').click();
  assert.match(output.innerText, /Unknown command/);
  input.value = 'clear';
  await input.dispatch('keydown', { key: 'Enter' });
  assert.equal(output.innerText, '');
});

test('suggestions insert with pointer and local ZIP errors do not block controls', async () => {
  const app = bootApp();
  const input = app.elements.get('cmdinput');
  input.value = 'hel';
  await input.dispatch('input');
  const suggestion = app.elements.get('suggestions').querySelectorAll('.suggestion')[0];
  assert.ok(suggestion);
  await suggestion.dispatch('pointerdown');
  assert.equal(input.value, 'help ');
  assert.equal(app.elements.get('suggestions').style.display, 'none');
  const invalid = { name: 'invalid.zip', size: 3, arrayBuffer: async () => Uint8Array.from([1, 2, 3]).buffer };
  app.elements.get('zipInput').files = [invalid];
  await app.elements.get('zipInput').dispatch('change');
  await settle();
  assert.match(app.elements.get('termout').innerText, /ZIP inspection failed/);
  await app.elements.get('connectBtn').click();
  assert.match(app.elements.get('termout').innerText, /file:\/\//);
  input.value = 'help';
  await input.dispatch('keydown', { key: 'Enter' });
  assert.match(app.elements.get('termout').innerText, /AVAILABLE COMMANDS/);
});

test('file browser, search, hide, remove, and draggable mini-button work', async () => {
  const app = bootApp();
  const zip = makeZip({ 'index.html': '<h1>test game</h1>', 'assets/app.js': 'ok' });
  const file = { name: 'browser-game.zip', size: zip.length, arrayBuffer: async () => zip.buffer.slice(zip.byteOffset, zip.byteOffset + zip.byteLength) };
  app.elements.get('zipInput').files = [file];
  await app.elements.get('zipInput').dispatch('change');
  await settle();
  assert.equal(app.elements.get('fileCount').textContent, '2', app.elements.get('termout').innerText);
  assert.match(app.elements.get('packageSummary').textContent, /Browser package/);
    const terminal = app.elements.get('cmdinput');
    terminal.value = 'run index.html';
    await terminal.dispatch('keydown', { key: 'Enter' });
    await settle();
    assert.match(app.elements.get('termout').innerText, /Browser package could not be hosted/);
    terminal.value = 'run app.js';
    await terminal.dispatch('keydown', { key: 'Enter' });
    assert.match(app.elements.get('termout').innerText, /not a supported launch entry point/);
  app.elements.get('fileSearch').value = 'index.html';
  await app.elements.get('fileSearch').dispatch('input');
  assert.equal(app.elements.get('filelist').querySelectorAll('.fileentry').length, 1);
  app.elements.get('fileSearch').value = '';
  await app.elements.get('fileSearch').dispatch('input');
  const hide = app.elements.get('filelist').querySelectorAll('.fileentry')[0].children.find(child => child.tagName === 'BUTTON');
  await hide.click();
  assert.equal(app.elements.get('fileCount').textContent, '1');
  await app.elements.get('removePackageBtn').click();
  assert.equal(app.elements.get('fileCount').textContent, '0');
  const floating = app.elements.get('floating');
  await floating.click();
  assert.equal(app.term.scrollCount, 1);
  assert.ok(app.elements.get('cmdinput').focusCount > 0);
  await floating.dispatch('pointerdown', { clientX: 5, clientY: 5 });
  await floating.dispatch('pointermove', { clientX: 25, clientY: 25 });
  await floating.dispatch('pointerup');
  assert.equal(floating.dataset.dragged, '1');
});
