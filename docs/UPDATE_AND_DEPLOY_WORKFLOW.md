# Update and Deploy Workflow — One Run Is the Default

From this release forward, a KEY CASTRO website update package should include:

```text
APPLY_UPDATE_AND_DEPLOY_LIVE.bat
scripts/UPDATE_AND_DEPLOY_RENDER.ps1
```

The normal workflow is no longer "install locally now, deploy later." The release launcher performs the sequence automatically:

1. Copy/update the website in `Documents\KEY_CASTRO_WEBSITE` while preserving the private `.env`.
2. Install dependencies and run the complete automated test suite.
3. Confirm the existing Git repo is on `main` and has the required `origin` and `renderdeploy` remotes.
4. Stage only the approved source/release paths and block private/runtime files.
5. Commit the release when there are source changes.
6. Push `origin main` and `renderdeploy main`.
7. Trigger Render service `srv-dam749e1egvs738cppq0` and wait for completion.
8. Verify the production health endpoint and the live Systems page before reporting success.

Render's provider-level **auto-deploy setting remains off**. Automatic deployment is intentionally handled by the controlled release script so tests and safety checks happen before production is triggered.

## One-CMD package execution

The user downloads the release ZIP and runs the supplied one-time extraction command. That command locates `APPLY_UPDATE_AND_DEPLOY_LIVE.bat` inside the release and executes it. No separate deploy command should be required after a successful run.

## Safety rules

The release script must never stage or deploy private/runtime material such as `.env`, `.owner_inbox.json`, `.venv`, local databases, logs, or `instance` runtime data. The private owner inbox remains part of the same Flask service and its secrets stay outside source control.

If Git/Render authentication has expired, the one-run workflow may require the provider's normal authentication interaction. It must stop with an explicit error rather than claim the website is live.
