## What and why

<!-- What does this change, and why is it needed? -->

Fixes #

## How it was tested

<!-- Commands run, tests added, and what you checked by hand. Say what you didn't verify. -->

- [ ] `pytest` passes
- [ ] `cd frontend && yarn build` passes (if the frontend changed)
- [ ] Regression test added for a backend bug fix

## Checklist

- [ ] No secrets, real `.env` values or real candidate data in the diff
- [ ] Follows [AGENTS.md](../AGENTS.md) and [SECURITY.md](../SECURITY.md)
- [ ] New modules using `app.database.db` are added to `_patch_db` in `tests/conftest.py`
- [ ] New environment variables are documented in `backend/.env.example`
