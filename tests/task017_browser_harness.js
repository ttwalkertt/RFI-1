'use strict';

const assert = require('node:assert/strict');
const vm = require('node:vm');

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

function preferenceUnitProof(modulePath) {
  const preferences = require(modulePath);
  const storage = new MemoryStorage();
  const key = preferences.storageKey(preferences.keys.currentFirm);
  assert.equal(key, 'rfi.admin.preferences.v1.current_firm');
  assert.equal(preferences.read('missing', 'fallback', () => true, storage), 'fallback');
  assert.equal(preferences.write('example', {page: 2}, storage), true);
  assert.deepEqual(preferences.read('example', null, value => value.page === 2, storage), {page: 2});
  assert.equal(preferences.remove('example', storage), true);
  assert.equal(preferences.read('example', 'removed', () => true, storage), 'removed');
  storage.setItem(key, '{broken');
  assert.equal(preferences.read(preferences.keys.currentFirm, 'safe', value => typeof value === 'string', storage), 'safe');
  assert.equal(storage.getItem(key), null);
  storage.setItem(key, JSON.stringify({unexpected: true}));
  assert.equal(preferences.rememberedFirm([{firm_id: 'seagate'}], 'seagate', storage), 'seagate');
  storage.setItem(key, JSON.stringify('stale'));
  assert.equal(preferences.rememberedFirm([{firm_id: 'seagate'}], 'seagate', storage), 'seagate');
  assert.equal(storage.getItem(key), null);
  assert.equal(preferences.rememberedFirm([], '', storage), '');
  const throwingRead = {getItem() { throw new Error('blocked'); }, removeItem() { throw new Error('blocked'); }};
  assert.equal(preferences.read('blocked', 'safe', () => true, throwingRead), 'safe');
  const throwingWrite = {setItem() { throw new Error('quota'); }};
  assert.equal(preferences.write('blocked', 'value', throwingWrite), false);
  assert.equal(preferences.remove('blocked', throwingRead), false);
}

function element(id, document) {
  return {
    id, value: '', textContent: '', className: '', disabled: false, checked: false,
    dataset: {}, style: {}, onclick: null, onchange: null, oninput: null,
    classList: {add() {}, remove() {}},
    querySelectorAll(selector) { return document.querySelectorAll(selector); },
    querySelector() { return null; },
    closest() { return {querySelector() { return {textContent: ''}; }}; },
    set innerHTML(value) {
      this._innerHTML = value;
      if (id === 'firms') {
        document.checkboxes = [...value.matchAll(/data-firm="([^"]+)"/g)].map(match => {
          const checkbox = element('', document);
          checkbox.dataset.firm = match[1];
          return checkbox;
        });
      }
    },
    get innerHTML() { return this._innerHTML || ''; },
  };
}

function fakeDocument() {
  const document = {elements: new Map(), checkboxes: []};
  document.getElementById = id => {
    if (!document.elements.has(id)) document.elements.set(id, element(id, document));
    return document.elements.get(id);
  };
  document.querySelectorAll = selector => selector === '[data-firm]' ? document.checkboxes : [];
  return document;
}

async function pageScript(base, path, storage) {
  const html = await fetch(base + path).then(response => response.text());
  const external = [...html.matchAll(/<script src="([^"]+)"><\/script>/g)];
  const scripts = [...html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).filter(source => source.trim());
  const document = fakeDocument();
  const calls = [];
  const context = {
    console, document, localStorage: storage, location: {search: ''}, URLSearchParams,
    setTimeout, clearTimeout, JSON, Set, Promise,
    fetch: async (url, options = {}) => {
      calls.push({path: url, method: options.method || 'GET'});
      return fetch(base + url, options);
    },
  };
  context.globalThis = context;
  vm.createContext(context);
  for (const match of external) {
    const source = await fetch(base + match[1]).then(response => response.text());
    vm.runInContext(source, context, {filename: match[1]});
  }
  for (const source of scripts) vm.runInContext(source, context, {filename: path});
  for (let attempt = 0; attempt < 200; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 10));
    const ready = path === '/source-profiles'
      ? calls.some(call => call.path.includes('/source-profile/history'))
      : calls.some(call => call.path === '/api/pulls/adapters');
    if (ready) break;
  }
  return {context, document, calls};
}

async function integrationProof(base, modulePath) {
  const preferences = require(modulePath);
  const storage = new MemoryStorage();
  storage.setItem(preferences.storageKey(preferences.keys.currentFirm), JSON.stringify('western-digital'));
  const first = await pageScript(base, '/source-profiles', storage);
  assert.equal(first.document.getElementById('firm').value, 'western-digital');
  assert(first.calls.some(call => call.path === '/api/firms/western-digital/source-profile'));
  assert(first.calls.some(call => call.path === '/api/firms/western-digital/source-profile/history'));
  assert(!first.calls.some(call => call.method === 'PUT' || call.method === 'POST'));

  const refresh = await pageScript(base, '/source-profiles', storage);
  assert.equal(refresh.document.getElementById('firm').value, 'western-digital');
  assert(!refresh.calls.some(call => call.method === 'PUT' || call.method === 'POST'));

  storage.setItem(preferences.storageKey(preferences.keys.currentFirm), JSON.stringify('seagate'));
  const navigation = await pageScript(base, '/pull-sources', storage);
  const selected = navigation.document.checkboxes.filter(item => item.checked).map(item => item.dataset.firm);
  assert.deepEqual(selected, ['seagate']);
  assert(!navigation.calls.some(call => call.path === '/api/pulls' && call.method === 'POST'));

  storage.setItem(preferences.storageKey(preferences.keys.currentFirm), JSON.stringify('stale-firm'));
  const stale = await pageScript(base, '/source-profiles', storage);
  assert.equal(stale.document.getElementById('firm').value, 'seagate');

  process.stdout.write(JSON.stringify({
    result: 'PASS', restoredFirm: 'western-digital', refreshedFirm: 'western-digital',
    navigatedFirm: selected[0], staleFallback: 'seagate', profilePutCount: 0,
    profileRevisionPostCount: 0, implicitPullPostCount: 0,
  }) + '\n');
}

async function emptyProof(base) {
  const storage = new MemoryStorage();
  const source = await pageScript(base, '/source-profiles', storage);
  assert.equal(source.document.getElementById('firm').value, '');
  assert(!source.calls.some(call => call.path.startsWith('/api/firms/')
    && call.path.includes('/source-profile')));
  const pull = await pageScript(base, '/pull-sources', storage);
  assert.equal(pull.document.checkboxes.length, 0);
  assert(!pull.calls.some(call => call.path === '/api/pulls' && call.method === 'POST'));
  process.stdout.write(JSON.stringify({result: 'PASS', emptyFirmLists: true}) + '\n');
}

preferenceUnitProof(process.argv[3]);
const proof = process.argv[4] === '--empty' ? emptyProof(process.argv[2])
  : integrationProof(process.argv[2], process.argv[3]);
proof.catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
