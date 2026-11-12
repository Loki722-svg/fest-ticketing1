# College Fest Event Management & Ticketing Platform

![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)
<!-- Replace OWNER/REPO with your GitHub username and repository name -->

Students browse fest events, register, pay (mock) and receive a QR e-ticket.
Organizers get a dashboard with registrations, revenue and QR check-in.

## Architecture
```
Browser ──> frontend (nginx :8080) ──/api──> booking-service (FastAPI :8000) ──> PostgreSQL
                                                   │
                                                   └──> payment-service (mock, :8001)
```

## Run it
```bash
docker compose up --build
```
- App: http://localhost:8080
- Booking API docs: http://localhost:8000/docs
- Payment mock: http://localhost:8001/docs

## Run tests
```bash
cd booking-service
pip install -r requirements.txt
pytest
```

## CDD modules covered
| Module | Where |
|---|---|
| Git / GitHub | `CONTRIBUTING.md`, PR template, Issues + Projects board |
| DevOps / CI-CD | `.github/workflows/ci.yml` (lint, tests, integration test on every PR), `deploy.yml` (publish images + deploy on merge to `main`), branch protection and CODEOWNERS |
| IaC | `terraform/main.tf` (cloud VM + image bucket) |
| Docker | one Dockerfile per service, `docker-compose.yml`, images pushed to GHCR |
| UX Design Thinking | `docs/ux-research.md` |
| Figma / UX factors | Figma prototype link in `docs/ux-research.md` |

## CI/CD
Every Pull Request runs lint, backend tests, a frontend check and a full Docker integration test
(`scripts/smoke-test.sh`). Merging into `main` publishes the Docker images to GitHub Container Registry
and deploys to the server. Full explanation, team setup and troubleshooting: [`docs/CICD.md`](docs/CICD.md).
Team rules: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Provision the server with `cd terraform && terraform init && terraform apply`.
