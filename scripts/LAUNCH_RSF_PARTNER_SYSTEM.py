"""Open the production RSF website or private Workspace in the default browser."""
from __future__ import annotations

import sys
import webbrowser

PUBLIC_URL = "https://realtysystemsfoundry.onrender.com/"
WORKSPACE_URL = "https://realtysystemsfoundry.onrender.com/app/"


def main() -> int:
    destination = PUBLIC_URL if "--website" in sys.argv else WORKSPACE_URL
    opened = webbrowser.open(destination)
    if not opened:
        print(f"Open this URL in your browser: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
