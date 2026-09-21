# UPDATE AND DEPLOY WORKFLOW — v3.9.8

The Render hostname migration now treats optional/empty collections as valid in Windows PowerShell 5.1. Required production settings are reconstructed and validated, malformed legacy env keys are ignored, and the final environment-variable payload is built directly before the replacement service is configured and verified. Secrets remain memory-only.

---

# Update and Deploy Workflow — One Run Is the Default

From this release forward, a Realty Systems Foundry website update package should include:

```text
APPLY_UPDATE_AND_DEPLOY_LIVE.bat
scripts/UPDATE_AND_DEPLOY_RENDER.ps1
```

The normal workflow is no longer "install locally now, deploy later." The release launcher performs the sequence automatically:

1. Safely migrate `Documents\KEY_CASTRO_WEBSITE` to `Documents\REALTY_SYSTEMS_FOUNDRY` when needed, then copy/update approved website files while preserving private local configuration and Git metadata.
2. Install dependencies and run the complete automated test suite.
3. Confirm the existing Git repo is on `main` and has the required `origin` and `renderdeploy` remotes.
4. Stage only the approved source/release paths and block private/runtime files.
5. Commit the release when there are source changes.
6. Push `origin main` and `renderdeploy main`.
7. Resolve the active `realtysystemsfoundry` Render service ID from the v3.9.3 migration state, deploy the exact release commit, and wait for completion.
8. Verify the production health endpoint and the live Systems page before reporting success.

Render's provider-level **auto-deploy setting remains off**. Automatic deployment is intentionally handled by the controlled release script so tests and safety checks happen before production is triggered.

## One-CMD package execution

The user downloads the release ZIP and runs the supplied one-time extraction command. That command locates `APPLY_UPDATE_AND_DEPLOY_LIVE.bat` inside the release and executes it. No separate deploy command should be required after a successful run.

## Safety rules

The release script must never stage or deploy private/runtime material such as `.env`, `.owner_inbox.json`, `.venv`, local databases, logs, or `instance` runtime data. The private owner inbox remains part of the same Flask service and its secrets stay outside source control.

If Git/Render authentication has expired, the one-run workflow may require the provider's normal authentication interaction. It must stop with an explicit error rather than claim the website is live.


### v3.9.3 hostname migration
The original service ID `srv-dam749e1egvs738cppq0` is now treated as the legacy rollback source. The migration workflow clones its configuration into a new service named `realtysystemsfoundry`, verifies `https://realtysystemsfoundry.onrender.com`, verifies the private owner API using the locally preserved token, writes the replacement service ID to `PROJECT_STATE.json`, and then deploys future releases to the replacement service.
