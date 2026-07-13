# Basic Web Extract for Hermes Agent

A free, local [`web_extract`](https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin) backend for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

It fetches pages directly with [`httpx`](https://www.python-httpx.org/) and converts HTML to Markdown with [`html-to-markdown`](https://pypi.org/project/html-to-markdown/). It requires no API key or external extraction service.

## Features

- Direct HTTP/HTTPS fetching
- Concurrent extraction of multiple URLs
- Local HTML-to-Markdown conversion
- Redirect handling
- HTML title and response metadata extraction
- Per-URL error handling
- Plain-text response support

## Installation

Install, enable, and select the plugin with one command:

```bash
hermes plugins install V1rgul/hermes-agent-plugin-web_extract-basic --enable && hermes config set web.extract_backend basic
```

On the first `web_extract` call, the plugin checks whether `httpx` and `html-to-markdown` are importable. If either is missing, it installs both into the active Hermes Python environment and then continues the extraction. Later calls reuse the installed packages.

Automatic installation follows Hermes' `security.allow_lazy_installs` setting. If lazy installation is disabled or package installation fails, `web_extract` returns the installer error and a manual installation command.

Then start a new Hermes session. If you use the messaging gateway, restart it:

```bash
hermes gateway restart
```

## Alternative pip installation

The repository is also a Python package. Installing it into the Hermes virtual environment installs its dependencies eagerly and registers the same plugin through a Python entry point:

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python" -m pip install --upgrade 'git+https://github.com/V1rgul/hermes-agent-plugin-web_extract-basic.git' && hermes plugins enable web-basic-web_extract && hermes config set web.extract_backend basic
```

## Requirements

- Hermes Agent with web-search provider plugin support
- Python 3.10+
- `httpx>=0.28,<1`
- `html-to-markdown>=3.8,<4`

## Limitations

- Supports extraction only, not web search.
- Fetches static HTTP responses; it does not execute JavaScript.
- Supports `http://` and `https://` URLs only.
