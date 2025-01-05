import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

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


class ProjectFileHandler(FileSystemEventHandler):
    # TODO: some kind of debounce would be GREAT, as e.g. pycharm
    #       saves a `my_file.py~` file for a moment whenever you save.
    def __init__(self, project: "Project") -> None:
        self.project = project

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
        if self._should_process(event.src_path):
            logger.info(f"File Modified: {event.src_path}")
            self.project.load_files([Path(self._to_str(event.src_path))])

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        if self._should_process(event.src_path):
            logger.info(f"File Created: {event.src_path}")
            self.project.load_files([Path(self._to_str(event.src_path))])

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent) -> None:
        path = Path(self._to_str(event.src_path))
        if path in self.project.file_map:
            logger.info(f"File Deleted: {event.src_path}")
            del self.project.file_map[path]

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
        max_workers: int | None = None,
    ) -> None:
        self.root = root
        self.max_workers = max_workers
        self.file_map: dict[Path, File] = {}

        git_repo: Repo | None
        if (root / ".git").exists():
            git_repo = Repo(root / ".git")
        else:
            git_repo = None
        self.git_repo = git_repo

        self._init_from_root_dir(root)

        self.observer = Observer()
        self.observer.schedule(ProjectFileHandler(self), str(self.root), recursive=True)
        self.observer.start()

    @property
    def files(self) -> list[File]:
        return list(self.file_map.values())

    def load_files(self, files: list[Path]) -> None:
        files_analysed: list[File] = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
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
