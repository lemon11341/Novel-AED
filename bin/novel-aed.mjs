#!/usr/bin/env node
/** npm launcher. No install hooks; setup explicitly installs a persistent Python runtime. */
import { spawnSync } from 'node:child_process';
import { readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline/promises';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
const usage = `Novel AED ${pkg.version} — connect your AI to a novel workflow

Requires Node.js 22+ and Python 3.11+. Python is not downloaded automatically.

  novel-aed setup                         Choose a client, preview, then confirm
  novel-aed setup --client codex          Preview only; no files or dependencies installed
  novel-aed setup --client codex --write  Install MCP + skill in the current project
  novel-aed setup --client cursor --write --replace   Back up and update an existing connection
  novel-aed doctor                       Check the installed MCP server (read-only)
  novel-aed mcp                          Run the installed server over stdio

Options: --client codex|claude|cursor|json, --project PATH (default current directory),
         --home PATH (persistent runtime + stories), --stories-root PATH (override storage),
         --write (setup only), --replace (setup only; back up replaced config/skill).
Environment: NOVEL_AED_PYTHON (Python executable), NOVEL_AED_HOME (storage directory).
No manuscript or host credentials are included in this package.
Story files are local, but tool results reach your AI host and may reach its model provider.
`;

function invoke(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }, ...options });
  if (result.error) throw new Error(`Could not run ${command}: ${result.error.message}`);
  if (result.status !== 0) throw new Error(result.stderr?.trim() || `${command} exited with ${result.status ?? result.signal}`);
  return result.stdout;
}

function findPython() {
  const candidates = process.env.NOVEL_AED_PYTHON
    ? [[process.env.NOVEL_AED_PYTHON]]
    : process.platform === 'win32' ? [['py', '-3'], ['python'], ['python3']] : [['python3'], ['python']];
  const failures = [];
  for (const [command, ...prefix] of candidates) {
    try {
      const output = invoke(command, [...prefix, '-c',
        'import sys,json; print(json.dumps({"executable":sys.executable,"version":list(sys.version_info[:3])}))'], { timeout: 15000 });
      const info = JSON.parse(output.trim());
      if (info.version[0] < 3 || (info.version[0] === 3 && info.version[1] < 11)) {
        throw new Error(`Python ${info.version.join('.')} is too old; Python 3.11+ is required.`);
      }
      return info.executable;
    } catch (error) {
      failures.push(`  ${[command, ...prefix].join(' ')}: ${error.message}`);
    }
  }
  throw new Error('Python 3.11+ was not found. Install Python or set NOVEL_AED_PYTHON to its executable.'
    + '\nAn explicit NOVEL_AED_PYTHON selection disables fallback to other launchers.'
    + `\nTried:\n${failures.join('\n')}`);
}

function validateOptions(options) {
  if (options.client && !['codex', 'claude', 'cursor', 'json'].includes(options.client)) {
    throw new Error('Unknown client. Choose codex, claude, cursor or json.');
  }
  if (options.replace && !options.write) throw new Error('--replace requires --write');
  if (options.client === 'json' && options.write) throw new Error('JSON mode prints a snippet only; choose a client to install.');
}

