"""No-key web extraction via httpx and html-to-markdown."""

from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse

from agent.web_search_provider import WebSearchProvider

if __package__:
	from .dependencies import load_dependencies
else:
	from dependencies import load_dependencies

_CHROME_USER_AGENT = (
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


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
			httpx, convert = await asyncio.to_thread(load_dependencies)
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
			"User-Agent": _CHROME_USER_AGENT,
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
