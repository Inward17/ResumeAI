# MCP server

ResumeAI exposes a [Model Context Protocol](https://modelcontextprotocol.io) server so AI assistants (Claude, Cursor, ChatGPT and other MCP clients) can work with a workspace: list jobs, look at candidates and their evidence, and move candidates through the pipeline.

- Endpoint: `<API URL>/mcp`, for example `https://<your-space>.hf.space/mcp` or `http://localhost:8000/mcp`.
- Transport: Streamable HTTP, stateless, JSON responses (no server-sent event streams, no sessions).
- Code: `backend/app/mcp_server.py` (official `mcp` Python SDK, FastMCP), mounted in `backend/app/main.py`. Its session manager runs inside the app lifespan.

## Authentication

Send a workspace API key, created under **Settings > API keys** by an owner or admin:

```
Authorization: Bearer rai_...
```

- Only workspace API keys are accepted. Firebase/Google ID tokens and anonymous requests get `401` before any MCP handling. A revoked key, or a key whose creator left the workspace, gets `401`.
- A key acts inside its own workspace with Recruiter (`member`) rights, whatever its creator's role (see [SECURITY.md](../SECURITY.md)). The tools go through the same checks as the REST API (`visible_job`, `job_filter`, `require_action`), so they never see another workspace's jobs or candidates.
- Each key gets the per-minute rate limit (`RATE_LIMIT_PER_MINUTE`, default 30 requests, per process). Over it: `429`.
- `AUTH_DISABLED=true` (local development only) behaves as in the REST API.

## Tools

| Tool | What it does | Needs |
|---|---|---|
| `list_jobs` | Visible jobs, newest first, with candidate counts; optional `status` (Active, Draft, Closed) | view |
| `get_job` | One job: description (cut at 4,000 characters), required and preferred skills, counts | view |
| `list_candidates` | A job's candidates with status, role match and credibility; filter by `status`, `min_role_match` (0-100), `search` (name, email or skill); `limit` (max 100) and `offset` | view |
| `search_candidates` | Same search across every visible job; one result per application | view |
| `get_candidate` | One candidate on one job: scores, per-skill matches, verification results and discrepancies, cover letter analysis, project reviews, coding and portfolio profiles, interview questions if already generated | view |
| `pipeline_summary` | Candidates per status for one job or all visible jobs | view |
| `update_candidate_status` | Set a status: Under Review, Shortlisted, Interview, Offer, Hired or Rejected. Same update as `PUT /api/v1/jobs/{job_id}/candidates/{candidate_id}/status` | `candidate.status` |

"view" is what every role has on the jobs it can see. Read tools are annotated `readOnlyHint`; `update_candidate_status` is `destructiveHint: false, idempotentHint: true`.

There are deliberately no tools that delete, upload, or spend AI quota (parsing, verification, project reviews, interview question generation, fact checks). Notes are not offered because the app has no notes feature yet.

Scores are 0-100. `null` means "not available" (not checked yet, or no source could be checked), never 0.

## Connecting a client

Claude Code:

```bash
claude mcp add --transport http resumeai https://<api-url>/mcp --header "Authorization: Bearer rai_..."
```

Clients with a JSON config (Cursor and others; key names vary a little per client):

```json
{
  "mcpServers": {
    "resumeai": {
      "type": "http",
      "url": "https://<api-url>/mcp",
      "headers": { "Authorization": "Bearer rai_..." }
    }
  }
}
```

Raw request:

```bash
curl https://<api-url>/mcp \
  -H "Authorization: Bearer rai_..." \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_jobs","arguments":{}}}'
```

## Security notes

- Candidate data is untrusted: resumes, cover letters and fetched profiles can contain prompt injection. Every field that came from the candidate is under a `candidate_provided` key, and the server instructions tell the model it is data, not instructions, and that status changes need the user's confirmation.
- Tool output is compact JSON with what the tools need: no team member ids or emails, no API keys, no raw resume text (experience and education entries are cut).
- The SDK's DNS-rebinding Host check is off, because it only allows localhost. The required key header is the protection: browsers can't send it cross-site without passing CORS, and `CORS_ORIGINS` lists exact origins.
- The rate limit is in memory per process, like the rest of the API.
