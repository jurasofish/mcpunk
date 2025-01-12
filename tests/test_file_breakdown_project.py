import logging
import sys
import time
from pathlib import Path

import pytest
from git import Repo

from mcpunk.file_breakdown import Project as FileBreakdownProject
from mcpunk.file_chunk import ChunkCategory
from tests.conftest import FileSet


def test_project_initialization(basic_file_set: FileSet) -> None:
    project = FileBreakdownProject(root=basic_file_set.root)
    assert project.root == basic_file_set.root
    assert len(project.files) == 2
    assert set(project.file_map.keys()) == {
        basic_file_set.root / "a.py",
        basic_file_set.root / "b.py",
    }


def test_project_file_loading(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "import foo")

    project = FileBreakdownProject(root=fs.root)
    assert len(project.files) == 1
    loaded_file = project.file_map[fs.root / "test.py"]
    assert loaded_file.contents == "import foo"
    assert loaded_file.ext == ".py"
    assert [c.category for c in loaded_file.chunks] == [ChunkCategory.imports]


def test_project_mixed_files_and_locations(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    # Top level files
    fs.add_file("script.py", "import blah")
    fs.add_file("readme.md", "# Title\n## Section")
    fs.add_file("config.xyz", "some: config")

    # Deep nested files
    fs.add_file("src/lib/utils.py", "x = 1")
    fs.add_file("docs/api/spec.md", "# API\n## Endpoints")
    fs.add_file("config/env/dev.xyz", "env: dev")

    project = FileBreakdownProject(root=fs.root)
    assert len(project.files) == 6

    # Check Python files were chunked correctly
    script_file = project.file_map[fs.root / "script.py"]
    utils_file = project.file_map[fs.root / "src/lib/utils.py"]
    assert [c.category for c in script_file.chunks] == [ChunkCategory.imports]
    assert [c.category for c in utils_file.chunks] == [ChunkCategory.module_level]

    # Check Markdown files were chunked correctly
    readme_file = project.file_map[fs.root / "readme.md"]
    spec_file = project.file_map[fs.root / "docs/api/spec.md"]
    assert all(c.category == ChunkCategory.markdown_section for c in readme_file.chunks)
    assert all(c.category == ChunkCategory.markdown_section for c in spec_file.chunks)

    # Check unknown extensions used whole file chunker
    config_file = project.file_map[fs.root / "config.xyz"]
    env_file = project.file_map[fs.root / "config/env/dev.xyz"]
    assert all(c.category == ChunkCategory.whole_file for c in config_file.chunks)
    assert all(c.category == ChunkCategory.whole_file for c in env_file.chunks)


def test_project_git_detection_without_git(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "x = 1")

    project = FileBreakdownProject(root=fs.root)
    assert project.git_repo is None


def test_project_git_detection_with_git(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "x = 1")
    # Initialize actual git repo
    Repo.init(fs.root)

    project = FileBreakdownProject(root=fs.root)
    assert project.git_repo is not None


def test_project_non_existent_root(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="does not exist"):
        FileBreakdownProject(root=non_existent)


@pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="Dumb test relies on chmod")
def test_project_handles_unreadable_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("good.py", "x = 1")
    bad_file = fs.root / "bad.py"
    bad_file.touch()
    bad_file.chmod(0o000)  # Make unreadable

    project = FileBreakdownProject(root=fs.root)
    assert len(project.files) == 1  # Should have just the good file
    assert (fs.root / "good.py") in project.file_map

    # Good file should be chunked normally
    good_file = project.file_map[fs.root / "good.py"]
    assert [c.category for c in good_file.chunks] == [ChunkCategory.module_level]


def test_project_handles_bad_syntax_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("good.py", "x = 1")
    fs.add_file("bad_syntax.py", "x = ")

    project = FileBreakdownProject(root=fs.root)
    assert len(project.files) == 2
    assert (fs.root / "good.py") in project.file_map
    assert (fs.root / "bad_syntax.py") in project.file_map

    # Bad syntax should fallback to whole file chunker
    bad_syntax_file = project.file_map[fs.root / "bad_syntax.py"]
    assert [c.category for c in bad_syntax_file.chunks] == [ChunkCategory.whole_file]

    # Good file should be chunked normally
    good_file = project.file_map[fs.root / "good.py"]
    assert [c.category for c in good_file.chunks] == [ChunkCategory.module_level]


def test_project_parallel_processing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A bit of a chunky one as it results in multiprocessing.

    # e.g. in CI we only have two cores. For reliable testing, patch this.
    monkeypatch.setattr("os.cpu_count", lambda: 8)

    fs = FileSet(tmp_path)

    # First add 10 files - should use single worker
    for i in range(10):
        fs.add_file(f"file_{i}.py", f"x_{i} = {i}")
    caplog.set_level(logging.DEBUG)
    project = FileBreakdownProject(root=fs.root, files_per_parallel_worker=10)
    assert len(project.files) == 10
    assert "workers" not in caplog.text.lower()

    # Add 20 more files - should now use multiple workers
    for i in range(10, 30):
        fs.add_file(f"file_{i}.py", f"x_{i} = {i}")
    project = FileBreakdownProject(root=fs.root, files_per_parallel_worker=10)
    assert len(project.files) == 30
    assert "Using 3 workers to process 30 files" in caplog.text


