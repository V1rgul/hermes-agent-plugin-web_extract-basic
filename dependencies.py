"""First-use dependency verification and installation."""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import subprocess
import sys
import threading
from typing import Any, Callable

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


def load_dependencies() -> tuple[Any, Callable[[str], Any]]:
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
