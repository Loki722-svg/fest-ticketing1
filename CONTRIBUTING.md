# Contributing Guide (team of 5)

## Branches
| Branch | Purpose | Who pushes |
|---|---|---|
| `main` | Stable, always working. A merge here publishes Docker images (and deploys, once a server is set up). | Nobody directly: only through a Pull Request from `dev` |
| `dev` | Integration branch where everyone's work meets. | Nobody directly: only through Pull Requests |
| `feature/<short-name>` | Your own work, e.g. `feature/qr-checkin`, `fix/sold-out-message` | You |

## Your daily workflow
```bash
git checkout dev && git pull                 # start from the latest dev
git checkout -b feature/<short-name>         # your own branch
# ...make changes, then:
git add . && git commit -m "feat: add team registration form"
git push -u origin feature/<short-name>
```
1. Open a **Pull Request** into `dev` on GitHub and link your issue (`Closes #12`).
2. Wait for the **CI Passed** check to turn green.
3. A teammate reviews it and clicks **Approve** (you can't approve your own PR).
4. Click **Squash and merge**, then delete the branch.
5. To release: the lead opens a PR from `dev` into `main`; same rules apply.

Commit message prefixes: `feat:` new feature, `fix:` bug fix, `test:` tests, `docs:` documentation, `ci:` pipeline, `chore:` anything else.

## What CI checks on every PR
Lint (flake8), 25+ backend tests, frontend JavaScript syntax, and a **Docker integration test** that starts the whole stack and walks through browse, login, register, pay, QR ticket and check-in. All must pass before merging. See `docs/CICD.md`.

Run the same checks on your laptop before pushing:
```bash
cd booking-service && python -m pytest -q           # tests
flake8 booking-service payment-service              # style (pip install flake8)
docker compose up -d --build && bash scripts/smoke-test.sh   # full stack
```

## Review checklist (also in the PR template)
- [ ] CI Passed (green)
- [ ] Tests added or updated for new behaviour
- [ ] No secrets, passwords or API keys committed
- [ ] Code is readable and matches the project style
- [ ] README / docs updated if needed
- [ ] PR is small and focused on one change

## Team roles
Replace the names with your own. `.github/CODEOWNERS` uses the same split to request the right reviewer automatically.

| Member | Role | Owns |
|---|---|---|
| Member 1 | Lead / DevOps | `.github/`, `terraform/`, `scripts/`, repo settings |
| Member 2 | Backend | `booking-service/`, database, tests |
| Member 3 | Docker / Payments | `payment-service/`, Dockerfiles, `docker-compose.yml`, registry |
| Member 4 | Frontend | `frontend/`, admin panel |
| Member 5 | UX | `docs/` research, personas, Figma prototype, usability tests |
