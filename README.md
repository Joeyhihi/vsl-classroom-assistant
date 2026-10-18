# VSL Classroom Assistant

A local-first web app that helps Deaf and hard-of-hearing students communicate with hearing teachers and classmates. It does this in three ways:

- **Sign to speech.** It recognises a **small, expert-validated vocabulary** of Vietnamese Sign Language (VSL) message units from a webcam and shows them as Vietnamese text. It speaks the text aloud only **after the student confirms**.
- **Speech to subtitles.** It turns spoken Vietnamese into subtitles. This feature is gated and planned for later.
- **Manual text.** It always offers manual text as a fallback.

> **Status: Phase 1 (Foundation).** Sign recognition does **not** exist yet. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Honest limitations

- This is **not a translator**. It classifies a closed list of 20–50 message units, one at a time, and the signer returns their hands to rest between units.
- **Accuracy is not promised.** It will be measured on signers the model has never seen.
- The MVP is for **adult participants only**. School use with minors needs institutional and legal approval first.
- **Privacy:** video stays in the browser by default. Nothing is recorded outside the consented data-collection mode.

## Quickstart (macOS and Windows)

Prerequisites: Git, [uv](https://docs.astral.sh/uv/), and Node 24 LTS. uv installs Python 3.12 for you.

```bash
uv run python scripts/bootstrap.py     # install dependencies, create .env
uv run python scripts/run_backend.py   # terminal 1: backend on http://127.0.0.1:8000 (mock model mode)
uv run python scripts/run_web.py       # terminal 2: frontend on http://localhost:5173
uv run python scripts/check.py         # all quality gates
```

The development Mac (M1, 8 GB) runs **mock mode and unit tests only**. The real AI pipeline is tested on the Windows laptop. Details are in [docs/CROSS_PLATFORM_SETUP.md](docs/CROSS_PLATFORM_SETUP.md).

## Repository layout

```
apps/web/              React + TypeScript + Vite frontend
services/ai-backend/   FastAPI backend (Python 3.12)
packages/vsl-features/ shared preprocessing (from Phase 3)
ml/                    training & evaluation (from Phase 4–5; data lives outside the repo)
model-artifacts/       local model files (gitignored)
scripts/               cross-platform helper scripts
docs/                  planning & architecture documents
```

## Documentation

| | |
|---|---|
| [Project overview](docs/PROJECT_OVERVIEW.md) | [Requirements](docs/REQUIREMENTS.md) |
| [Architecture](docs/ARCHITECTURE.md) | [Repository structure](docs/REPOSITORY_STRUCTURE.md) |
| [API contracts](docs/API_CONTRACTS.md) | [AI/ML strategy](docs/AI_ML_STRATEGY.md) |
| [Dataset & annotation](docs/DATASET_AND_ANNOTATION.md) | [UX & accessibility](docs/UX_AND_ACCESSIBILITY.md) |
| [Security & privacy](docs/SECURITY_AND_PRIVACY.md) | [Cross-platform setup](docs/CROSS_PLATFORM_SETUP.md) |
| [Testing strategy](docs/TESTING_STRATEGY.md) | [Roadmap](docs/ROADMAP.md) |
| [Decisions (ADRs)](docs/DECISIONS.md) | [Risks & open questions](docs/RISKS_AND_OPEN_QUESTIONS.md) |

## Contributing data

This repository is **public**. It never contains real sign recordings, landmarks, names, manifests, or consent records. Test fixtures are synthetic. See [docs/DATASET_AND_ANNOTATION.md](docs/DATASET_AND_ANNOTATION.md).