def test_project_watch_new_file(tmp_path: Path) -> None:
    # Init project
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "def test(): pass")
    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)

    # Add new file and wait for refresh
    fs.add_file("new.py", "import new")
    for _ in range(2_000):
        if (fs.root / "new.py") in project.file_map:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated")

    assert (fs.root / "new.py") in project.file_map
    new_file = project.file_map[fs.root / "new.py"]
    assert new_file.contents == "import new"
    assert [c.category for c in new_file.chunks] == [ChunkCategory.imports]


def test_project_watch_modify_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "def test(): pass")
    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)

    # Modify file and wait for refresh
    (fs.root / "test.py").write_text("import modified")
    for _ in range(2_000):
        if project.file_map[fs.root / "test.py"].contents == "import modified":
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated")

    modified_file = project.file_map[fs.root / "test.py"]
    assert modified_file.contents == "import modified"
    assert [c.category for c in modified_file.chunks] == [ChunkCategory.imports]


def test_project_watch_delete_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "def test(): pass")
    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)
    assert len(project.file_map) == 1

    # Delete file and wait for refresh
    (fs.root / "test.py").unlink()
    for _ in range(2_000):
        if (fs.root / "test.py") not in project.file_map:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated")

    assert (fs.root / "test.py") not in project.file_map


def test_project_watch_delete_and_recreate_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("test.py", "def test(): pass")
    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)
    assert len(project.file_map) == 1

    # Delete file and wait for refresh
    (fs.root / "test.py").unlink()
    for _ in range(2_000):
        if (fs.root / "test.py") not in project.file_map:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated after delete")
    assert len(project.file_map) == 0

    # Recreate file and wait for refresh
    fs.add_file("test.py", "import recreated")
    for _ in range(2_000):
        if (fs.root / "test.py") in project.file_map:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated after recreation")

    modified_file = project.file_map[fs.root / "test.py"]
    assert modified_file.contents == "import recreated"
    assert [c.category for c in modified_file.chunks] == [ChunkCategory.imports]


def test_project_watch_modify_deep_file(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("deep/nested/dir/test.py", "def test(): pass")
    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)
    assert len(project.file_map) == 1

    # Modify deep file and wait for refresh
    (fs.root / "deep/nested/dir/test.py").write_text("import modified")
    for _ in range(2_000):
        if project.file_map[fs.root / "deep/nested/dir/test.py"].contents == "import modified":
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File not updated")

    modified_file = project.file_map[fs.root / "deep/nested/dir/test.py"]
    assert modified_file.contents == "import modified"
    assert [c.category for c in modified_file.chunks] == [ChunkCategory.imports]


def test_project_instantiation_git_ignored_files(tmp_path: Path) -> None:
    fs = FileSet(tmp_path)

    # Setup git repo
    repo = Repo.init(fs.root)

    # Create files
    fs.add_file("tracked.py", "x = 1")
    fs.add_file("ignored.py", "y = 2")

    # Add gitignore
    (fs.root / ".gitignore").write_text("ignored.py\n")

    # Add tracked file to git
    repo.index.add(["tracked.py"])
    repo.index.commit("Add tracked file")

    project = FileBreakdownProject(root=fs.root)
    assert len(project.files) == 1
    assert (fs.root / "tracked.py") in project.file_map
    assert (fs.root / "ignored.py") not in project.file_map


def test_project_git_ignored_file_watch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test is a bit racy and gross, has a retry loop.

    It's generally tricky to confirm that something doesn't happen, especially when
    that thing has a nondeterministic delay to it. Oh well. Better imo than digging
    deep into tests of implementation details.
    """
    fs = FileSet(tmp_path)
    repo = Repo.init(fs.root)
    (fs.root / ".gitignore").write_text("ignored.py\n")

    # Add tracked file to git
    fs.add_file("tracked.py", "x = 1")
    repo.index.add(["tracked.py"])
    repo.index.commit("Add tracked file")

    # Add ignored file
    fs.add_file("ignored.py", "y = 2")

    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)
    assert len(project.files) == 1

    # Modify ignored file
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    (fs.root / "ignored.py").write_text("y = 3")

    # Wait for ignore message in logs
    for _ in range(2_000):
        if f"Ignoring modified for {fs.root / 'ignored.py'}" in caplog.text:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File was not ignored")


def test_project_modify_file_in_dot_git_dir(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Files in .git should be ignored."""
    fs = FileSet(tmp_path)

    # Setup git repo and add file
    _repo = Repo.init(fs.root)
    git_file = fs.root / ".git" / "test.py"
    git_file.parent.mkdir(exist_ok=True)
    git_file.write_text("x = 1")

    project = FileBreakdownProject(root=fs.root, file_watch_refresh_freq_seconds=0.0)
    assert len(project.files) == 0  # No tracked files

    # Modify file in .git
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    git_file.write_text("x = 2")

    # Wait for ignore message in logs
    for _ in range(2_000):
        if f"Ignoring modified for {git_file}" in caplog.text:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError("File in .git was not ignored")


def test_project_load_non_existent_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fs = FileSet(tmp_path)
    fs.add_file("exists.py", "x = 1")

    project = FileBreakdownProject(root=fs.root)

    caplog.clear()
    caplog.set_level(logging.WARNING)
    non_existent = fs.root / "does_not_exist.py"
    project.load_files([fs.root / "does_not_exist.py"])

    # Wait for warning message
    for _ in range(2_000):
        if f"File {non_existent} does not exist" in caplog.text:
            break
        time.sleep(1e-3)
    else:
        raise AssertionError(f"No log message about non-existent file. Caplog is {caplog.text}")

    assert len(project.files) == 1
    assert fs.root / "exists.py" in project.file_map
    assert fs.root / "does_not_exist.py" not in project.file_map
