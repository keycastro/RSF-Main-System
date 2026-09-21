REALTY SYSTEMS FOUNDRY WEBSITE v3.9.2 - ONE CMD AUTO DEPLOY

1. Extract the release ZIP.
2. Open CMD.
3. Run the single command provided with the release.

The included updater preserves private local data, runs the complete test suite, renames the EXISTING Render service to realtysystemsfoundry, confirms the new hostname, commits approved files, pushes both GitHub remotes, triggers Render deployment, updates the private RSF Inbox API base while preserving its token, and verifies https://realtysystemsfoundry.onrender.com before reporting success.

The local project remains Documents\REALTY_SYSTEMS_FOUNDRY. GitHub repository names and the Render service ID remain unchanged.
