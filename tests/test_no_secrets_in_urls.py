"""
Issue #27: API keys and tokens go in headers, never in a URL query string
(SECURITY.md). URLs end up in access logs, proxy caches and error messages.
"""
import re
from pathlib import Path

APP = Path(__file__).parent.parent / "backend" / "app"
SECRET_PARAM = re.compile(
    r"""params\s*=\s*\{[^}]*["'](key|api_key|apikey|token|access_token|secret)["']\s*:"""
    r"""|[?&](key|api_key|apikey|token|access_token)=""",
    re.I,
)


def test_no_secret_in_query_parameters():
    offenders = [
        f"{path.relative_to(APP)}:{n}"
        for path in APP.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if SECRET_PARAM.search(line)
    ]
    assert offenders == []
