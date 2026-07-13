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

## Installation with automatic dependencies

Install the package into the Hermes Python environment. `pip` installs `httpx` and `html-to-markdown` automatically from the dependencies declared in `pyproject.toml`:

```bash
~/.hermes/hermes-agent/venv/bin/python -m pip install \
	git+https://github.com/V1rgul/hermes-agent-plugin-web_extract-basic.git
```

Enable the plugin and select it as the extraction backend:

```bash
hermes plugins enable web-basic-web-extract
hermes config set web.extract_backend basic
```

Then start a new Hermes session. If you use the messaging gateway, restart it:

```bash
hermes gateway restart
```

> The standard `hermes plugins install owner/repo` command clones plugin files but currently does not install packages from `requirements.txt`. Use the `pip install git+…` command above when you want dependencies installed automatically.

## Manual Git installation

```bash
git clone https://github.com/V1rgul/hermes-agent-plugin-web_extract-basic.git \
	~/.hermes/plugins/web/basic_web_extract
~/.hermes/hermes-agent/venv/bin/python -m pip install -r \
	~/.hermes/plugins/web/basic_web_extract/requirements.txt
hermes plugins enable web/basic_web_extract
hermes config set web.extract_backend basic
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
