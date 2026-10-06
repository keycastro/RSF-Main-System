"""Source publishing is intentionally disabled.

RSF source changes must go through a branch, GitHub checks, and merge to main.
Use deployment/DEPLOY_RSF_LIVE.bat only after the verified PR is merged.
"""
raise SystemExit(
    "SAFE STOP: direct source publishing to main is disabled. "
    "Use branch -> GitHub CI -> merge, then deploy the exact merged main commit."
)
