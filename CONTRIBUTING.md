# Contributing to ResumeAI

Thanks for helping. This guide covers how to set up, what a good change looks like, and how it gets reviewed.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems privately as described in [SECURITY.md](SECURITY.md), never in a public issue.

## Before you start

- **Bugs:** search the [issues](https://github.com/Inward17/ResumeAI/issues) first. If it's new, open one with the bug report template: steps to reproduce, what you expected and what happened.
- **Features:** open a feature request first, so we can agree on the approach before you write code.
- **Small fixes** (typos, docs, an obvious one-line bug) can go straight to a pull request.

## Set up

Follow [Run locally](README.md#run-locally) in the README: Python 3.11+, Node 24.12+ with Yarn 1, a MongoDB database and a Firebase project. Copy `backend/.env.example` and `frontend/.env.example` to `.env` files and fill them in. Never commit a `.env` file or a real key.

## Make the change

- **Branch:** create a branch from `main`, one topic per branch.
- **Diff:** keep it small and match the surrounding code. Don't add a dependency for something a few lines can do.
- **Tests:** add a regression test for every backend bug fix, and tests for new backend behaviour.
- **Rules:** follow the conventions and review guidelines in [AGENTS.md](AGENTS.md) and the security rules in [SECURITY.md](SECURITY.md). They are what reviewers check against.

Two rules that are easy to miss:
- Tests patch every module that does a top-level `from app.database import db` automatically (`_patch_db` in `tests/conftest.py` scans `backend/app`). Keep the name `db` when you import it, or the module escapes the patch.
- Use fictional data in tests and examples (`example.com` addresses). Never use real candidate data.

## Check it

```bash
pytest                          # from the repository root; external services are mocked
cd frontend && yarn build       # the frontend has no test suite, so the build is the check
```

CI runs both on every pull request.

## Open the pull request

- Fill in the pull request template: what changed, why, how you tested it, and any linked issue (`Fixes #123`).
- Keep the description factual: say what you verified and what you didn't.
- Codex reviews pull requests. Comment `@codex review` to request one if it hasn't started.
- A maintainer merges once checks pass and review comments are resolved. Merging to `main` deploys the app, so we merge carefully.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
