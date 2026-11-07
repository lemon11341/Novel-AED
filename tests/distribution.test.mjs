import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, readdirSync, mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { main } from '../bin/novel-aed.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cli = path.join(root, 'bin', 'novel-aed.mjs');
const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));

function run(args, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], { cwd: root, encoding: 'utf8', windowsHide: true,
    timeout: 30000, env: { ...process.env, PYTHONUTF8: '1' }, ...options });
}

function setupHarness(failAt) {
  const project = path.join(tmpdir(), 'novel-aed-mocked-project 한글');
  const home = path.join(tmpdir(), 'novel-aed-mocked-home 한글');
  const runtime = {
    version: pkg.version,
    runtime_root: path.join(home, 'runtimes', pkg.version),
    python: path.join(home, 'mock-python'),
    stories_root: path.join(home, 'stories'),
    ready: false,
  };
  const calls = [];
  const stdout = [];
  const stderr = [];
  const dependencies = {
    detectPython() { calls.push(['python']); return 'mock-python'; },
    planRuntime(python, options, install = false) {
      calls.push(['plan', install]);
      assert.equal(python, 'mock-python');
      if (install && failAt === 'install') throw new Error('Installation failed');
      return { ...runtime, ready: install };
    },
    configureHost(python, selectedRuntime, options, write = false) {
      calls.push(['configure', options.client, write]);
      assert.equal(python, 'mock-python');
      assert.equal(selectedRuntime.ready, write);
      if (write && failAt === 'configure') throw new Error('Configuration failed');
    },
    input: { isTTY: false },
    output: { isTTY: false, write(text) { stdout.push(text); } },
    errorOutput: { write(text) { stderr.push(text); } },
  };
  return { project, home, runtime, calls, dependencies,
    stdout: () => stdout.join(''), stderr: () => stderr.join('') };
}

test('help and version do not need Python or create an installation', () => {
  const env = { ...process.env, NOVEL_AED_PYTHON: path.join(root, 'missing-python') };
  assert.match(run(['--help'], { env }).stdout, /Python 3\.11/);
  const version = run(['--version'], { env });
  assert.equal(version.status, 0);
  assert.equal(version.stdout.trim(), pkg.version);
});

test('invalid and ambiguous invocations fail before installing anything', () => {
  for (const args of [['unknown'], ['setup'], ['setup', '--client', 'unknown'],
    ['setup', '--client', 'codex', '--replace'], ['setup', '--client'],
    ['setup', '--client', 'json', '--write'], ['doctor', '--write']]) {
    const result = run(args);
    assert.equal(result.status, 1, JSON.stringify(args));
    assert.match(result.stderr, /novel-aed:/);
  }
});

test('setup preview contains persistent paths, never writes files or installs dependencies', () => {
  // Only empty fixtures in the system temporary directory; intentionally no deletion.
  const temporary = mkdtempSync(path.join(tmpdir(), 'novel-aed-npm-preview-'));
  const home = path.join(temporary, 'persistent home 한글');
  const project = path.join(temporary, 'project 한글');
  mkdirSync(project);
  const result = run(['setup', '--client', 'codex', '--project', project, '--home', home]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /\[mcp_servers\.novel_aed\]/);
  assert.match(result.stdout, /runtimes/);
  assert.match(result.stdout, /stories/);
  assert.match(result.stderr, /No files changed/);
  assert.equal(existsSync(home), false);
  assert.deepEqual(readdirSync(project), []);
  // JSON is a portable snippet and must not acquire Python-only host timeout keys.
  const json = run(['setup', '--client', 'json', '--project', project, '--home', home]);
  assert.equal(json.status, 0, json.stderr);
  assert.deepEqual(Object.keys(JSON.parse(json.stdout).mcpServers.novel_aed).sort(), ['args', 'command']);
  assert.match(json.stderr, /JSON is a snippet only/);
  assert.match(json.stderr, /choose --client codex\|claude\|cursor with --write/);
  assert.doesNotMatch(json.stderr, /Add --write to install/);
  assert.doesNotMatch(json.stderr, /First story:|Resume:/);
  assert.equal(existsSync(home), false);
  assert.deepEqual(readdirSync(project), []);
});

test('doctor and mcp diagnose a missing runtime without installing it', () => {
  const home = path.join(tmpdir(), `novel-aed-not-installed-${randomUUID()}`);
  for (const command of ['doctor', 'mcp']) {
    const result = run([command, '--home', home]);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /no verified runtime/);
    assert.ok(result.stderr.includes(home));
    assert.match(result.stderr, /same --home or NOVEL_AED_HOME/);
    assert.match(result.stderr, /add --replace/);
    assert.match(result.stderr, /never install automatically/);
    assert.equal(existsSync(home), false);
  }
});

test('missing-runtime diagnostics preserve the requested storage when Python canonicalizes it', async () => {
  for (const command of ['doctor', 'mcp']) {
    const harness = setupHarness();
    const requested = path.join(tmpdir(), 'SHORT~1', 'not-installed');
    const canonical = path.join(tmpdir(), 'Long Directory Name', 'not-installed', 'runtimes', 'version');
    harness.dependencies.planRuntime = () => ({ ...harness.runtime, runtime_root: canonical });
    await assert.rejects(main([command, '--home', requested], harness.dependencies), error => {
      assert.ok(error.message.includes(`Requested storage: ${path.resolve(requested)}`));
      assert.ok(error.message.includes(`no verified runtime at ${canonical}`));
      return true;
    });
    assert.deepEqual(harness.calls, [['python']]);
  }
});

