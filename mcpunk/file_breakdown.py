import logging
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from threading import Lock, Timer
from typing import Literal

from git import Repo
from pydantic import (
    BaseModel,
)
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from mcpunk.file_chunk import Chunk, ChunkCategory
from mcpunk.file_chunkers import (
    BaseChunker,
    MarkdownChunker,
    PythonChunker,
    VueChunker,
    WholeFileChunker,
)

ALL_CHUNKERS: list[type[BaseChunker]] = [
    PythonChunker,
    MarkdownChunker,
    VueChunker,
    # Want the WholeFileChunker to be last as it's more of a "fallback" chunker
    WholeFileChunker,
]

logger = logging.getLogger(__name__)


class _ProjectFileHandler(FileSystemEventHandler):
    def __init__(
        self,
        project: "Project",
        file_watch_refresh_freq_seconds: float = 0.1,
    ) -> None:
        self.project = project
        self._project_lock = Lock()

        self._paths_pending_refresh: set[Path] = set()
        self._paths_pending_refresh_lock = Lock()

        self._refresh_freq_sec = file_watch_refresh_freq_seconds
        self._timer: Timer | None = None
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = Timer(self._refresh_freq_sec, self._refresh_paths)
        self._timer.daemon = True
        self._timer.start()

    def _refresh_paths(self) -> None:
        with self._project_lock:
            try:
                with self._paths_pending_refresh_lock:
                    paths_pending_refresh = self._paths_pending_refresh.copy()
                    self._paths_pending_refresh.clear()
                if paths_pending_refresh:
                    logger.info(f"Refreshing {len(paths_pending_refresh)} paths")
                    _paths_fmt = "\n\t".join(str(x) for x in paths_pending_refresh)
                    logger.debug(f"Refreshing\n\t{_paths_fmt}")

                paths_to_delete = {x for x in paths_pending_refresh if not x.exists()}
                for p in paths_to_delete:
                    if p.absolute() in self.project.file_map:
                        del self.project.file_map[p.absolute()]

                dir_paths = {x for x in paths_pending_refresh if x.exists() and x.is_dir()}

                paths_to_really_refresh = paths_pending_refresh - dir_paths - paths_to_delete
                self.project.load_files(list(paths_to_really_refresh))
            except Exception:
                logger.exception("Error refreshing paths")
            finally:
                self._schedule_refresh()

    def _path_event(
        self,
        path: Path,
        *,
        action: Literal["modified", "created", "deleted"],
    ) -> None:
        path = path.absolute()

        logger.debug(f"watchdog says {action}: {path}")
        if self._should_process(path):
            logger.debug(f"New path pending refresh: {path}")
            with self._paths_pending_refresh_lock:
                self._paths_pending_refresh.add(path)
        else:
            logger.debug(f"Ignoring {action} for {path}")

    def _should_process(self, path: Path) -> bool:
        if self.project.git_repo is None:
            return True

        assert path.is_absolute()

        # We don't want to exclude non-existent files, as they may have been deleted.

        if path.exists() and path.is_dir():
            return False

        # Special case this, as we def don't want it and it seems that
        # `git check-ignore` doesn't consider it as ignored.
        if path.is_relative_to(self.project.root / ".git"):
            return False

        try:
            rel_path = str(path.relative_to(self.project.root))
            t1 = time.monotonic()
            check_ignore_res: str = self.project.git_repo.git.execute(  # type: ignore[call-overload]
                ["git", "check-ignore", str(rel_path)],
                with_exceptions=False,
            )
            logger.debug(f"git check-ignore took {(time.monotonic() - t1) * 1000:.4f}ms")
            return check_ignore_res == ""
        except Exception:
            logger.exception(f"Error checking git ignore for {path}")
            return False

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent) -> None:
        self._path_event(
            Path(self._to_str(event.src_path)),
            action="modified",
        )

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        self._path_event(
            Path(self._to_str(event.src_path)),
            action="created",
        )

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent) -> None:
        self._path_event(
            Path(self._to_str(event.src_path)),
            action="deleted",
        )

    @staticmethod
    def _to_str(s: str | bytes) -> str:
        if isinstance(s, bytes):
            return s.decode("utf-8")
        return s


class File(BaseModel):
    chunks: list[Chunk]
    abs_path: Path
    contents: str
    ext: str  # File extension

    @classmethod
    def from_file_contents(
        cls,
        source_code: str,
        file_path: Path,
    ) -> "File":
        """Extract all callables, calls and imports from the given source code file."""
        chunks: list[Chunk] = []

        # Try all eligible chunkers in order until one of them doesn't crash.
        for chunker in ALL_CHUNKERS:
            if chunker.can_chunk(source_code, file_path):
                try:
                    chunks = chunker(source_code, file_path).chunk_file()
                    chunks = _split_large_chunks(chunks)
                    break
                except Exception:
                    logger.exception(f"Error chunking file {file_path} with {chunker}")
        return File(
            chunks=chunks,
            abs_path=file_path.absolute(),
            contents=source_code,
            ext=file_path.suffix,
        )

    def chunks_of_type(self, chunk_type: ChunkCategory) -> list[Chunk]:
        return [c for c in self.chunks if c.category == chunk_type]


