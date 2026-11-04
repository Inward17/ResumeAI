# Security

## Reporting a vulnerability

Don't open a public issue. Use **Report a vulnerability** on this repository's Security tab if it's available; otherwise contact the repository owner privately through GitHub. Include the steps to reproduce and the impact.

## What this app protects

ResumeAI stores resumes and candidate personal data (names, emails, phone numbers, employment and education history), plus interview evaluations. It holds API keys for paid services. Treat all of it as sensitive.

## Security review guidelines

Flag any change that breaks these rules. Severity guidance is in [AGENTS.md](AGENTS.md#review-guidelines).

### Authentication

- Every API route requires `get_current_user`, applied to the routers in `backend/app/main.py`. A new router must be included the same way.
- ID tokens must keep being verified for signature, issuer, audience and expiry (`backend/app/auth.py`).
- `AUTH_DISABLED` is for local development only. `VITE_AUTH_DISABLED` must stay gated on `import.meta.env.DEV`, so production bundles never contain the bypass.

### Workspace isolation

- Data belongs to a workspace. Job queries must filter on `org_id` from `ensure_org(user)`.
- Routes under a job use `require_job_owner`, and routes taking a candidate id use `require_candidate_access`. Flag any route that accepts a job or candidate id without one of these checks.
- Return 404, not 403, for another workspace's resource, so ids aren't revealed.
- A workspace API key acts only inside its own workspace.

### Roles and invitations

- Changing the workspace, members, invites or API keys requires an owner or admin (`require_manager`). The one exception: members may remove themselves.
- The workspace owner can't be removed or demoted.
- Invites must stay random, expiring, single-use and bound to the invited email address: accepting needs a signed-in account with that address.

### Secrets

- Never commit `.env` files, keys or real connection strings. `.env.example` holds placeholders only.
- Anything with a `VITE_` prefix ends up in the browser bundle, so it must never hold a secret. Firebase web config is the exception: it's public by design.
- Workspace API keys are stored only as hashes and shown once, at creation.
- Keys must not appear in logs, error messages, API responses or URLs. Send them in headers where the provider allows it.
- Deploy secrets stay in GitHub Actions and Hugging Face settings. Workflows must not print them, or expose them to pull requests from forks.

### Untrusted input

Resumes, and everything fetched about a candidate (GitHub repositories, READMEs, LinkedIn data, web results), are controlled by the candidate.

- **Prompt injection:** a resume or README may try to instruct the model. Keep this text clearly separated from instructions in prompts, and treat model output as untrusted: validate its structure before storing it, and never execute it or use it to choose a privileged action.
- **Uploads:** keep the extension allow-list and the size limit, enforced on the server. Stored names must stay `uuid_basename`, so a filename can't traverse paths. Never serve an upload as active content.
- **Cloned or fetched code:** GitHub analysis must never execute candidate code or install its dependencies.
- **Outbound requests:** URLs and usernames from resumes must not let a caller reach internal addresses or arbitrary hosts (SSRF). Validate the host before fetching, and use timeouts.
- **Database queries:** never pass request JSON directly into a MongoDB filter, because it can inject operators. Use typed models and cast ids.
- **Rendering:** candidate and model text must render as plain text. Flag `dangerouslySetInnerHTML`, and `href` values built from candidate data that could be `javascript:` links.

### Personal data

- Don't log resume contents or contact details. Log candidate ids instead.
- Deleting a job must also remove its applications and evaluations.
- Candidate data sent to a new third-party service, or stored in new browser storage, needs a stated reason in the pull request.
- Test data and fixtures must be fictional (`example.com` addresses).

### Browser and transport

- `CORS_ORIGINS` must list exact origins. Never use `*`, because credentials are allowed.
- Error responses must not leak stack traces, connection strings or provider responses.

### Dependencies and CI

- A new dependency needs a stated reason. Pin versions of security-sensitive ones, and check that the package name is the intended one.
- Workflows keep least-privilege `permissions`. Flag untrusted pull request input used directly in a `run:` step.
