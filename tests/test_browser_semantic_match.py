"""Unit tests for orbit.browser.session's pure semantic-matching helpers.

No real browser needed. These pin down the bug class that surfaced when
clicking "the 'Process' button" on the demo portal: a table row's
concatenated text can contain the target word too (its "processed" status
cell), and a plain substring match let the row outscore the actual button —
clicking the row instead of submitting the form. Matching must stay
role-aware and word-based, never raw-substring, to avoid that.
"""

from types import SimpleNamespace

from orbit.browser.session import (
    _clean_target,
    _describe_elements,
    _is_actionable,
    _match_score,
)


def _node(tag, text, role=None, name=None):
    ax_node = SimpleNamespace(role=role, name=name) if (role or name) else None
    return SimpleNamespace(
        tag_name=tag,
        ax_node=ax_node,
        get_meaningful_text_for_llm=lambda: text,
    )


def test_clean_target_extracts_quoted_text():
    assert _clean_target("the 'Process' button") == "process"
    assert _clean_target('click the "Search" field') == "search"


def test_clean_target_strips_role_and_stop_words():
    assert _clean_target("Search customer field") == "search customer"


def test_match_score_prefers_button_over_row_with_overlapping_text():
    row = _node("tr", "1\nJohn Smith\nWidget A\n2\nprocessed")
    button = _node("button", "Process order", role="button", name="Process order")
    cleaned = _clean_target("the 'Process' button")
    assert _match_score(cleaned, button) > _match_score(cleaned, row)


def test_is_actionable_excludes_rows_and_cells():
    row = _node("tr", "row text", role="row")
    cell = _node("td", "cell text", role="cell")
    button = _node("button", "Process order", role="button", name="Process order")
    assert not _is_actionable(row)
    assert not _is_actionable(cell)
    assert _is_actionable(button)


def test_describe_elements_only_lists_actionable_roles():
    selector_map = {
        1: _node("tr", "row text", role="row"),
        2: _node("button", "Process order", role="button", name="Process order"),
    }
    assert _describe_elements(selector_map) == ["[2] button: 'Process order'"]


def test_match_score_exact_match_is_perfect():
    node = _node("button", "Search", role="button", name="Search")
    assert _match_score("search", node) == 1.0
