from __future__ import annotations

import asyncio
from types import SimpleNamespace

import provider


def test_extract_reports_dependency_install_failure_for_each_url(monkeypatch):
	def fail_dependencies():
		raise RuntimeError("installer offline; run pip install")

	monkeypatch.setattr(provider, "load_dependencies", fail_dependencies)
	urls = ["https://example.com", "https://example.org"]
	results = asyncio.run(provider.BasicExtractProvider().extract(urls))

	assert [result["url"] for result in results] == urls
	assert all("dependency setup failed" in result["error"] for result in results)
	assert all("installer offline" in result["error"] for result in results)


def test_extract_uses_chrome_user_agent(monkeypatch):
	captured = {}

	class FakeTimeout:
		def __init__(self, *args, **kwargs):
			pass

	class FakeLimits:
		def __init__(self, *args, **kwargs):
			pass

	class FakeResponse:
		headers = {"content-type": "text/html"}
		text = "<html><head><title>Example</title></head><body>OK</body></html>"
		url = "https://example.com"
		status_code = 200

		def raise_for_status(self):
			pass

	class FakeAsyncClient:
		def __init__(self, **kwargs):
			captured.update(kwargs)

		async def __aenter__(self):
			return self

		async def __aexit__(self, exc_type, exc_value, traceback):
			pass

		async def get(self, url):
			return FakeResponse()

	fake_httpx = SimpleNamespace(
		Timeout=FakeTimeout,
		Limits=FakeLimits,
		AsyncClient=FakeAsyncClient,
	)
	convert = lambda html: SimpleNamespace(content="OK")
	monkeypatch.setattr(provider, "load_dependencies", lambda: (fake_httpx, convert))

	results = asyncio.run(
		provider.BasicExtractProvider().extract(["https://example.com"])
	)

	assert not results[0].get("error"), results
	assert captured["headers"]["User-Agent"] == (
		"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
	)
	assert captured["headers"]["Accept"].startswith("text/html")
