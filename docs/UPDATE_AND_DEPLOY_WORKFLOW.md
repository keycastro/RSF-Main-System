# Update and Deploy Workflow — CMD First

Work only from:

```cmd
cd /d "%USERPROFILE%\Documents\KEY_CASTRO_WEBSITE"
```

Before commit, inspect changes and confirm no `.env`, `.owner_inbox.json`, database URL, passwords, tokens, logs, or private inquiry data are staged.

```cmd
git status
git add <approved files only>
git status
git commit -m "Describe the website update"
git push origin main
git push renderdeploy main
render deploys create srv-dam749e1egvs738cppq0 --wait --confirm -o text
curl -fsS https://keycastro.onrender.com/system/health
```

Render auto-deploy remains off. PythonAnywhere remains retired.

## Owner inbox

The online private owner inbox is part of the same Flask service. Keep `.owner_inbox.json` local and gitignored. Use the `KEY CASTRO INBOX` desktop shortcut rather than exposing an owner/login link on the public site.
