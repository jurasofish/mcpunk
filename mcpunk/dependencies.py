# ruff: noqa: E402
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Union

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


@dataclass
class DependencyState:
    settings: Union["Settings", None] = None
    engine: Engine | None = None
    session_maker: sessionmaker[Session] | None = None

    settings_override: Union["Settings", None] = None
    engine_override: Engine | None = None
    session_maker_override: sessionmaker[Session] | None = None


class Dependencies(metaclass=Singleton):
    """Dependencies that can play nice with testing.

    If you want to get settings, db session, etc. do it here. This means that in
    tests we can patch/etc JUST this object and have everything play nice.
    """

    def __init__(self) -> None:
        self._state = DependencyState()

    def settings(self) -> "Settings":
        if self._state.settings_override is not None:
            return self._state.settings_override
        if self._state.settings is None:
            self._state.settings = Settings()
        return self._state.settings

    def db_engine(self) -> "Engine":
        if self._state.engine_override is not None:
            return self._state.engine_override
        if self._state.engine is None:
            settings = self.settings()
            self._state.engine = create_engine(
                f"sqlite:///{settings.db_path}?check_same_thread=true&timeout=10&uri=true",
                echo=settings.db_echo,
            )
        return self._state.engine

    def session_maker(self) -> sessionmaker[Session]:
        if self._state.session_maker_override is not None:
            return self._state.session_maker_override
        if self._state.session_maker is None:
            self._state.session_maker = sessionmaker(
                autocommit=False,
                expire_on_commit=True,
                autoflush=False,
                bind=self.db_engine(),
            )
        return self._state.session_maker

    @contextmanager
    def override(
        self,
        settings: Union["Settings", None] = None,
        db_engine: Engine | None = None,
        session_maker: sessionmaker[Session] | None = None,
    ) -> Generator[None, None, None]:
        """Override dependency functions for testing."""
        # Backup current state and methods
        orig_state = self._state
        self._state = DependencyState(
            settings_override=settings,
            engine_override=db_engine,
            session_maker_override=session_maker,
        )

        try:
            yield
        finally:
            self._state = orig_state


from mcpunk.settings import Settings

deps = Dependencies()
