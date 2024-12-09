import textwrap

import deepdiff
import pytest

from mcpunk.python_file_analysis import Callable, extract_imports, extract_module_statements

# This makes pytest print nice diffs when asserts fail
# within this function.
pytest.register_assert_rewrite("assert_calls_equal")


def sorted_callables(calls: list[Callable]) -> list[Callable]:
    """Sort a list of Call objects by line and column."""
    return sorted(calls, key=lambda x: (x.line, x.col, x.code))


def assert_callables_equal(actual: list[Callable], expected: list[Callable]) -> None:
    """Assert that two lists of Call objects are equal."""
    actual = sorted_callables(actual)
    expected = sorted_callables(expected)
    assert len(actual) == len(expected)
    actual_dicts = [x.model_dump(mode="json") for x in actual]
    expected_dicts = [x.model_dump(mode="json") for x in expected]
    if actual_dicts != expected_dicts:
        print("\n")  # Help format with pytest
        for i, (a, e) in enumerate(zip(actual_dicts, expected_dicts, strict=True)):
            if a != e:
                print(f"Expected {i}: {e}")
                print(f"Actual   {i}: {a}")
                print(f"Diff {i}: {deepdiff.DeepDiff(a, e)}")
            else:
                print(f"Pair {i} is equal")
        # raise AssertionError(deepdiff.DeepDiff(actual_dicts, expected_dicts))
    assert actual == expected


def test_empty_source_code() -> None:
    source = textwrap.dedent("""\


    """)
    actual = Callable.from_source_code(source)
    expected: list[Callable] = []
    assert_callables_equal(actual, expected)


def test_no_function_definitions() -> None:
    source = textwrap.dedent("""\
x = 1
y = x + 2
    """)
    actual = Callable.from_source_code(source)
    expected: list[Callable] = []
    assert_callables_equal(actual, expected)


def test_basic_function_def() -> None:
    source = textwrap.dedent("""\
def my_func(x):
    return x
my_func("hello")

def empty_func():
    pass

def empty_func_ii():
    '''some docstring'''
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="my_func",
            line=1,
            col=4,
            offset=4,
            code_offset_start=0,
            code_offset_end=28,
            code="def my_func(x):\n    return x",
        ),
        Callable(
            name="empty_func",
            line=5,
            col=4,
            offset=51,
            code_offset_start=47,
            code_offset_end=73,
            code="def empty_func():\n    pass",
        ),
        Callable(
            name="empty_func_ii",
            line=8,
            col=4,
            offset=79,
            code_offset_start=75,
            code_offset_end=75 + 45,
            code="def empty_func_ii():\n    '''some docstring'''",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_function_def_with_callable() -> None:
    source = textwrap.dedent("""\
@wrapper()
def my_func(x):
    return x
my_func("hello")
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="my_func",
            line=2,
            col=4,
            offset=15,
            code_offset_start=0,
            code_offset_end=39,
            code="@wrapper()\ndef my_func(x):\n    return x",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_simple_class() -> None:
    """Test basic class definition without methods."""
    source = textwrap.dedent("""\
class SimpleClass:
    pass
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="SimpleClass",
            line=1,
            col=6,
            offset=6,
            code_offset_start=0,
            code_offset_end=27,
            code="class SimpleClass:\n    pass",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_async_function() -> None:
    """Test async function definition."""
    source = textwrap.dedent("""\
async def fetch_data():
    return "data"
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="fetch_data",
            line=1,
            col=10,
            offset=10,
            code_offset_start=0,
            code_offset_end=41,
            code='async def fetch_data():\n    return "data"',
        ),
    ]
    assert_callables_equal(actual, expected)


