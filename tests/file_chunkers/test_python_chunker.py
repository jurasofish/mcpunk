from pathlib import Path

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
