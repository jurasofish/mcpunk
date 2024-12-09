import ast
import logging
from typing import Annotated, assert_never

import asttokens
import more_itertools
from asttokens.util import Token
from asttokens.util import walk as asttokens_walk
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Callable(BaseModel):
    """Represents a callable (function/class) definition in the source code."""

    name: Annotated[str, Field(description="Name of the function or class")]
    # line/col/offset are for where `my_func` begins in `def my_func(...):` or
    # `MyClass` in `class MyClass(...):`
    line: Annotated[int, Field(description="First line is 1")]
    col: Annotated[int, Field(description="First column is 0")]
    offset: Annotated[int, Field(description="char offset corresponding to line & col.")]
    code_offset_start: Annotated[
        int,
        Field(description="Character offset of the start of the callable"),
    ]
    code_offset_end: Annotated[
        int,
        Field(description="Character offset of the end of the callable"),
    ]
    # This is the whole code block. For a function it will include decorators,
    # for example. Does NOT line up with line/col/offset.
    code: Annotated[str, Field(description="Complete source code of the callable")]

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    def from_source_code(
        cls,
        source_code: str,
    ) -> list["Callable"]:
        """Extract all callables from the given source code."""
        try:
            atok = asttokens.ASTTokens(source_code, parse=True)
        except SyntaxError:
            logger.error(  # noqa: TRY400
                f"Skipping {source_code} because it's not valid Python syntax",
            )
            return []
        assert atok.tree is not None
        nodes: list[ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef] = [
            n
            for n in asttokens_walk(
                atok.tree,
                # Joined strings seem to relate to f-strings, and enabling
                # them seems to be problematic. Let's just skip them.
                include_joined_str=False,
            )
            if isinstance(n, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef)
        ]
        callables = []
        for node in nodes:
            # print(ast.dump(node, indent=4))
            # print(atok.get_text(node))

            callable_name = node.name

            prefixes: list[str]
            if isinstance(node, ast.FunctionDef):
                prefixes = ["def"]
            elif isinstance(node, ast.AsyncFunctionDef):
                prefixes = ["async", "def"]
            elif isinstance(node, ast.ClassDef):
                prefixes = ["class"]
            else:
                assert_never(node)

            all_tokens: list[Token] = list(atok.get_tokens(node))
            # Make sure we sort by position in the file
            all_tokens = sorted(all_tokens, key=lambda x: x.startpos)

            callable_start_tok: Token | None = None
            window_size = len(prefixes) + 1
            looking_for = [*prefixes, callable_name]
            for window_elements in more_itertools.sliding_window(all_tokens, window_size):
                # This is a bit gross
                assert len(window_elements) == window_size
                if looking_for == [x.string for x in window_elements]:
                    callable_start_tok = window_elements[-1]
                    break

            if callable_start_tok is None:
                raise AssertionError(
                    f"Could not find callable {callable_name} in {node}\n"
                    f"{atok.get_text(node)}\n"
                    f"{ast.dump(node, indent=4)}\n",
                )

            range_ = atok.get_text_range(node)
            callable_ = Callable(
                name=node.name,
                line=callable_start_tok.start[0],
                col=callable_start_tok.start[1],
                offset=callable_start_tok.startpos,
                code=atok.get_text(node),
                code_offset_start=range_[0],
                code_offset_end=range_[1],
            )
            callables.append(callable_)
        return callables


def extract_imports(source_code: str) -> list[str]:
    """Extract all module-level import statements from source code.

    Takes source code as input and returns a list of import statements.
    """
    atok = asttokens.ASTTokens(source_code, parse=True)
    imports: list[str] = []

    for node in atok.tree.body:  # type: ignore[union-attr]
        if isinstance(node, ast.Import | ast.ImportFrom):
            import_code = atok.get_text(node)
            imports.append(import_code)

    return imports


def extract_module_statements(source_code: str) -> list[str]:
    """Extract all module-level statements from source code.

     function/class definitions are inserted like `def func1...` or `class MyClass...`
     to provide context around where the module-level statements are defined.

    Takes source code as input and returns a list of statement strings.
    """
    # TODO: include comments

    atok = asttokens.ASTTokens(source_code, parse=True)
    statements: list[str] = []

    for node in atok.tree.body:  # type: ignore[union-attr]
        if isinstance(node, ast.FunctionDef):
            statements.append(f"def {node.name}...")
        elif isinstance(node, ast.AsyncFunctionDef):
            statements.append(f"async def {node.name}...")
        elif isinstance(node, ast.ClassDef):
            statements.append(f"class {node.name}...")
        elif isinstance(node, ast.Import | ast.ImportFrom):
            pass
        else:
            statement_code = atok.get_text(node)
            statements.append(statement_code)

    return statements
