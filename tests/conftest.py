from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run_cli():
    def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        process_env = os.environ.copy()
        process_env.update(env or {})
        return subprocess.run(
            [sys.executable, "-m", "kaapi", *args],
            cwd=ROOT,
            env=process_env,
            text=True,
            capture_output=True,
            check=False,
        )
    return run
