'use strict';

const assert = require('node:assert/strict');
const vm = require('node:vm');

function element() {
  return {
    textContent: '', _innerHTML: '', disabled: false, checked: false, dataset: {}, style: {},
    className: '', onclick: null, onchange: null,
    classList: {add() {}, remove() {}},
    set innerHTML(value) { this._innerHTML = value; },
    get innerHTML() { return this._innerHTML; },
  };
}

async function main(base) {
  const html = await fetch(base + '/pull-sources').then(response => response.text());
  const scripts = [...html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).filter(source => source.trim());
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    querySelectorAll() { return []; },
  };
  const historyCalls = [];
  const context = {
    console, document, URLSearchParams, JSON, Set, Promise, location: {search: ''},
    history: {pushState(state, title, url) { historyCalls.push({state, title, url}); }},
    RFIAdminPreferences: {rememberedFirm() { return ''; }, rememberFirm() {}},
    setTimeout() { return 0; }, clearTimeout() {},
    fetch: async path => ({
      ok: true,
      async json() {
        if (path === '/api/pulls/firms') return {items: []};
        if (path === '/api/pulls/adapters') return {items: []};
        throw new Error('Unexpected browser harness request: ' + path);
      },
    }),
  };
  context.globalThis = context;
  vm.createContext(context);
  for (const source of scripts) vm.runInContext(source, context, {filename: '/pull-sources'});
  await new Promise(resolve => setImmediate(resolve));

  const run = {
    run_id: 'pull-browser-proof',
    status: 'partial',
    summary: {firms: 1, artifacts: 3, success: 1, duplicate: 0, no_change: 0,
      skipped: 0, configuration_problem: 2, retrieval_failure: 0},
    firms: [{firm_id: 'firm & co', canonical_name: 'Firm & Co', status: 'partial',
      source_profile_revision_number: 4, artifacts: [
        {artifact_id: 'press/release?', label: 'Press release',
          outcome: 'configuration_problem', diagnostic: 'Not configured.', attempts: []},
        {artifact_id: 'sec_10k', label: 'Annual report', outcome: 'success',
          diagnostic: 'Stored.', attempts: []},
        {artifact_id: '', label: 'Unidentified configuration',
          outcome: 'configuration_problem', diagnostic: 'Identity unavailable.', attempts: []},
      ]}],
  };
  context.renderResults(run);
  const rendered = document.getElementById('results').innerHTML;
  const links = [...rendered.matchAll(/<a class="badge configuration-action"([^>]*)>/g)];
  assert.equal(links.length, 1);
  assert(rendered.includes('/source-profiles?firm_id=firm+%26+co&amp;artifact_id=press%2Frelease%3F'));
  assert(!links[0][1].includes('target='));
  assert(rendered.includes('<span class="badge">success</span>'));
  assert(rendered.includes('<span class="badge">configuration_problem</span>'));
  assert(!html.includes('window.open('));
  assert(!html.includes('history.replaceState'));
  assert(!html.includes('role="dialog"'));
  context.renderResults(run, true);
  assert.equal(historyCalls.length, 1);
  assert.equal(historyCalls[0].state.run_id, 'pull-browser-proof');
  assert.equal(historyCalls[0].title, '');
  assert.equal(historyCalls[0].url, '/pull-sources?run_id=pull-browser-proof');
  process.stdout.write(JSON.stringify({
    result: 'PASS', actionableLinks: links.length, currentTab: true,
    encodedFirmAndArtifact: true, nonActionableStatusesUnchanged: true,
    popupOrModal: false, durableBackUrl: historyCalls[0].url,
  }) + '\n');
}

main(process.argv[2]).catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
