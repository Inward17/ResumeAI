"""
Issue #17: the Codex request workflow only goes green for a completed review of the exact head.
Runs the workflow's inline script against a fake GitHub API.
"""
import io
import json
import textwrap
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "codex-review.yml"
SHA = "a" * 40
OLD_SHA = "b" * 40
CODEX = "chatgpt-codex-connector[bot]"
ACTIONS = "github-actions[bot]"


def _script():
    text = WORKFLOW.read_text(encoding="utf-8")
    return textwrap.dedent(text.split("run: |\n", 1)[1])


def _review_state(sha, status="completed"):
    state = {"code_review": {"commit_sha": sha, "status": status}}
    return f"<!-- codex-pull-request-review-summary -->\n<!-- codex-review-state:v1 {json.dumps(state)} -->\n"


class FakeGitHub:
    def __init__(self, on_request=None, author_permission="write"):
        self.comments, self.reviews = [], []
        self.pr = {"state": "open", "draft": False, "head": {"sha": SHA}, "user": {"login": "someone"}}
        self.on_request = on_request
        self.author_permission = author_permission
        self.fail_next = False
        self.next_id = 100

    def comment(self, login, body):
        self.next_id += 1
        item = {"id": self.next_id, "user": {"login": login}, "body": body,
                "html_url": f"https://github.test/pull/1#issuecomment-{self.next_id}"}
        self.comments.append(item)
        return item

    @property
    def requests(self):
        return [c for c in self.comments if c["body"] == "@codex review"]

    def urlopen(self, req, timeout=None):
        path = req.full_url.split("/repos/o/r", 1)[1]
        if self.fail_next:
            self.fail_next = False
            raise urllib.error.URLError("temporary")
        if req.data is not None:
            created = self.comment(ACTIONS, json.loads(req.data)["body"])
            if created["body"] == "@codex review" and self.on_request:
                self.on_request(self)
            return io.BytesIO(json.dumps(created).encode())
        if "/collaborators/" in path:
            payload = {"permission": self.author_permission}
        elif "/reviews" in path:
            payload = self.reviews
        elif "/comments" in path:
            payload = self.comments
        else:
            payload = self.pr
        return io.BytesIO(json.dumps(payload).encode())


def _run(gh, tmp_path, env=None, while_waiting=None):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 1, "head": {"sha": gh.pr["head"]["sha"]}}}))
    summary = tmp_path / "summary.md"
    clock = {"now": 0.0}

    def sleep(seconds):
        clock["now"] += seconds
        if while_waiting:
            while_waiting(gh)

    variables = {"GH_REPO": "o/r", "GH_TOKEN": "x", "GITHUB_EVENT_PATH": str(event),
                 "GITHUB_STEP_SUMMARY": str(summary), **(env or {})}
    with patch.dict("os.environ", variables), patch("urllib.request.urlopen", gh.urlopen), \
         patch("time.sleep", sleep), patch("time.monotonic", lambda: clock["now"]):
        with pytest.raises(SystemExit) as exit_info:
            exec(compile(_script(), "codex-review", "exec"), {"__name__": "__main__"})
    return exit_info.value.code or 0, summary.read_text() if summary.exists() else ""


def _codex_completes(gh):
    gh.comment(CODEX, _review_state(SHA))


def _codex_rejects(gh):
    gh.comment(CODEX, "To use Codex here, [create a Codex account and connect to github](https://x).")


def test_completed_review_of_this_head_passes(tmp_path):
    gh = FakeGitHub(on_request=_codex_completes)
    code, summary = _run(gh, tmp_path)
    assert code == 0
    assert "completed a review" in summary and "not an approval" in summary


def test_formal_review_on_this_head_passes(tmp_path):
    gh = FakeGitHub(on_request=lambda g: g.reviews.append(
        {"user": {"login": CODEX}, "commit_id": SHA, "state": "COMMENTED"}))
    assert _run(gh, tmp_path)[0] == 0


def test_authentication_rejection_fails(tmp_path):
    code, summary = _run(FakeGitHub(on_request=_codex_rejects), tmp_path)
    assert code == 1
    assert "rejected" in summary and "unreviewed" in summary


def test_no_response_times_out_as_failure(tmp_path):
    code, summary = _run(FakeGitHub(), tmp_path)
    assert code == 1
    assert "No completed Codex review" in summary


def test_late_review_is_picked_up(tmp_path):
    assert _run(FakeGitHub(), tmp_path, while_waiting=_codex_completes)[0] == 0


def test_review_of_an_older_commit_does_not_count(tmp_path):
    gh = FakeGitHub()
    gh.comment(CODEX, _review_state(OLD_SHA))
    assert _run(gh, tmp_path)[0] == 1


def test_unfinished_review_does_not_count(tmp_path):
    gh = FakeGitHub()
    gh.comment(CODEX, _review_state(SHA, status="in_progress"))
    assert _run(gh, tmp_path)[0] == 1


def test_lookalike_from_another_account_does_not_count(tmp_path):
    gh = FakeGitHub()
    gh.comment("mallory", _review_state(SHA))
    gh.reviews.append({"user": {"login": "mallory"}, "commit_id": SHA})
    assert _run(gh, tmp_path)[0] == 1


def test_rejection_of_an_earlier_request_is_ignored(tmp_path):
    gh = FakeGitHub(on_request=_codex_completes)
    _codex_rejects(gh)
    assert _run(gh, tmp_path)[0] == 0


def test_rerun_does_not_request_twice_and_keeps_watching(tmp_path):
    gh = FakeGitHub(on_request=_codex_rejects)
    assert _run(gh, tmp_path)[0] == 1
    assert _run(gh, tmp_path)[0] == 1
    assert len(gh.requests) == 1


def test_native_mode_only_watches(tmp_path):
    gh = FakeGitHub()
    gh.comment(CODEX, _review_state(SHA))
    assert _run(gh, tmp_path, env={"CODEX_NATIVE_REVIEW": "true"})[0] == 0
    assert gh.requests == []


def test_newer_commit_ends_the_old_run_quietly(tmp_path):
    def push(gh):
        gh.pr["head"]["sha"] = OLD_SHA

    assert _run(FakeGitHub(), tmp_path, while_waiting=push)[0] == 0


def test_github_api_blip_keeps_waiting(tmp_path):
    gh = FakeGitHub()

    def blip_then_complete(g):
        if not g.fail_next and not any(c["user"]["login"] == CODEX for c in g.comments):
            g.fail_next = True
            _codex_completes(g)

    assert _run(gh, tmp_path, while_waiting=blip_then_complete)[0] == 0


def test_external_contributor_is_not_requested(tmp_path):
    gh = FakeGitHub(author_permission="read")
    assert _run(gh, tmp_path)[0] == 0
    assert gh.requests == []


def test_workflow_has_no_checkout_or_extra_permissions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout" not in text
    assert "permissions:\n  contents: read\n  pull-requests: write\n\n" in text
