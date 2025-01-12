import logging
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from threading import Timer

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
    def __init__(self, project: "Project") -> None:
        self.project = project
        self._timers: dict[Path, Timer] = {}
        self._debounce_delay = 100

    def _handle_event(self, path: Path, event_type: str) -> None:
        """Process the file event after the debounce delay."""
        if path in self._timers:
            del self._timers[path]

        if event_type in ("modified", "created"):
            if self._should_process(str(path)):
                logger.info(f"Processing debounced {event_type}: {path}")
                self.project.load_files([path])
        elif event_type == "deleted":
            if path in self.project.file_map:
                logger.info(f"Processing debounced deletion: {path}")
                del self.project.file_map[path]
        else:
            raise ValueError(f"bad value {event_type}")

    def _schedule_debounce(self, path: Path, event_type: str) -> None:
        """Schedule a debounced file event processing."""
        if path in self._timers:
            self._timers[path].cancel()
        timer = Timer(self._debounce_delay, self._handle_event, args=[path, event_type])
        self._timers[path] = timer
        timer.start()

    def _should_process(self, path: str | bytes) -> bool:
        if self.project.git_repo is None:
            return True

        pl_path = Path(self._to_str(path))
        if not pl_path.exists():
            return False
        if not pl_path.is_file():
            return False

        try:
            rel_path = str(pl_path.relative_to(self.project.root))
            check_ignore_res: str = self.project.git_repo.git.execute(  # type: ignore[call-overload]
                ["git", "check-ignore", str(rel_path)],
                with_exceptions=False,
            )
            return check_ignore_res == ""
        except Exception:
            logger.exception(f"Error checking git ignore for {self._to_str(path)}")
            return False

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent) -> None:
        path = Path(self._to_str(event.src_path))
        if path.is_file():  # Only process files, not directories
            logger.debug(f"File Modified (debouncing): {path}")
            self._schedule_debounce(path, "modified")

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        path = Path(self._to_str(event.src_path))
        if path.is_file():  # Only process files, not directories
            logger.debug(f"File Created (debouncing): {path}")
            self._schedule_debounce(path, "created")

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent) -> None:
        path = Path(self._to_str(event.src_path))
        if path in self._timers:
            self._timers[path].cancel()
            del self._timers[path]
        self._schedule_debounce(path, "deleted")

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
    ) -> None:
        self.root = root
        self.files_per_parallel_worker = files_per_parallel_worker
        self.file_map: dict[Path, File] = {}

        git_repo: Repo | None
        if (root / ".git").exists():
            git_repo = Repo(root / ".git")
        else:
            git_repo = None
        self.git_repo = git_repo

        self._init_from_root_dir(root)

        self.observer = Observer()
        self.observer.schedule(
            event_handler=_ProjectFileHandler(self),
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
            ignore_dirs = {".venv", "build", ".git", "__pycache__"}  # customize this set

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
