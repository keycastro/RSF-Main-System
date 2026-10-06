"""Retired Render recovery workflow.

The pre-v1.18.229 recovery tool depended on recoverable account passwords and could
copy the obsolete credential-vault secret into production. That security model is
retired. Use the current verified GitHub main -> Render deployment workflow instead.
"""
from __future__ import annotations


def main() -> int:
    raise SystemExit(
        "SAFE STOP: RECOVER_NEW_RENDER_HOSTING.py is retired as of RSF v1.18.229. "
        "It depended on recoverable passwords. Preserve the database/password hashes "
        "and use the current branch -> CI -> merge -> exact-main Render deployment flow."
    )


if __name__ == "__main__":
    main()
