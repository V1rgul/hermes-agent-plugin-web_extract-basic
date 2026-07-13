"""No-key web extraction via httpx and html-to-markdown."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import shutil
import subprocess
import sys
import threading
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_DEPENDENCY_SPECS = (
	"httpx>=0.28,<1",
	"html-to-markdown>=3.8,<4",
)
_DEPENDENCY_LOCK = threading.Lock()
_DEPENDENCIES: tuple[Any, Callable[[str], Any]] | None = None


class DependencyInstallError(RuntimeError):
	"""Raised when the plugin cannot install its optional dependencies."""


def _manual_install_command() -> str:
	return f'"{sys.executable}" -m pip install ' + " ".join(
		f"'{spec}'" for spec in _DEPENDENCY_SPECS
	)


def _install_error(detail: str) -> DependencyInstallError:
	detail = detail.strip()[-2000:] if detail.strip() else "unknown installer error"
	return DependencyInstallError(
		f"Could not install Basic Web Extract dependencies: {detail}. "
		f"Install them manually with: {_manual_install_command()}"
	)


def _lazy_installs_allowed() -> bool:
	"""Honor Hermes' lazy-install opt-out."""
	try:
		from hermes_cli.config import load_config

		config = load_config()
		security = config.get("security") or {}
		if not bool(security.get("allow_lazy_installs", True)):
			return False
	except Exception:
		pass

	return os.environ.get("HERMES_DISABLE_LAZY_INSTALLS") != "1"


def _run_installer(command: list[str], timeout: int) -> tuple[bool, str]:
	try:
		result = subprocess.run(
			command,
			capture_output=True,
			text=True,
			timeout=timeout,
			stdin=subprocess.DEVNULL,
		)
	except (OSError, subprocess.SubprocessError) as exc:
		return False, str(exc)

	detail = (result.stderr or result.stdout).strip()
	return result.returncode == 0, detail


def _install_dependencies() -> None:
	"""Install the plugin's fixed dependency set into the active environment."""
	if not _lazy_installs_allowed():
		raise _install_error(
			"lazy installs are disabled by security.allow_lazy_installs or the runtime environment"
		)

	errors: list[str] = []
	uv = shutil.which("uv")
	if uv:
		success, detail = _run_installer(
			[uv, "pip", "install", "--python", sys.executable, *_DEPENDENCY_SPECS],
			300,
		)
		if success:
			return
		errors.append(f"uv: {detail}")

	pip_command = [sys.executable, "-m", "pip"]
	pip_ready, detail = _run_installer([*pip_command, "--version"], 15)
	if not pip_ready:
		bootstrap_ok, bootstrap_detail = _run_installer(
			[sys.executable, "-m", "ensurepip", "--upgrade", "--default-pip"],
			120,
		)
		if not bootstrap_ok:
			errors.append(f"ensurepip: {bootstrap_detail or detail}")
			raise _install_error("\n".join(errors))

	success, detail = _run_installer(
		[*pip_command, "install", *_DEPENDENCY_SPECS],
		300,
	)
	if not success:
		errors.append(f"pip: {detail}")
		raise _install_error("\n".join(errors))


def _import_dependencies() -> tuple[Any, Callable[[str], Any]]:
	httpx = importlib.import_module("httpx")
	converter = importlib.import_module("html_to_markdown")
	convert = getattr(converter, "convert")
	return httpx, convert


def _load_dependencies() -> tuple[Any, Callable[[str], Any]]:
	"""Import dependencies, installing them once on the first missing import."""
	global _DEPENDENCIES

	if _DEPENDENCIES is not None:
		return _DEPENDENCIES

	with _DEPENDENCY_LOCK:
		if _DEPENDENCIES is not None:
			return _DEPENDENCIES
		try:
			_DEPENDENCIES = _import_dependencies()
		except ImportError:
			logger.info(
				"Basic Web Extract dependencies missing; installing: %s",
				", ".join(_DEPENDENCY_SPECS),
			)
			_install_dependencies()
			importlib.invalidate_caches()
			try:
				_DEPENDENCIES = _import_dependencies()
			except ImportError as exc:
				raise _install_error(
					f"installation completed but dependencies still cannot be imported: {exc}"
				) from exc
		return _DEPENDENCIES


class _TitleParser(HTMLParser):
	def __init__(self) -> None:
		super().__init__()
		self._in_title = False
		self._parts: list[str] = []

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		if tag.lower() == "title":
			self._in_title = True

	def handle_endtag(self, tag: str) -> None:
		if tag.lower() == "title":
			self._in_title = False

	def handle_data(self, data: str) -> None:
		if self._in_title:
			self._parts.append(data)

	@property
	def title(self) -> str:
		return " ".join("".join(self._parts).split())


def _page_title(html: str) -> str:
	parser = _TitleParser()
	try:
		parser.feed(html)
	except Exception:
		return ""
	return parser.title


class BasicExtractProvider(WebSearchProvider):
	"""Fetch HTML directly and convert it to Markdown locally."""

	@property
	def name(self) -> str:
		return "basic"

	@property
	def display_name(self) -> str:
		return "Basic Web Extract"

	def is_available(self) -> bool:
		# The provider remains selectable before dependencies exist because its
		# first extraction installs them lazily.
		return True

	def supports_search(self) -> bool:
		return False

	def supports_extract(self) -> bool:
		return True

	def _base_result(self, url: str) -> dict[str, Any]:
		return {
			"url": url,
			"title": "",
			"content": "",
			"raw_content": "",
			"metadata": {"sourceURL": url, "provider": self.name},
		}

	async def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
		if not urls:
			return []

		try:
			httpx, convert = await asyncio.to_thread(_load_dependencies)
		except Exception as exc:
			return [
				{
					**self._base_result(url),
					"error": f"Basic extraction dependency setup failed: {exc}",
				}
				for url in urls
			]

		timeout = httpx.Timeout(30.0, connect=10.0)
		limits = httpx.Limits(max_connections=min(max(len(urls), 1), 10))
		headers = {
			"User-Agent": (
				"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
				"(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HermesBasicExtract/1.0"
			),
			"Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
		}

		async with httpx.AsyncClient(
			follow_redirects=True,
			headers=headers,
			limits=limits,
			timeout=timeout,
		) as client:
			return await asyncio.gather(
				*(self._extract_one(client, convert, url) for url in urls)
			)

	async def _extract_one(
		self,
		client: Any,
		convert: Callable[[str], Any],
		url: str,
	) -> dict[str, Any]:
		base = self._base_result(url)
		if urlparse(url).scheme.lower() not in {"http", "https"}:
			return {**base, "error": "Only http:// and https:// URLs are supported"}

		try:
			response = await client.get(url)
			response.raise_for_status()
			content_type = response.headers.get("content-type", "").lower()
			text = response.text
			is_html = "html" in content_type or "<html" in text[:1000].lower()
			title = _page_title(text) if is_html else ""
			markdown = convert(text).content.strip() if is_html else text.strip()

			final_url = str(response.url)
			return {
				"url": final_url,
				"title": title,
				"content": markdown,
				"raw_content": markdown,
				"metadata": {
					"sourceURL": final_url,
					"title": title,
					"contentType": content_type,
					"statusCode": response.status_code,
					"provider": self.name,
				},
			}
		except Exception as exc:
			return {**base, "error": f"Basic extraction failed: {exc}"}

	def get_setup_schema(self) -> dict[str, Any]:
		return {
			"name": self.display_name,
			"badge": "free",
			"tag": "Direct HTTP fetch + local HTML-to-Markdown conversion; no API key.",
			"env_vars": [],
		}
