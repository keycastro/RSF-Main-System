REALTY SYSTEMS FOUNDRY WEBSITE v3.9.1 - ONE CMD AUTO DEPLOY

1. Extract the release ZIP.
2. Open CMD.
3. Run the single command provided with the release.

The included updater copies approved files into Documents\REALTY_SYSTEMS_FOUNDRY, preserves private .env/runtime data, installs dependencies, runs the complete test suite, commits approved files, pushes GitHub remotes, triggers the existing Render service, and verifies the live v3.9.1 rebrand before reporting success.

The updater safely migrates the old KEY_CASTRO_WEBSITE folder to REALTY_SYSTEMS_FOUNDRY when needed, preserving private local state and Git metadata.