class Project:
    def __init__(
        self,
        *,
        root: Path,
        files_per_parallel_worker: int = 100,
        file_watch_refresh_freq_seconds: float = 0.1,
    ) -> None:
        self.root = root.expanduser().absolute()
        self.files_per_parallel_worker = files_per_parallel_worker
        self.file_map: dict[Path, File] = {}

        git_repo: Repo | None
        if (root / ".git").exists():
            git_repo = Repo(root / ".git")
        else:
            git_repo = None
        self.git_repo = git_repo

        self._init_from_root_dir(root)

        # Note potential that if a file is modified here it won't be picked up.

        self.observer = Observer()
        self.observer.schedule(
            event_handler=_ProjectFileHandler(
                self,
                file_watch_refresh_freq_seconds=file_watch_refresh_freq_seconds,
            ),
            path=str(self.root),
            recursive=True,
        )
        self.observer.start()

    @property
    def files(self) -> list[File]:
        return list(self.file_map.values())

    def load_files(self, files: list[Path]) -> None:
        # How many workers to use?
        _cpu_count = os.cpu_count() or 1
        n_workers = math.floor(len(files) / self.files_per_parallel_worker)
        n_workers = min(n_workers, _cpu_count // 2)  # Avoid maxing out the system
        n_workers = max(n_workers, 1)

        files_analysed: list[File]
        if n_workers == 1:
            files_analysed_maybe_none = [_analyze_file(file_path) for file_path in files]
            files_analysed = [x for x in files_analysed_maybe_none if x is not None]
        else:
            logger.info(f"Using {n_workers} workers to process {len(files)} files")
            files_analysed = []
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                future_to_file = {
                    executor.submit(_analyze_file, file_path): file_path for file_path in files
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result is not None:
                            files_analysed.append(result)
                    except Exception:
                        logger.exception(f"File {file_path} generated an exception")

        for file in files_analysed:
            self.file_map[file.abs_path] = file

    def _init_from_root_dir(self, root: Path) -> None:
        if not root.exists():
            raise ValueError(f"Root directory {root} does not exist")

        files: list[Path] = []
        if self.git_repo is not None:
            rel_paths = self.git_repo.git.ls_files().splitlines()
            files.extend(root / rel_path for rel_path in rel_paths)
        else:
            # Exclude specific top-level directories
            # TODO: make this configurable
            ignore_dirs = {".venv", "build", ".git", "__pycache__"}

            for path in root.iterdir():
                if path.is_dir() and path.name not in ignore_dirs:
                    files.extend(path.glob("**/*"))

            # Don't forget files in the root directory itself
            files.extend(root.glob("*"))

        files = [file for file in files if file.is_file()]
        self.load_files(files)


def _analyze_file(file_path: Path) -> File | None:
    try:
        if not file_path.exists():
            logger.warning(f"File {file_path} does not exist")
            return None
        if not file_path.is_file():
            logger.warning(f"File {file_path} is not a file")
            return None

        return File.from_file_contents(file_path.read_text(), file_path)
    except Exception:
        logger.exception(f"Error processing file {file_path}")
        return None


def _split_large_chunks(chunks: list[Chunk], max_size: int = 10000) -> list[Chunk]:
    """Split any chunks larger than max_size into smaller chunks.

    Args:
        chunks: List of chunks to potentially split
        max_size: Maximum size in characters for any chunk

    Returns:
        New list of chunks with large chunks split into smaller ones
    """
    result: list[Chunk] = []
    for chunk in chunks:
        result.extend(_split_large_chunk(chunk, max_size))
    return result


def _split_large_chunk(chunk: Chunk, max_size: int = 10000) -> list[Chunk]:
    """Split a chunk larger than max_size into smaller chunks.

    This will split the chunk at line boundaries, unless the
    line is already longer than max_size.

    Args:
        chunk: The chunk to potentially split
        max_size: Maximum size in characters for the chunk

    Returns:
        List containing either the original chunk (if small enough) or multiple smaller chunks
    """
    # If chunk is small enough, return it as is
    if len(chunk.content) <= max_size:
        return [chunk]

    prefix = "[This is a subsection of the chunk. Other parts contain the rest of the chunk]\n\n"
    max_size -= len(prefix)

    result: list[Chunk] = []
    max_line_size = max_size - 50  # Leave some margin

    # Preprocess to split long lines first. This could be avoided, but it does
    # make the whole thing a bit simpler as we always know later on that a single line
    # will never be longer than max_size.
    processed_lines = []
    for line in chunk.content.splitlines(keepends=True):
        if len(line) > max_line_size:
            # Split the line into chunks of max_line_size
            for i in range(0, len(line), max_line_size):
                processed_lines.append(line[i : i + max_line_size])
        else:
            processed_lines.append(line)

    # Now split into chunks of max_size
    current_content: list[str] = []
    current_size = 0
    part_num = 1

    for line in processed_lines:
        # If adding this line would exceed the limit, create a new chunk
        if current_size + len(line) > max_size and current_content:
            new_chunk = Chunk(
                category=chunk.category,
                name=f"{chunk.name}_part{part_num}",
                content=prefix + "".join(current_content),
                line=None,
            )
            result.append(new_chunk)
            part_num += 1
            current_content = []
            current_size = 0

        # Add the line to the current chunk
        current_content.append(line)
        current_size += len(line)

    # Add the final chunk if there's anything left
    if current_content:
        new_chunk = Chunk(
            category=chunk.category,
            name=f"{chunk.name}_part{part_num}",
            content=prefix + "".join(current_content),
            line=None,
        )
        result.append(new_chunk)

    return result
