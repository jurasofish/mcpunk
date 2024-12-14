from pathlib import Path

from mcpunk.file_chunkers import VueChunker


def test_vue_chunker() -> None:
    source_code = """\
<template>
  <div class="example">{{ msg }}</div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      msg: 'Hello world!'
    }
  }
}
</script>

blah

<style>
.example {
  color: red;
}
</style>

<custom1>
  This could be e.g. documentation for the component.
</custom1>
something_else
    """
    assert VueChunker.can_chunk("", Path("anything.vue"))
    assert not VueChunker.can_chunk("", Path("blah.vues"))

    chunks = VueChunker(source_code, Path("anything.vue")).chunk_file()
    chunks = sorted(
        chunks,
        key=lambda x: x.line if x.line is not None else 999999,
    )

    assert [x.name for x in chunks] == [
        "template",
        "script",
        "style",
        "custom1",
        "outer_content",
    ]

    # Test line numbers
    assert chunks[0].line == 1  # template
    assert chunks[1].line == 5  # script
    assert chunks[2].line == 17  # style
    assert chunks[3].line == 23  # custom1

    # Test content
    assert (
        chunks[0].content
        == """\
<template>
  <div class="example">{{ msg }}</div>
</template>"""
    )

    assert (
        chunks[1].content
        == """\
<script lang="ts">
export default {
  data() {
    return {
      msg: 'Hello world!'
    }
  }
}
</script>"""
    )

    assert (
        chunks[2].content
        == """\
<style>
.example {
  color: red;
}
</style>"""
    )

    assert (
        chunks[3].content
        == """\
<custom1>
  This could be e.g. documentation for the component.
</custom1>"""
    )

    # Test outer content combines non-tag content
    assert chunks[4].content.strip() == "blah\nsomething_else"

    # Test categories
    assert all(chunk.category == "other" for chunk in chunks[:4])
    assert chunks[4].category == "module_level"
