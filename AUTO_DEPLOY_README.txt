REALTY SYSTEMS FOUNDRY WEBSITE v3.9.0 - ONE CMD AUTO DEPLOY

1. Extract the release ZIP.
2. Open CMD.
3. Run the single command provided with the release.

The included updater copies approved files into Documents\KEY_CASTRO_WEBSITE, preserves private .env/runtime data, installs dependencies, runs the complete test suite, commits approved files, pushes GitHub remotes, triggers the existing Render service, and verifies the live v3.9.0 rebrand before reporting success.

The internal local project folder name remains KEY_CASTRO_WEBSITE for deployment compatibility.
