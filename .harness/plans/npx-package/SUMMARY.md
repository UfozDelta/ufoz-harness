# npx-package

`export_kit.py` rebuilds `kit/` from the repo (settings, six-executor harness, both
skill trees, notices); `index.js` copies it into a project, backing up changed files
and appending `.harness/.env` to `.gitignore`. `package.json` 0.3.0 adds
`prepack` (build kit) and `test`. Docs: package README, kit README, third-party
notices (frontend-design is Apache-2.0). BUILD: pass
