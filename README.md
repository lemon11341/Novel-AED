# Novel AED — 소설 이어쓰기 도구 | Novel Continuation Tool

[English](README.md) | [한국어](README.ko.md)

## Download and start

**[Download the user ZIP (v0.1.1)](https://github.com/lemon11341/Novel-AED/releases/download/v0.1.1/novel-aed-0.1.1-download.zip)** · [Release notes](https://github.com/lemon11341/Novel-AED/releases/tag/v0.1.1)

Extract the ZIP and open the entire `Novel-AED-0.1.1` folder as your AI agent's project. Python 3.11+ is required. The folder workflow below needs no npm or MCP installation. Provide your manuscript and title to an AI environment that can edit files and run commands, then use the first-story prompt below.

**Continue an unfinished novel with your AI agent, one approved stage at a time.**

Novel AED connects a local MCP server and a skill to your AI agent. Your selected model analyzes the manuscript, plans the remaining story through its ending, and writes each chapter with self-review. Source text, approved canon, drafts and approval history stay in local files.

## Start here

**The easiest start is to open this entire folder as your AI agent's project.** You need Python 3.11+ and an AI environment that can edit files and run commands. Follow [Use the folder as an agent project](#use-the-folder-as-an-agent-project); Node.js and MCP installation are not needed for that route.

- To expose Novel AED as callable tools, choose [MCP installation](#install-mcp-from-source). Setup provides configuration for Codex, Claude Code and Cursor.
- **Public npm distribution is still pending.** Use the folder workflow or source MCP installation today. If you received a verified `.tgz`, follow the [tarball installation instructions](docs/releasing.md#로컬-검증과-압축파일) in the release guide.

Your AI environment supplies the model and account. Attaching a manuscript to an ordinary chat does not run this tool.

## What it does

- Analyzes characters, events and timeline, worldbuilding, narration, style, themes, foreshadowing and emotion.
- Plans chapter pacing and an actual ending from approved analysis.
- Checks source quotations, canon references, chapter order, character counts and artifact integrity.
- Preserves drafts and requires explicit user approval before accepting analysis, an outline or a chapter.
- Exposes 17 MCP tools and a matching skill; the CLI uses the same validation and approval code.

Your host provides the model and its authentication. Novel AED does not require a separate model API key. One selected model performs the novel work sequentially, including self-review.

## Use the folder as an agent project

You can use the downloaded repository directly as a project, without installing MCP or waiting for npm publication. Requires Python 3.11+ and an AI agent that can read/edit local files and run terminal commands.

1. Download this repository using GitHub's **Code → Download ZIP** and extract it, or clone it with Git.
2. Open the extracted **Novel-AED folder** as the agent's project/workspace. Include the whole folder, rather than attaching only the README or manuscript.
3. Provide the original manuscript and its title, then ask:

   > Read AGENTS.md, workflow/WORKFLOW.md and workflow/STAGES.md. The manuscript is at [file path] and its title is [title]. Initialize a new story if needed, analyze it, show me the result and wait for my approval.

Replace `[file path]` and `[title]` with your own values. Keep the manuscript under `stories/inputs/` (create the folder if needed); this location is excluded from Git. Avoid placing private manuscripts in the repository root. Check `python --version` (`python3 --version` on macOS/Linux) for Python 3.11+. If the command is unavailable, install Python, then reopen your terminal and AI app.

After the first task, the agent should show the analysis, saved path and digest, then wait. Read the result and approve it or request changes. Analysis, outline and each chapter require separate approval; installation does not create a story or write it through to the ending automatically.

The agent performs the writing and runs `scripts/workspace.py` for validation and approval records. This file/CLI mode uses only Python's standard library; Node.js, npm and MCP dependencies are not required. If the agent does not automatically load `AGENTS.md`, the request above tells it to read the rules explicitly.

Stories are stored in this project's `stories/` directory. Keep the entire story folder when moving or backing up a work. To resume, reopen the project and ask:

> Read the state and past records in stories/[story folder] and resume from the current stage. If a result awaits approval, show it first and wait.

An agent that only accepts attachments and cannot edit files or execute commands cannot operate this workflow directly. To expose Novel AED as callable tools in a supporting host, use the MCP setup below.

## Install MCP from source

This is the installation path available from the checkout. Python 3.11+ and a host supporting local stdio MCP are required. Setup supports Codex, Claude Code and Cursor.

### Windows PowerShell

Run in the repository directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-mcp.txt
python scripts/setup_mcp.py --client codex --write
.venv/Scripts/python.exe scripts/check_mcp.py
```

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.txt
python3 scripts/setup_mcp.py --client codex --write
.venv/bin/python scripts/check_mcp.py
```

Replace `codex` with `claude` or `cursor` for another supported host. Omit `--write` to preview configuration. Setup preserves other settings and refuses conflicting entries; `--write --replace` backs up and replaces the Novel AED connection and skill.

Source setup defaults to this checkout's project and `stories/` directory. To connect from another project, pass `--project /absolute/path/to/project`. Open and trust the selected project in your AI host, then reload its MCP connection or restart the host. If tools are still missing, start a new conversation and check the connection. Successful setup does not prove that the host has loaded the tools; installing the skill alone does not register the server.

See [MCP setup](docs/mcp.md) for manual JSON configuration, storage options and troubleshooting.

## Use with your AI

In Codex, invoke `$novel-aed`. In other hosts, ask the agent to use Novel AED and read its workflow guidance.

**Start a story:**

> Use Novel AED to analyze the provided manuscript. Its title is [title]. Initialize a new story if needed, show me the analysis and wait for my approval.

Provide the original manuscript to the agent. If it has not been registered, the agent initializes a new story. With multiple workspaces, identify the intended story.

**Resume a story:**

> Use Novel AED to resume [story ID]. Read its current state and past records. If a result awaits approval, show it first and wait.

Replace `[story ID]` with the ID returned by `list_stories`, such as `my-story`, not an absolute path or `stories/my-story`. If you do not know the ID, ask the agent to list the registered stories first.

The workflow is:

```text
Analysis → user approval → outline → user approval
         → chapter + self-review → user approval → next chapter
```

Only an explicit approval of the presented result advances that stage. A request to continue is not approval of a new result. Revision requests preserve the old submission in history.

## npm distribution

**Initial npm publication is pending.** The following commands are intended for use after publication; source installation above is available now.

Requires Node.js 22+, npm and Python 3.11+:

```sh
npx novel-aed setup
# Non-interactive installation in the current project:
npx novel-aed setup --client codex --write
npx novel-aed doctor
```

Interactive setup previews the selected connection and asks before installing. With `--client` but without `--write`, it only previews. Python itself is not downloaded; setup installs MCP dependencies in an isolated environment.

After successful setup, the launcher prints the connected project, actual manuscript storage directory and ready-to-copy first-story and resume prompts. Open and trust that project in the selected host, then restart the host or reload its MCP connection before using the prompts. Setup does not import a manuscript or confirm that the host has loaded its tools.

`--client json` prints a manual configuration snippet only; it cannot be combined with `--write`. To use its persistent runtime paths, first install with a supported client, then rerun the JSON preview. Neither `doctor` nor `mcp` installs a missing runtime.

The npm installer keeps versioned runtimes outside the npm cache and manuscripts in separate storage:

| Platform | Default storage root |
| --- | --- |
| Windows | `%LOCALAPPDATA%/NovelAED` |
| macOS / Linux | `$XDG_DATA_HOME/novel-aed`, default `~/.local/share/novel-aed` |

The root contains `runtimes/` and `stories/`. Set `--home` or `NOVEL_AED_HOME` to change it, or `--stories-root` to select an existing story directory. These npm defaults differ from source installation: the connected project's own `stories/` is not used unless selected explicitly. The storage directory printed at setup is where new story workspaces keep their source, drafts, approved chapters and approval history. Back up each entire story folder. Updating or clearing npm caches does not delete manuscripts.

After upgrading, reconnect with `npx novel-aed setup --client codex --write --replace`. For verified tarball installation and publishing, see [release instructions](docs/releasing.md).

## Files and privacy

A story workspace contains:

```text
source.md          Original manuscript
preferences.json   Language, length and user preferences
references/        Supplementary material and applicability notes
drafts/            Editable JSON drafts
history/           Preserved submissions
state.json         Progress, approved results and approval records
chapters/          Approved chapter exports
```

Story workspaces and legacy `data/` are excluded from Git and npm packages. Back them up separately. Novel AED does not call a model itself. Its tools run locally, but manuscript content returned by those tools becomes visible to your AI host and may be sent to its model provider under that provider's data policy. Local storage does not mean offline AI processing. Do not include host credentials when sharing diagnostics; installation paths can also reveal personal directory names.

Deterministic checks do not guarantee literary quality, semantic consistency or genuine user approval. The server records the supplied approval message but cannot authenticate its author. Self-review is performed by the same model and is not independent verification.

## CLI and development

The file workflow requires only Python's standard library:

```sh
python scripts/workspace.py init stories/my-story --source /path/to/manuscript.txt --title "My Story"
python scripts/workspace.py status stories/my-story
```

With MCP dependencies installed in your active Python environment:

```sh
npm test
npm run package
python scripts/verify_package.py artifacts
python scripts/smoke_package.py artifacts
```

The smoke test installs the packed distribution in an isolated temporary project and checks MCP calls and persistent storage. CI is configured for Windows/Linux and Python 3.11/3.12. Release publishing is opt-in through the manual release workflow.

## Documentation

- [MCP installation and tools](docs/mcp.md)
- [Workflow and CLI commands](workflow/WORKFLOW.md)
- [Stage instructions](workflow/STAGES.md) and [JSON schemas](workflow/schemas/)
- [Agent rules](AGENTS.md) and [skill](skills/novel-aed/SKILL.md)
- [Research references and limitations](docs/research.md)
- [Distribution and releases](docs/releasing.md)

For legacy databases, use the read-only export procedure in the workflow guide. Historical results are never approved automatically.

## License

[MIT](LICENSE)
