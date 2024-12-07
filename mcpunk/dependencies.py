# ruff: noqa: E402
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

__all__ = [
    "Dependencies",
    "deps",
]


class Singleton(type):
    _instances: dict[Any, Any] = {}  # noqa: RUF012

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Dependencies(metaclass=Singleton):
    """Dependencies that can play nice with testing.

    If you want to get settings, db session, etc. do it here. This means that in
    tests we can patch/etc JUST this object and have everything play nice.
    """

    def __init__(self) -> None:
        self._settings: Settings | None = None
        self._engine: Engine | None = None
        self._session_maker: sessionmaker[Session] | None = None

    def _clear(self) -> None:
        self._settings = None
        self._engine = None
        self._session_maker = None

    def settings(self) -> "Settings":
        if self._settings is None:
            self._settings = Settings()
        return self._settings

    def db_engine(self) -> "Engine":
        if self._engine is None:
            settings = self.settings()
            self._engine = create_engine(
                f"sqlite:///{settings.db_path}?check_same_thread=true&timeout=10&uri=true",
                echo=settings.db_echo,
            )
        return self._engine

    def session_maker(self) -> sessionmaker[Session]:
        if self._session_maker is None:
            self._session_maker = sessionmaker(
                autocommit=False,
                expire_on_commit=True,
                autoflush=False,
                bind=self.db_engine(),
            )
        return self._session_maker


from mcpunk.settings import Settings

deps = Dependencies()
