# Agent Rules — voitomo-audioviz

## Core rule
Code flows one way only: local branch -> Pull Request -> `main` -> CI/CD -> server.
Nothing flows backward. Servers never hold their own version of the code.

## Hard rules
1. Never modify, create, delete, or upload files on any remote server (SSH, scp, rsync, sftp, or otherwise). Server changes happen only through CI/CD.
2. SSH is read-only for inspection (logs, `git status`, `git log`, `ls`, `cat`, process status). No state-changing commands (no edits, `git pull/checkout/reset`, installs, restarts) unless the user explicitly asks in that message.
3. Never commit or push directly to `main`. Work on a feature branch and open a PR.
4. Never force-push, `git reset --hard`, rebase published branches, or bulk-delete branches or files without explicit confirmation.
5. Before any task: `git fetch`, check `git status`, and confirm the branch is based on the latest `origin/main`. If the tree is dirty, behind, or diverged, report it before changing anything.
6. Never overwrite a file with an older version. If a file differs unexpectedly, stop and show the diff.
7. Never commit secrets (`.env`, keys, tokens). Configuration and secrets live in environment variables or a secrets manager. `.env` is git-ignored; keep it that way.
8. Small, focused commits in Conventional Commits form (`feat:`, `fix:`, `chore:`, `docs:`).
9. If a task seems to require touching a server or production data, stop and ask.

## Stack
- **Bot (Python 3.11+):** aiogram Telegram bot in `bot/` (routers, services). Entry points: `audioviz_bot_run.py`, `bot_run.py`, `bot/main.py`.
- **Renderer (TypeScript, Node 20):** Remotion/three.js render server in `renderer/`, entry `renderer/server.ts`.
- **GPU workers:** Vast.ai lifecycle in `bot/services/vast_lifecycle.py`. Whisper and alignment run on GPU via `vast_ai_service.py`.
- **Docker:** not used. Services run from shell scripts (`start.sh`, `run_audioviz_supervisor.sh`, `gpu_start_services.sh`).

## Setup, test, lint
Python (tests use `unittest` and `pytest`; CI installs pytest):
```bash
pip install pytest pytest-asyncio pydantic aiohttp aiogram librosa soundfile
PYTHONPATH=. python3 -m unittest tests.test_audio_gpu_workflow tests.test_gpu_lifecycle
PYTHONPATH=. python -m pytest tests/test_music_engine.py tests/test_end_to_end_manifest.py
```

Renderer:
```bash
cd renderer && npm ci && npx tsc --noEmit
```

Lint: no linter is configured yet. Before finalizing a change, run the checks above plus `python3 -m py_compile` on each changed Python file.

## Branching and PR workflow
1. Sync: `git fetch`, verify a clean status, branch from the latest `origin/main`.
2. Branch: `feat/<short-name>` or `fix/<short-name>`.
3. Change the code, then run the tests and checks locally.
4. Commit, push the branch, and open a PR with a description of what changed and why.
5. Stop. The owner reviews and merges. Nothing deploys manually.

## Deployment
- Deploys happen only via CI/CD. Agents never deploy manually, and never copy files to a server.
- The server copy at `/root/audioviz` is not a git checkout. Treat it as unmanaged until CI/CD replaces it.
- CI (`.github/workflows/ci.yml`) runs tests and the renderer type check on PRs and pushes to `main`. It has no deploy job yet.
- Rollback will be by redeploying a previous commit SHA once CI/CD exists. Do not improvise rollbacks.
