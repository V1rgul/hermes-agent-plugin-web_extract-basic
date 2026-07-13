from __future__ import annotations

import pytest

import dependencies


@pytest.fixture(autouse=True)
def reset_dependency_cache(monkeypatch):
	monkeypatch.setattr(dependencies, "_DEPENDENCIES", None)


def test_load_dependencies_reuses_installed_imports(monkeypatch):
	expected = (object(), lambda value: value)
	install_calls = []

	monkeypatch.setattr(dependencies, "_import_dependencies", lambda: expected)
	monkeypatch.setattr(
		dependencies,
		"_install_dependencies",
		lambda: install_calls.append(True),
	)

	assert dependencies.load_dependencies() is expected
	assert dependencies.load_dependencies() is expected
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

	monkeypatch.setattr(dependencies, "_import_dependencies", fake_import_dependencies)
	monkeypatch.setattr(dependencies, "_install_dependencies", fake_install_dependencies)

	assert dependencies.load_dependencies() is expected
	assert dependencies.load_dependencies() is expected
	assert state == {"installed": True, "install_calls": 1, "import_calls": 2}


def test_uv_installer_is_preferred(monkeypatch):
	calls = []

	def fake_run(command, timeout):
		calls.append((command, timeout))
		return True, "installed"

	monkeypatch.setattr(dependencies, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(dependencies.shutil, "which", lambda name: "/usr/bin/uv")
	monkeypatch.setattr(dependencies, "_run_installer", fake_run)

	dependencies._install_dependencies()

	assert calls == [
		(
			[
				"/usr/bin/uv",
				"pip",
				"install",
				"--python",
				dependencies.sys.executable,
				*dependencies._DEPENDENCY_SPECS,
			],
			300,
		)
	]


def test_disabled_lazy_installs_return_actionable_errors(monkeypatch):
	monkeypatch.setattr(dependencies, "_lazy_installs_allowed", lambda: False)
	monkeypatch.setattr(
		dependencies,
		"_run_installer",
		lambda *args, **kwargs: pytest.fail("installer should not run"),
	)

	with pytest.raises(dependencies.DependencyInstallError) as error:
		dependencies._install_dependencies()

	message = str(error.value)
	assert "lazy installs are disabled" in message
	assert "pip install" in message


def test_pip_fallback_uses_active_python(monkeypatch):
	calls = []

	def fake_run(command, timeout):
		calls.append((command, timeout))
		return True, "ok"

	monkeypatch.setattr(dependencies, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(dependencies.shutil, "which", lambda name: None)
	monkeypatch.setattr(dependencies, "_run_installer", fake_run)

	dependencies._install_dependencies()

	assert calls == [
		([dependencies.sys.executable, "-m", "pip", "--version"], 15),
		(
			[
				dependencies.sys.executable,
				"-m",
				"pip",
				"install",
				*dependencies._DEPENDENCY_SPECS,
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

	monkeypatch.setattr(dependencies, "_lazy_installs_allowed", lambda: True)
	monkeypatch.setattr(dependencies.shutil, "which", lambda name: "/usr/bin/uv")
	monkeypatch.setattr(dependencies, "_run_installer", fake_run)

	dependencies._install_dependencies()

	assert calls[0][0] == "/usr/bin/uv"
	assert calls[1] == [dependencies.sys.executable, "-m", "pip", "--version"]
	assert calls[2][:4] == [dependencies.sys.executable, "-m", "pip", "install"]
