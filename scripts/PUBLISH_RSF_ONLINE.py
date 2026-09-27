"""Safe source-publish entry point.

Private-workspace releases must never overwrite the current public website source.
The real implementation lives in deploy_render_unified.py so publish and live deploy
share exactly the same source-protection rules.
"""
from __future__ import annotations

from deploy_render_unified import main

if __name__ == "__main__":
    raise SystemExit(main(["--publish-only"]))