def test_nested_function() -> None:
    """Test nested function definition."""
    source = textwrap.dedent("""\
def outer():
    def inner():
        return True
    return inner
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="outer",
            line=1,
            col=4,
            offset=4,
            code_offset_start=0,
            code_offset_end=66,
            code="def outer():\n    def inner():\n        return True\n    return inner",
        ),
        Callable(
            name="inner",
            line=2,
            col=8,
            offset=21,
            code_offset_start=13,
            code_offset_end=13 + 36,
            code="    def inner():\n        return True",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_class_with_method() -> None:
    """Test class with a single method."""
    source = textwrap.dedent("""\
class MyClass:
    def my_method(self):
        return 42
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="MyClass",
            line=1,
            col=6,
            offset=6,
            code_offset_start=0,
            code_offset_end=57,
            code="class MyClass:\n    def my_method(self):\n        return 42",
        ),
        Callable(
            name="my_method",
            line=2,
            col=8,
            offset=23,
            code_offset_start=15,
            code_offset_end=15 + 42,
            code="    def my_method(self):\n        return 42",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_nested_classes() -> None:
    """Test nested class definitions with methods."""
    source = textwrap.dedent("""\
class Outer:
    class Inner:
        def inner_method(self):
            return "inner"

        class DeepNested:
            @staticmethod
            def deep_method():
                return "deep"

    def outer_method(self):
        return "outer"
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="Outer",
            line=1,
            col=6,
            offset=6,
            code_offset_start=0,
            code_offset_end=254,
            code="class Outer:\n"
            "    class Inner:\n"
            "        def inner_method(self):\n"
            '            return "inner"\n'
            "\n"
            "        class DeepNested:\n"
            "            @staticmethod\n"
            "            def deep_method():\n"
            '                return "deep"\n'
            "\n"
            "    def outer_method(self):\n"
            '        return "outer"',
        ),
        Callable(
            name="Inner",
            line=2,
            col=10,
            offset=23,
            code_offset_start=13,
            code_offset_end=13 + 189,
            code="    class Inner:\n"
            "        def inner_method(self):\n"
            '            return "inner"\n'
            "\n"
            "        class DeepNested:\n"
            "            @staticmethod\n"
            "            def deep_method():\n"
            '                return "deep"',
        ),
        Callable(
            name="inner_method",
            line=3,
            col=12,
            offset=42,
            code_offset_start=30,
            code_offset_end=30 + 58,
            code='        def inner_method(self):\n            return "inner"',
        ),
        Callable(
            name="DeepNested",
            line=6,
            col=14,
            offset=104,
            code_offset_start=90,
            code_offset_end=90 + 112,
            code="        class DeepNested:\n"
            "            @staticmethod\n"
            "            def deep_method():\n"
            '                return "deep"',
        ),
        Callable(
            name="deep_method",
            line=8,
            col=16,
            offset=158,
            code_offset_start=116,
            code_offset_end=116 + 86,
            code="            @staticmethod\n"
            "            def deep_method():\n"
            '                return "deep"',
        ),
        Callable(
            name="outer_method",
            line=11,
            col=8,
            offset=212,
            code_offset_start=204,
            code_offset_end=204 + 50,
            code='    def outer_method(self):\n        return "outer"',
        ),
    ]
    assert_callables_equal(actual, expected)


def test_multiline_function_definition() -> None:
    """Test function definitions that span multiple lines."""
    source = textwrap.dedent("""\
def long_function_name(
    param1: str,
    param2: int,
    param3: list[
        dict[str, int]
    ],
    *args: tuple[str, ...],
    **kwargs: dict[
        str,
        Any
    ],
) -> None:
    return None
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="long_function_name",
            line=1,
            col=4,
            offset=4,
            code_offset_start=0,
            code_offset_end=212,
            code="def long_function_name(\n"
            "    param1: str,\n"
            "    param2: int,\n"
            "    param3: list[\n"
            "        dict[str, int]\n"
            "    ],\n"
            "    *args: tuple[str, ...],\n"
            "    **kwargs: dict[\n"
            "        str,\n"
            "        Any\n"
            "    ],\n"
            ") -> None:\n"
            "    return None",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_multiline_class_definition() -> None:
    """Test class definitions that span multiple lines."""
    source = textwrap.dedent("""\
class ComplexClass(
    BaseClass,
    Generic[
        TypeVar1,
        TypeVar2,
    ],
    metaclass=ABCMeta,
):
    '''A complex class with multi-line definition'''

    def __init__(
        self,
        param1: str,
        param2: int = 42
    ) -> None:
        self.param1 = param1
        self.param2 = param2
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="ComplexClass",
            line=1,
            col=6,
            offset=6,
            code_offset_start=0,
            code_offset_end=321,
            code="class ComplexClass(\n"
            "    BaseClass,\n"
            "    Generic[\n"
            "        TypeVar1,\n"
            "        TypeVar2,\n"
            "    ],\n"
            "    metaclass=ABCMeta,\n"
            "):\n"
            "    '''A complex class with multi-line definition'''\n"
            "\n"
            "    def __init__(\n"
            "        self,\n"
            "        param1: str,\n"
            "        param2: int = 42\n"
            "    ) -> None:\n"
            "        self.param1 = param1\n"
            "        self.param2 = param2",
        ),
        Callable(
            name="__init__",
            line=11,
            col=8,
            offset=179,
            code_offset_start=171,
            code_offset_end=171 + 150,
            code="    def __init__(\n"
            "        self,\n"
            "        param1: str,\n"
            "        param2: int = 42\n"
            "    ) -> None:\n"
            "        self.param1 = param1\n"
            "        self.param2 = param2",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_multiline_decorators() -> None:
    """Test function with multi-line decorators."""
    source = textwrap.dedent("""\
@decorator1(
    param1="value1",
    param2="value2",
)
@decorator2(
    param3={
        "key1": "value1",
        "key2": "value2",
    }
)
def decorated_function(
    x: int,
    y: str,
) -> bool:
    return True
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="decorated_function",
            line=11,
            col=4,
            offset=147,
            code_offset_start=0,
            code_offset_end=217,
            code="@decorator1(\n"
            '    param1="value1",\n'
            '    param2="value2",\n'
            ")\n"
            "@decorator2(\n"
            "    param3={\n"
            '        "key1": "value1",\n'
            '        "key2": "value2",\n'
            "    }\n"
            ")\n"
            "def decorated_function(\n"
            "    x: int,\n"
            "    y: str,\n"
            ") -> bool:\n"
            "    return True",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_unicode_names() -> None:
    """Test handling of Unicode characters in function and class names."""
    source = textwrap.dedent("""\
def 你好_world():
    pass

class お早う_class:
    def μ_method():
        pass

def λ_function():
    yield from range(10)
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="你好_world",
            line=1,
            col=4,
            offset=4,
            code_offset_start=0,
            code_offset_end=24,
            code="def 你好_world():\n    pass",
        ),
        Callable(
            name="お早う_class",
            line=4,
            col=6,
            offset=32,
            code_offset_start=26,
            code_offset_end=26 + 49,
            code="class お早う_class:\n    def μ_method():\n        pass",
        ),
        Callable(
            name="μ_method",
            line=5,
            col=8,
            offset=51,
            code_offset_start=43,
            code_offset_end=43 + 32,
            code="    def μ_method():\n        pass",
        ),
        Callable(
            name="λ_function",
            line=8,
            col=4,
            offset=81,
            code_offset_start=77,
            code_offset_end=77 + 42,
            code="def λ_function():\n    yield from range(10)",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_conditional_definitions() -> None:
    """Test functions and classes defined inside conditional blocks."""
    source = textwrap.dedent("""\
if True:
    def true_func():
        pass
else:
    def false_func():
        pass

try:
    class TryClass:
        pass
except Exception:
    class ExceptClass:
        pass
finally:
    def finally_func():
        return True
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="true_func",
            line=2,
            col=8,
            offset=17,
            code_offset_start=9,
            code_offset_end=9 + 33,
            code="    def true_func():\n        pass",
        ),
        Callable(
            name="false_func",
            line=5,
            col=8,
            offset=57,
            code_offset_start=49,
            code_offset_end=49 + 34,
            code="    def false_func():\n        pass",
        ),
        Callable(
            name="TryClass",
            line=9,
            col=10,
            offset=100,
            code_offset_start=90,
            code_offset_end=90 + 32,
            code="    class TryClass:\n        pass",
        ),
        Callable(
            name="ExceptClass",
            line=12,
            col=10,
            offset=151,
            code_offset_start=141,
            code_offset_end=141 + 35,
            code="    class ExceptClass:\n        pass",
        ),
        Callable(
            name="finally_func",
            line=15,
            col=8,
            offset=194,
            code_offset_start=186,
            code_offset_end=186 + 43,
            code="    def finally_func():\n        return True",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_property_and_special_methods() -> None:
    """Test property decorators and special methods."""
    source = textwrap.dedent("""\
class DataClass:
    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val

    @classmethod
    def from_string(cls, s: str) -> 'DataClass':
        return cls(int(s))

    @staticmethod
    def validate(x: int) -> bool:
        return x > 0

    def __str__(self) -> str:
        return str(self._value)

    async def __aiter__(self):
        yield self._value
    """)
    actual = Callable.from_source_code(source)
    expected = [
        Callable(
            name="DataClass",
            line=1,
            col=6,
            offset=6,
            code_offset_start=0,
            code_offset_end=458,
            code="class DataClass:\n"
            "    @property\n"
            "    def value(self) -> int:\n"
            "        return self._value\n\n"
            "    @value.setter\n"
            "    def value(self, val: int) -> None:\n"
            "        self._value = val\n\n"
            "    @classmethod\n"
            "    def from_string(cls, s: str) -> 'DataClass':\n"
            "        return cls(int(s))\n\n"
            "    @staticmethod\n"
            "    def validate(x: int) -> bool:\n"
            "        return x > 0\n\n"
            "    def __str__(self) -> str:\n"
            "        return str(self._value)\n\n"
            "    async def __aiter__(self):\n"
            "        yield self._value",
        ),
        Callable(
            name="value",
            line=3,
            col=8,
            offset=39,
            code_offset_start=17,
            code_offset_end=17 + 68,
            code="    @property\n    def value(self) -> int:\n        return self._value",
        ),
        Callable(
            name="value",
            line=7,
            col=8,
            offset=113,
            code_offset_start=87,
            code_offset_end=87 + 82,
            code="    @value.setter\n    def value(self, val: int) -> None:\n"
            "        self._value = val",
        ),
        Callable(
            name="from_string",
            line=11,
            col=8,
            offset=196,
            code_offset_start=171,
            code_offset_end=171 + 92,
            code="    @classmethod\n    def from_string(cls, s: str) -> 'DataClass':\n"
            "        return cls(int(s))",
        ),
        Callable(
            name="validate",
            line=15,
            col=8,
            offset=291,
            code_offset_start=265,
            code_offset_end=265 + 72,
            code="    @staticmethod\n    def validate(x: int) -> bool:\n        return x > 0",
        ),
        Callable(
            name="__str__",
            line=18,
            col=8,
            offset=347,
            code_offset_start=339,
            code_offset_end=339 + 61,
            code="    def __str__(self) -> str:\n        return str(self._value)",
        ),
        Callable(
            name="__aiter__",
            line=21,
            col=14,
            offset=416,
            code_offset_start=402,
            code_offset_end=402 + 56,
            code="    async def __aiter__(self):\n        yield self._value",
        ),
    ]
    assert_callables_equal(actual, expected)


def test_extract_imports_basic() -> None:
    source = """\
import os
import sys as system
import json, csv
from pathlib import Path
from typing import List, Optional as Opt
from . import local_module
from ..parent import something as other
"""

    result = extract_imports(source)
    assert result == [
        "import os",
        "import sys as system",
        "import json, csv",
        "from pathlib import Path",
        "from typing import List, Optional as Opt",
        "from . import local_module",
        "from ..parent import something as other",
    ]


def test_extract_mixed_scope_imports() -> None:
    source = """
import os  # module level

def func1():
    import sys  # inside function
    print("hello")

import json  # module level again

class MyClass:
    import csv  # inside class

    def method(self):
        from pathlib import Path  # inside method
        return Path('.')

from typing import List  # module level at end
"""

    result = extract_imports(source)
    assert result == ["import os", "import json", "from typing import List"]


def test_extract_module_statements() -> None:
    source = """\
import os
x = 1

def func1():
    y = 2
    return y

CONSTANT = "test"
import json

class MyClass:
    z = 3

    def method(self):
        pass

final_var = True

a = (
    1,
    # Internal comment
    2,
)

if __name__ == "__main__":
    print("hey!")

# A comment!

async def func2():
    pass
"""

    result = extract_module_statements(source)
    assert result == [
        "x = 1",
        "def func1...",
        'CONSTANT = "test"',
        "class MyClass...",
        "final_var = True",
        "a = (\n    1,\n    # Internal comment\n    2,\n)",
        'if __name__ == "__main__":\n    print("hey!")',
        "async def func2...",
    ]
