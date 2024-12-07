from pathlib import Path

from git import Repo


def get_recent_branches(repo_path: Path, limit: int = 10) -> list[str]:
    """Get the list of up to `limit` recently checked out branches in the given git repo."""
    repo = Repo(repo_path)
    reflog = repo.git.reflog()
    branches = _branches_from_reflog(reflog, limit)
    return branches


def _branches_from_reflog(reflog: str, limit: int) -> list[str]:
    branches = []
    for line in reflog.splitlines():
        if "checkout:" in line:
            branch = line.split("to ")[-1].strip()
            if branch not in branches:
                branches.append(branch)
                if len(branches) >= limit:
                    break
    return branches
