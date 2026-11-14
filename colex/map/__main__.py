"""python -m colex.map: build the Company Map from the configured sources and print its statistics."""
from __future__ import annotations

import json
import time

from colex.config import ConfigStore
from colex.map.build import build


def main() -> None:
    started = time.monotonic()
    stats = build(ConfigStore().active().payload)
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    print(f"built in {time.monotonic() - started:.2f}s")


if __name__ == "__main__":
    main()
