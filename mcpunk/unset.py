"""Common unset values.

This module exports
1. `Unset`: Singleton object representing an unset state.
2. `AnyUnset`: Alias for `Unset`, typed as `Any` (so essentially ignored by mypy)
3. `UnsetType`: Enum class containing the `Unset` singleton.

This is useful in situations where you need to specify a value as "not defined" or "unset",
but where e.g. `None` is not appropriate (e.g. because `None` is a meaningful value).

Typical uses are like
- `def foo(bar: str | UnsetType = Unset, baz: str | UnsetType):`
  In this we've used `Unset` as we've typed it such that it recognizes `UnsetType`
  as a valid value.
- `def foo(bar: str = AnyUnset):` Here we've used `AnyUnset` since the argument
  is typed as `str`, so passing in `Unset` would raise a type error. But because
  `AnyUnset` is typed as `Any`, it's essentially ignored by mypy.
- API models like `class x(BaseModel): y: int = AnyUnset`
"""

from enum import Enum
from typing import Any

from pydantic_core import core_schema

__all__ = [
    "AnyUnset",
    "Unset",
    "UnsetType",
]


class UnsetType(Enum):
    Unset = object()

    def __repr__(self) -> str:
        return "<Unset>"

    def __str__(self) -> str:
        return self.__repr__()

    def __bool__(self) -> bool:
        return False

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source: Any,
        _handler: Any,
    ) -> core_schema.IsInstanceSchema:
        return core_schema.is_instance_schema(UnsetType)


Unset = UnsetType.Unset
AnyUnset: Any = UnsetType.Unset