test('successful setup gives host-specific prompts, storage and privacy guidance only after configuration', async () => {
  for (const client of ['codex', 'claude', 'cursor']) {
    const harness = setupHarness();
    const selectedStorage = client === 'codex'
      ? path.join(harness.home, 'selected manuscripts 한글') : harness.runtime.stories_root;
    const args = ['setup', '--client', client, '--project', harness.project, '--home', harness.home, '--write'];
    if (client === 'codex') args.push('--stories-root', selectedStorage);
    await main(args, harness.dependencies);
    assert.deepEqual(harness.calls, [
      ['python'], ['plan', false], ['plan', true], ['configure', client, true],
    ]);
    assert.equal(harness.stdout(), '');
    const message = harness.stderr();
    assert.match(message, /setup completed/);
    assert.ok(message.includes(`Project: ${harness.project}`));
    assert.ok(message.includes(`Manuscript storage: ${selectedStorage}`));
    assert.match(message, /restart the host or reload its MCP connection/);
    assert.match(message, /does not prove that the host has loaded the tools/);
    assert.match(message, /First story:[\s\S]*\[title\][\s\S]*Initialize a new story if needed/);
    assert.match(message, /show me the analysis and wait for my approval/);
    assert.match(message, /Resume:[\s\S]*list_stories[\s\S]*resume \[story ID\][\s\S]*past records/);
    assert.match(message, /If a result awaits approval, show it first and wait/);
    assert.match(message, /Only explicit approval/);
    assert.match(message, /continue is not approval/);
    assert.match(message, /Setup does not import a manuscript/);
    assert.match(message, /Back up the entire story folder/);
    assert.match(message, /tool results are visible to your AI host[\s\S]*model provider/);
    if (client === 'codex') assert.match(message, /\$novel-aed:/);
    else assert.doesNotMatch(message, /\$novel-aed/);
  }
});

test('installation or configuration failure never prints success or story prompts', async () => {
  for (const failAt of ['install', 'configure']) {
    const harness = setupHarness(failAt);
    await assert.rejects(main(['setup', '--client', 'codex', '--write'], harness.dependencies),
      /Installation failed|Configuration failed/);
    assert.doesNotMatch(harness.stderr(), /setup completed|First story:|Resume:/);
    assert.equal(harness.stdout(), '');
    assert.equal(harness.calls.some(call => call[0] === 'configure'), failAt === 'configure');
  }
});

test('every explicit preview avoids installation and write configuration', async () => {
  for (const client of ['codex', 'claude', 'cursor', 'json']) {
    const harness = setupHarness();
    await main(['setup', '--client', client], harness.dependencies);
    assert.deepEqual(harness.calls, [
      ['python'], ['plan', false], ['configure', client, false],
    ]);
    assert.match(harness.stderr(), /No files changed/);
    assert.doesNotMatch(harness.stderr(), /setup completed|First story:|Resume:/);
  }
});

test('interactive JSON selection with --write fails before Python discovery or installation', async () => {
  const harness = setupHarness();
  harness.dependencies.input.isTTY = true;
  harness.dependencies.output.isTTY = true;
  let closed = false;
  harness.dependencies.promptFactory = () => ({
    async question() { return 'json'; },
    close() { closed = true; },
  });
  await assert.rejects(main(['setup', '--write'], harness.dependencies), /JSON mode prints a snippet only/);
  assert.equal(closed, true);
  assert.deepEqual(harness.calls, []);
  assert.equal(harness.stderr(), '');
});

test('declining interactive setup leaves only a preview and no story prompts', async () => {
  const harness = setupHarness();
  harness.dependencies.input.isTTY = true;
  harness.dependencies.output.isTTY = true;
  const answers = ['codex', 'n'];
  let closed = 0;
  harness.dependencies.promptFactory = () => ({
    async question() { return answers.shift(); },
    close() { closed++; },
  });
  await main(['setup'], harness.dependencies);
  assert.deepEqual(harness.calls, [
    ['python'], ['plan', false], ['configure', 'codex', false],
  ]);
  assert.equal(answers.length, 0);
  assert.equal(closed, 2);
  assert.match(harness.stderr(), /Preview only/);
  assert.doesNotMatch(harness.stderr(), /setup completed|First story:|Resume:/);
});

test('explicit Python selection reports the failed executable without installing Python', () => {
  const missingPython = path.join(root, 'does-not-exist');
  const result = run(['setup', '--client', 'codex'], {
    env: { ...process.env, NOVEL_AED_PYTHON: missingPython }
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Python 3\.11\+ was not found/);
  assert.match(result.stderr, /explicit NOVEL_AED_PYTHON selection disables fallback/);
  assert.ok(result.stderr.includes(missingPython));
  assert.match(result.stderr, /Could not run/);
});
