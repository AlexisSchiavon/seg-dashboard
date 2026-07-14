"""Structural regression guard for the EXTERNAL-SERVICE WRITE SURFACE.

Why this test exists
--------------------
The SEG Dashboard is read-only for every external service with exactly ONE
authorized exception: `trello.create_card` (auto-create of won-deal cards,
CREATE-only, gated by a list whitelist + TRELLO_AUTO_CREATE_ENABLED). See
CLAUDE.md "RESTRICCIONES CRÍTICAS".

This test parses the AST of every module in `app/integrations/` and fails if
ANY external-write call appears that is not in the single-element allowlist
below. It is a tripwire: if in three months someone (us included) adds a
`.post()` to Pipedrive, or an `update()/append_row()` to Google Sheets, the
suite goes RED here — long before it reaches production.

It scans `app/integrations/` specifically because that is the only layer that
talks to external HTTP/gspread APIs. Router files (`app/routers/`) use
`@router.post(...)` decorators that describe OUR OWN backend endpoints, not
outbound writes — they are intentionally out of scope.
"""
import ast
from pathlib import Path

# HTTP client write verbs + gspread worksheet write methods. Bare `append`
# (list) and `format` (str) are deliberately excluded to avoid false positives;
# gspread's real write API uses `append_row`/`append_rows`, etc.
#
# CAVEAT (intentional, conservative): `update` also matches a plain `dict.update`.
# app/integrations/ has ZERO dict.update today (these are thin API wrappers), so
# this is currently false-positive-free. If a legitimate dict.update is ever
# added here it will trip this guard on purpose — review it, and if truly benign,
# refactor or add it to ALLOWED_WRITES with a comment. Erring toward a RED build
# is the whole point: a missed Sheets `ws.update()` write is the failure we fear.
WRITE_METHODS = frozenset({
    # httpx / requests
    "post", "put", "patch", "delete",
    # gspread worksheet / spreadsheet writes
    "update", "update_cell", "update_cells", "update_acell",
    "append_row", "append_rows", "insert_row", "insert_rows",
    "delete_row", "delete_rows", "batch_update", "add_worksheet",
    "del_worksheet",
})

# The ONLY authorized external write in the entire system, as (filename, method).
ALLOWED_WRITES = frozenset({("trello.py", "post")})

INTEGRATIONS_DIR = Path(__file__).resolve().parent.parent / "app" / "integrations"


def _find_write_calls(path: Path) -> list[tuple[str, str, int]]:
    """Return (filename, method, lineno) for every attribute-method call whose
    method name is a known external-write verb."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in WRITE_METHODS:
                found.append((path.name, method, node.lineno))
    return found


def test_only_authorized_external_write_is_trello_create_card():
    assert INTEGRATIONS_DIR.is_dir(), f"missing {INTEGRATIONS_DIR}"

    violations: list[tuple[str, str, int]] = []
    for py_file in sorted(INTEGRATIONS_DIR.glob("*.py")):
        for filename, method, lineno in _find_write_calls(py_file):
            if (filename, method) not in ALLOWED_WRITES:
                violations.append((filename, method, lineno))

    assert not violations, (
        "Unauthorized external-service WRITE call(s) detected in app/integrations/. "
        "The only authorized external write is trello.create_card (POST /cards). "
        "Pipedrive and Google Sheets are read-only ALWAYS. If this is a legitimate, "
        "explicitly-approved new write, update ALLOWED_WRITES and CLAUDE.md together.\n"
        f"Violations (file, method, line): {violations}"
    )


def test_the_authorized_write_still_exists():
    """Sanity: the one allowed write must actually be present, so this guard
    can't silently pass because the write path was renamed/removed."""
    trello_py = INTEGRATIONS_DIR / "trello.py"
    calls = _find_write_calls(trello_py)
    assert ("trello.py", "post", ) in {(f, m) for f, m, _ in calls} or any(
        m == "post" for _, m, _ in calls
    ), "Expected trello.create_card's POST /cards to be present in trello.py"
