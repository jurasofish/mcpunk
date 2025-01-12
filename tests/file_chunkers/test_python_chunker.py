from pathlib import Path

import pytest

from mcpunk.file_chunk import ChunkCategory
from mcpunk.file_chunkers import PythonChunker


def test_python_chunker_basic() -> None:
    """A basic test that it picks out key elements.

    Notably the picking apart of python code into callables, imports, and module-level
    statements is tested elsewhere.
    """
    source_code = """\
from typing import List
import os

x = 1

def func1(a: int) -> str:
    return str(a)

y = 2

class MyClass:
    def method1(self) -> None:
        pass

    @property
    def prop1(self) -> int:
        return 42
"""
    assert PythonChunker.can_chunk("", Path("test.py"))
    assert not PythonChunker.can_chunk("", Path("test.txt"))

    chunks = PythonChunker(source_code, Path("test.py")).chunk_file()
    chunks = sorted(chunks, key=lambda x: x.line if x.line is not None else -1)

    assert [x.name for x in chunks] == [
        "<imports>",
        "<module_level_statements>",
        "func1",
        "MyClass",
        "method1",
        "prop1",
    ]

    # Test categories
    assert chunks[0].category.value == "imports"
    assert chunks[1].category.value == "module_level"
    assert chunks[2].category.value == "callable"
    assert chunks[3].category.value == "callable"
    assert chunks[4].category.value == "callable"
    assert chunks[5].category.value == "callable"

    # Test content
    assert chunks[0].content == "from typing import List\nimport os"
    assert chunks[1].content == "x = 1\ndef func1...\ny = 2\nclass MyClass..."

    assert chunks[2].content == "def func1(a: int) -> str:\n    return str(a)"
    assert chunks[2].line == 6

    assert "class MyClass:" in chunks[3].content
    assert chunks[3].line == 11

    assert "def method1(self)" in chunks[4].content
    assert chunks[4].line == 12

    assert "@property" in chunks[5].content
    assert "def prop1(self)" in chunks[5].content
    assert chunks[5].line == 16


def test_python_chunker_empty() -> None:
    """Tests empty source files produce empty chunk lists."""
    empty_source = ""
    chunks = PythonChunker(empty_source, Path("test.py")).chunk_file()
    assert chunks == []


def test_python_chunker_only_imports() -> None:
    """Tests files with only imports."""
    imports_only = """\
from typing import List
import os
"""
    chunks = PythonChunker(imports_only, Path("test.py")).chunk_file()
    assert len(chunks) == 1
    assert chunks[0].name == "<imports>"
    assert chunks[0].content == "from typing import List\nimport os"


def test_python_chunker_only_module_level() -> None:
    """Tests files with only module level statements."""
    module_level_only = """\
x = 1
y = 2
"""
    chunks = PythonChunker(module_level_only, Path("test.py")).chunk_file()
    assert len(chunks) == 1
    assert chunks[0].name == "<module_level_statements>"
    assert chunks[0].content == "x = 1\ny = 2"


def test_python_chunker_only_callables() -> None:
    """Tests files with only function/class definitions."""
    callables_only = """\
def func1() -> None:
    pass

class MyClass:
    def method1(self) -> None:
        pass
"""
    chunks = PythonChunker(callables_only, Path("test.py")).chunk_file()
    assert len(chunks) == 4
    assert [x.name for x in chunks] == ["<module_level_statements>", "func1", "MyClass", "method1"]
    module_level = chunks[0]
    assert module_level.category == ChunkCategory.module_level
    # We should still have module level statements, just with skeleton of the callables:
    assert module_level.content == "def func1...\nclass MyClass..."


def test_python_chunker_invalid_syntax() -> None:
    with pytest.raises(Exception, match=".*"):
        _ = PythonChunker("x = (1", Path("test.py")).chunk_file()