function parse(args) {
  const options = { project: process.cwd() };
  for (let i = 0; i < args.length; i++) {
    const flag = args[i];
    if (['--write', '--replace'].includes(flag)) { options[flag.slice(2)] = true; continue; }
    if (['--client', '--project', '--home', '--stories-root'].includes(flag)) {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Missing value for ${flag}`);
      options[flag.slice(2)] = args[++i];
      continue;
    }
    throw new Error(`Unknown option: ${flag}`);
  }
  validateOptions(options);
  return options;
}

function plan(python, options, install = false) {
  const args = [path.join(root, 'scripts', 'install_runtime.py')];
  if (options.home) args.push('--home', path.resolve(options.home));
  if (install) args.push('--install');
  return JSON.parse(invoke(python, args, { stdio: ['inherit', 'pipe', 'inherit'] }).trim());
}

function configure(python, runtime, options, write = false) {
  const args = [path.join(root, 'scripts', 'setup_mcp.py'), '--client', options.client,
    '--project', path.resolve(options.project), '--runtime-root', runtime.runtime_root,
    '--python', runtime.python, '--stories-root', path.resolve(options['stories-root'] || runtime.stories_root)];
  if (write) args.push('--write');
  if (options.replace) args.push('--replace');
  invoke(python, args, { stdio: 'inherit' });
}

function setupSuccessMessage(runtime, options) {
  const client = { codex: 'Codex', claude: 'Claude Code', cursor: 'Cursor' }[options.client];
  const prefix = options.client === 'codex' ? '$novel-aed:' : 'Use Novel AED to';
  return [
    `Novel AED ${runtime.version} setup completed for ${client}.`,
    `Project: ${path.resolve(options.project)}`,
    `Manuscript storage: ${path.resolve(options['stories-root'] || runtime.stories_root)}`,
    '',
    `Next: open and trust this project in ${client}, then restart the host or reload its MCP connection.`,
    'Setup completion does not prove that the host has loaded the tools. If they are still missing, start a new conversation and check the connection; the skill alone does not register MCP.',
    '',
    'First story: provide the original manuscript and title to your AI host, then send:',
    `  ${prefix} analyze the provided manuscript. Its title is [title]. Initialize a new story if needed, show me the analysis and wait for my approval.`,
    '',
    'Resume: replace [story ID] with an ID from list_stories; ask the AI to list stories if needed.',
    `  ${prefix} resume [story ID]. Read its current state and past records. If a result awaits approval, show it first and wait.`,
    '',
    'Only explicit approval of a presented result advances that stage. A request to continue is not approval of a new result.',
    'Setup does not import a manuscript. New story workspaces keep the source, drafts, approved chapters and approval history under the storage directory above. Back up the entire story folder.',
    'Privacy: tool results are visible to your AI host and may be sent to its model provider under that provider\'s data policy. Local storage does not mean offline AI; Novel AED does not call a model itself or require a separate model API key.',
    '',
  ].join('\n');
}

export async function main(argv = process.argv.slice(2), {
  detectPython = findPython,
  planRuntime = plan,
  configureHost = configure,
  input = process.stdin,
  output = process.stdout,
  errorOutput = process.stderr,
  promptFactory = createInterface,
} = {}) {
  const [command, ...args] = argv;
  if (!command || command === '--help' || command === '-h' || args.includes('--help')) { output.write(usage); return; }
  if (command === '--version' || command === '-v') { output.write(`${pkg.version}\n`); return; }
  if (!['setup', 'mcp', 'doctor'].includes(command)) throw new Error(`Unknown command: ${command}`);
  const options = parse(args);
  if (command !== 'setup' && (options.write || options.replace || options.client)) throw new Error('Client/write options are only valid for setup');
  let interactive = false;
  if (command === 'setup' && !options.client) {
    if (!input.isTTY || !output.isTTY) throw new Error('Specify --client codex|claude|cursor|json. Add --write to install after reviewing the preview.');
    const prompt = promptFactory({ input, output });
    try { options.client = (await prompt.question('Client [codex/claude/cursor/json] (codex): ')).trim() || 'codex'; }
    finally { prompt.close(); }
    validateOptions(options);
    interactive = !options.write && options.client !== 'json';
  }
  const python = detectPython();
  const runtime = planRuntime(python, options);
  if (command === 'setup') {
    if (!options.write) {
      configureHost(python, runtime, options);
      errorOutput.write(`Preview only. Runtime: ${runtime.runtime_root}\nStories: ${path.resolve(options['stories-root'] || runtime.stories_root)}\n`);
      if (!interactive) {
        errorOutput.write(options.client === 'json'
          ? 'No files changed. JSON is a snippet only; this preview does not install its runtime. To install, choose --client codex|claude|cursor with --write, then rerun the JSON preview for manual host configuration.\n'
          : 'No files changed. Add --write to install.\n');
        return;
      }
      const prompt = promptFactory({ input, output });
      let accepted;
      try { accepted = /^y(?:es)?$/i.test((await prompt.question('Install this runtime, MCP connection and skill? [y/N] ')).trim()); }
      finally { prompt.close(); }
      if (!accepted) return;
    }
    const installed = planRuntime(python, options, true);
    configureHost(python, installed, options, true);
    errorOutput.write(setupSuccessMessage(installed, options));
    return;
  }
  if (!runtime.ready) {
    throw new Error(`This version has no verified runtime at ${runtime.runtime_root}.\n`
      + `Requested storage: ${path.resolve(options.home || process.env.NOVEL_AED_HOME || runtime.home || runtime.stories_root)}\n`
      + 'Run novel-aed setup --client codex --write (or choose claude/cursor), using the same --home or NOVEL_AED_HOME.\n'
      + 'For an existing connection after an upgrade, add --replace. doctor and mcp never install automatically.');
  }
  const script = command === 'doctor' ? 'check_mcp.py' : 'mcp_server.py';
  const parameters = [path.join(runtime.runtime_root, 'scripts', script)];
  if (command === 'mcp') parameters.push('--stories-root', path.resolve(options['stories-root'] || runtime.stories_root));
  invoke(runtime.python, parameters, { stdio: 'inherit' });
}

if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
  main().catch(error => { process.stderr.write(`novel-aed: ${error.message}\n`); process.exitCode = 1; });
}
