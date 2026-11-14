"""The PayRo code as it is on disk in the sandbox repository, and a way to run it.

The app runs the files in the repository folder itself, on every request, so it always runs whatever is
checked out there (normally `main`). Nothing is copied or cached: after a merge, the next request runs
the merged code. The code runs in a subprocess with a scrubbed environment and no network, like the
coder's tests. File access is not sandboxed, so use this on a demo machine only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from colex import testrunner

TELLER = Path(__file__).with_name("teller.py")


class Checkout:
    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()

    def exists(self) -> bool:
        return (self.repo / "payments").is_dir()

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run the teller inside the repository folder, so `import payments` loads the files checked out there."""
        cmd = [sys.executable, "-B", str(TELLER)]
        if testrunner.network_namespace():
            cmd = ["unshare", "-rn", *cmd]
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(testrunner.BLOCKER), "PYTHONDONTWRITEBYTECODE": "1",
               "LC_ALL": "C.UTF-8"}
        try:
            done = subprocess.run(cmd, cwd=self.repo, env=env, input=json.dumps(request), capture_output=True,
                                  text=True, timeout=20)
            out = json.loads(done.stdout.strip().splitlines()[-1])   # the answer is the last line printed
        except subprocess.TimeoutExpired:
            return {"error": "the code did not answer within 20 seconds"}
        except (ValueError, IndexError, OSError) as exc:
            return {"error": f"the code could not be run: {type(exc).__name__}"}
        return out if isinstance(out, dict) else {"error": "the code gave an unexpected answer"}
