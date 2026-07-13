from __future__ import annotations

import asyncio

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
