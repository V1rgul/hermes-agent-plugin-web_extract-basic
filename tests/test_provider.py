from __future__ import annotations

import asyncio

import pytest

import provider


@pytest.fixture(autouse=True)
def reset_dependency_cache(monkeypatch):
	monkeypatch.setattr(provider, "_DEPENDENCIES", None)


def test_load_dependencies_reuses_installed_imports(monkeypatch):
	expected = (object(), lambda value: value)
	install_calls = []

	monkeypatch.setattr(provider, "_import_dependencies", lambda: expected)
	monkeypatch.setattr(provider, "_install_dependencies", lambda: install_calls.append(True))

	assert provider._load_dependencies() is expected
	assert provider._load_dependencies() is expected
	assert install_calls == []


def test_load_dependencies_installs_once_when_import_is_missing(monkeypatch):
	expected = (object(), lambda value: value)
	state = {"installed": False, "install_calls": 0, "import_calls": 0}

	def fake_import_dependencies():
		state["import_calls"] += 1
		if not state["installed"]:
			raise ImportError("html_to_markdown missing")
		return expected

	def fake_install_dependencies():
		state["install_calls"] += 1
		state["installed"] = True

	monkeypatch.setattr(provider, "_import_dependencies", fake_import_dependencies)
	monkeypatch.setattr(provider, "_install_dependencies", fake_install_dependencies)

	assert provider._load_dependencies() is expected
	assert provider._load_dependencies() is expected
	assert state == {"installed": True, "install_calls": 1, "import_calls": 2}


def test_uv_installer_is_preferred(monkeypatch):
	calls = []

	def fake_run(command, timeout):
		calls.append((command, timeout))
		return True, "installed"

	monkeypatch.setattr(provider, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(provider.shutil, "which", lambda name: "/usr/bin/uv")
	monkeypatch.setattr(provider, "_run_installer", fake_run)

	provider._install_dependencies()

	assert calls == [
		(
			[
				"/usr/bin/uv",
				"pip",
				"install",
				"--python",
				provider.sys.executable,
				*provider._DEPENDENCY_SPECS,
			],
			300,
		)
	]


def test_disabled_lazy_installs_return_actionable_errors(monkeypatch):
	monkeypatch.setattr(provider, "_lazy_installs_allowed", lambda: False)
	monkeypatch.setattr(
		provider,
		"_run_installer",
		lambda *args, **kwargs: pytest.fail("installer should not run"),
	)

	with pytest.raises(provider.DependencyInstallError) as error:
		provider._install_dependencies()

	message = str(error.value)
	assert "lazy installs are disabled" in message
	assert "pip install" in message


def test_pip_fallback_uses_active_python(monkeypatch):
	calls = []

	def fake_run(command, timeout):
		calls.append((command, timeout))
		return True, "ok"

	monkeypatch.setattr(provider, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(provider.shutil, "which", lambda name: None)
	monkeypatch.setattr(provider, "_run_installer", fake_run)

	provider._install_dependencies()

	assert calls == [
		([provider.sys.executable, "-m", "pip", "--version"], 15),
		(
			[
				provider.sys.executable,
				"-m",
				"pip",
				"install",
				*provider._DEPENDENCY_SPECS,
			],
			300,
		),
	]


def test_failed_uv_install_falls_back_to_pip(monkeypatch):
	calls = []

	def fake_run(command, timeout):
		calls.append(command)
		if command[0] == "/usr/bin/uv":
			return False, "uv failed"
		return True, "ok"

	monkeypatch.setattr(provider, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(provider.shutil, "which", lambda name: "/usr/bin/uv")
	monkeypatch.setattr(provider, "_run_installer", fake_run)

	provider._install_dependencies()

	assert calls[0][0] == "/usr/bin/uv"
	assert calls[1] == [provider.sys.executable, "-m", "pip", "--version"]
	assert calls[2][:4] == [provider.sys.executable, "-m", "pip", "install"]


def test_extract_reports_dependency_install_failure_for_each_url(monkeypatch):
	def fail_dependencies():
		raise provider.DependencyInstallError("installer offline; run pip install")

	monkeypatch.setattr(provider, "_load_dependencies", fail_dependencies)
	urls = ["https://example.com", "https://example.org"]
	results = asyncio.run(provider.BasicExtractProvider().extract(urls))

	assert [result["url"] for result in results] == urls
	assert all("dependency setup failed" in result["error"] for result in results)
	assert all("installer offline" in result["error"] for result in results)
