# adkx — ADK Extension Toolkit

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

An extension toolkit for [Google ADK (Agent Development Kit)](https://github.com/google/adk-python) that simplifies agent development with preset state injection and sub-agent promotion.

## Features

- **Preset Injection** — Automatically inject initial state into sessions via `preset.yaml`
- **Sub-Agent Promotion** — Expose sub-agents as standalone apps in the Web UI
- **Drop-in CLI** — `adkx web` wraps `adk web` with extension features enabled by default

## Installation

```bash
pip install git+https://github.com/Koichi73/adkx.git
```

## Quick Start

**1. Initialize preset config**

```bash
adkx init ./my_agents
```

**2. Edit `preset.yaml`**

```yaml
initial_state:
  api_key: "your-api-key"
  mode: "production"

promote_agents:
  search_agent: {}
  summary_agent:
    module: sub_agents.summary
```

- `initial_state` — key-value pairs injected into every new session
- `promote_agents` — sub-agents to expose as independent apps in the Web UI

**3. Start the server**

```bash
adkx web ./my_agents
```

Open `http://127.0.0.1:8000` — you'll see your agents (including promoted sub-agents) in the dropdown.

## CLI Reference

| Command | Description |
|---------|-------------|
| `adkx init [DIR]` | Create a `preset.yaml` template in the specified directory |
| `adkx web AGENTS_DIR` | Start the ADK Web UI with extension features |

### `adkx web` options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Binding host |
| `--port` | `8000` | Server port |
| `--preset / --no-preset` | `--preset` | Enable/disable preset state injection |
| `--reload / --no-reload` | `--reload` | Enable/disable auto-reload |
| `-v, --verbose` | off | Enable DEBUG logging |

All other `adk web` options (CORS, Cloud Trace, session/artifact/memory service URIs, etc.) are also supported.

## How It Works

### Preset Injection

`PresetMiddleware` intercepts `POST /apps/{app_name}/users/{user_id}/sessions` requests and merges `initial_state` from `preset.yaml` into the session. Client-provided values always take priority.

### Sub-Agent Promotion

On startup, `adkx web` reads `promote_agents` from `preset.yaml` and generates alias directories so sub-agents appear as top-level apps in the Web UI. These directories are automatically cleaned up on exit.

## Requirements

- Python 3.11+
- [google-adk](https://github.com/google/adk-python) >= 1.27.1

## License

[Apache License 2.0](LICENSE)
