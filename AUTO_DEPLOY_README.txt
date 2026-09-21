REALTY SYSTEMS FOUNDRY WEBSITE v3.9.8 - ONE CMD AUTO DEPLOY

v3.9.8 securely copies the original Render production environment variables and secret files before deploying the replacement hostname service. If RENDER_API_KEY is not already present in the CMD session, the updater will ask once with hidden input. The key is used only in memory and is not saved by this updater.

---

HISTORICAL v3.9.3 AUTO DEPLOY NOTES

1. Extract the release ZIP.
2. Open CMD.
3. Run the single command provided with the release.

The included updater preserves private local data, runs the complete test suite, clones the existing Render service configuration into a new service named realtysystemsfoundry, verifies the exact new hostname plus private RSF Inbox/database continuity, records the replacement service ID, commits approved files, pushes both GitHub remotes, deploys the exact release commit to the replacement service, updates the private RSF Inbox API base while preserving its token, and verifies https://realtysystemsfoundry.onrender.com before reporting success.

The local project remains Documents\REALTY_SYSTEMS_FOUNDRY. GitHub repository names remain unchanged. The migration creates a replacement Render service with a new service ID and keeps the original service as rollback.


## v3.9.3 Render hostname migration correction

Production testing proved that changing the original Render service name did not reassign its existing `onrender.com` hostname. The approved target remains `https://realtysystemsfoundry.onrender.com`. v3.9.3 therefore creates a new Render service by cloning the original service configuration with Render CLI `services create --from`, verifies the new public host and the private RSF Inbox/database continuity, then records the replacement service ID for future deployments. The original service is retained as `realtysystemsfoundry-legacy` for rollback and is not deleted automatically. Public design, systems, and pricing are unchanged.
