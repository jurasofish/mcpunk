# ruff: noqa: E501
from mcpunk.git_analysis import _branches_from_reflog


def test_branches_from_reflog() -> None:
    """Test extracting branches from the reflog contents."""
    branches = _branches_from_reflog(example_reflog, limit=10)
    assert branches == [
        "9a7e727a89db0b0e30eb27c569f8f1ba114b7f59",
        "stratch/7",
        "Avoid-new-try_eval_type-unavailable-on-older-pydantic",
        "decorator_typing",
    ]


def test_branches_from_reflog_limit() -> None:
    """Test branch extraction respects the limit."""
    branches = _branches_from_reflog(example_reflog, limit=3)
    assert branches == [
        "9a7e727a89db0b0e30eb27c569f8f1ba114b7f59",
        "stratch/7",
        "Avoid-new-try_eval_type-unavailable-on-older-pydantic",
    ]


example_reflog = """
9a7e727 (HEAD) HEAD@{0}: checkout: moving from stratch/7 to 9a7e727a89db0b0e30eb27c569f8f1ba114b7f59
97d4034 (stratch/7) HEAD@{1}: checkout: moving from Avoid-new-try_eval_type-unavailable-on-older-pydantic to stratch/7
2c89684 (origin/Avoid-new-try_eval_type-unavailable-on-older-pydantic, Avoid-new-try_eval_type-unavailable-on-older-pydantic) HEAD@{2}: rebase (finish): returning to refs/heads/Avoid-new-try_eval_type-unavailable-on-older-pydantic
2c89684 (origin/Avoid-new-try_eval_type-unavailable-on-older-pydantic, Avoid-new-try_eval_type-unavailable-on-older-pydantic) HEAD@{3}: rebase (start): checkout main
477afc1 HEAD@{4}: cherry-pick: run on all push
2c89684 (origin/Avoid-new-try_eval_type-unavailable-on-older-pydantic, Avoid-new-try_eval_type-unavailable-on-older-pydantic) HEAD@{5}: cherry-pick: Avoid new try_eval_type unavailable on older pydantic
2212d39 (tag: v0.4.0, upstream/main, upstream/HEAD, origin/main, origin/HEAD, main) HEAD@{6}: checkout: moving from stratch/7 to Avoid-new-try_eval_type-unavailable-on-older-pydantic
97d4034 (stratch/7) HEAD@{7}: rebase (finish): returning to refs/heads/stratch/7
97d4034 (stratch/7) HEAD@{8}: rebase (pick): run on all push
e7a99cd HEAD@{9}: rebase (pick): Avoid new try_eval_type unavailable on older pydantic
937b86c HEAD@{10}: rebase (start): checkout fca2db224199adedb80a17841d8bca7540fc1412^
8c058e4 HEAD@{11}: rebase (finish): returning to refs/heads/stratch/7
8c058e4 HEAD@{12}: rebase (pick): Avoid new try_eval_type unavailable on older pydantic
fca2db2 HEAD@{13}: rebase (pick): run on all push
937b86c HEAD@{14}: rebase (pick): Improve decorator typing
2d04b9c HEAD@{15}: rebase (pick): Add py.typed
9a7e727 (HEAD) HEAD@{16}: rebase (squash): Basic Makefile
75032a3 HEAD@{17}: rebase (squash): # This is a combination of 2 commits.
84730d4 HEAD@{18}: rebase (start): checkout 84730d47d148a94b9f3043e9905e446d07ba6db9^
6868c03 HEAD@{19}: rebase (finish): returning to refs/heads/stratch/7
6868c03 HEAD@{20}: rebase (pick): Avoid new try_eval_type unavailable on older pydantic
8013d69 HEAD@{21}: rebase (pick): run on all push
31945d4 HEAD@{22}: rebase (pick): Improve decorator typing
dd59f17 HEAD@{23}: rebase (pick): Add py.typed
4083a3f HEAD@{24}: rebase (pick): Update Makefile
0807c3f (stratch/6) HEAD@{25}: rebase (start): checkout 8051fd44d12d785c84a6b9d1f0403d97021a8816^
c504f8c HEAD@{26}: commit: Avoid new try_eval_type unavailable on older pydantic
07152e2 HEAD@{27}: commit: Update Makefile
9483e5a HEAD@{28}: checkout: moving from decorator_typing to stratch/7
165dd1f (origin/decorator_typing, decorator_typing) HEAD@{29}: rebase (finish): returning to refs/heads/decorator_typing
165dd1f (origin/decorator_typing, decorator_typing) HEAD@{30}: rebase (start): checkout main
8a5e13f HEAD@{31}: cherry-pick: run on all push
165dd1f (origin/decorator_typing, decorator_typing) HEAD@{32}: cherry-pick: Improve decorator typing
8264ed4 HEAD@{33}: cherry-pick: Add py.typed
2212d39 (tag: v0.4.0, upstream/main, upstream/HEAD, origin/main, origin/HEAD, main) HEAD@{34}: checkout: moving from stratch/7 to decorator_typing
9483e5a HEAD@{35}: commit: run on all push
aa25ae5 HEAD@{36}: commit: Improve decorator typing
8051fd4 HEAD@{37}: commit: Add py.typed
0807c3f (stratch/6) HEAD@{38}: checkout: moving from stratch/6 to stratch/7
0807c3f (stratch/6) HEAD@{39}: rebase (finish): returning to refs/heads/stratch/6
0807c3f (stratch/6) HEAD@{40}: rebase (pick): sync-fork Makefile
84730d4 HEAD@{41}: rebase (pick): Basic Makefile
"""
