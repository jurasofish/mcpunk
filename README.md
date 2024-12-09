# MCPunk 🤖

MCPunk provides tools for [Roaming RAG](https://arcturus-labs.com/blog/2024/11/21/roaming-rag--make-_the-model_-find-the-answers/)
with [Model Context Protocol](https://github.com/modelcontextprotocol).

MCPunk is built with the following in mind

- **Context is King** - LLMs can be great but only if provided with appropriate
  context: not too long, focused and relevant.
- **Human in the Loop** - **You** can see exactly what data the LLM has considered
  and how it found it, **You** can jump into chat and direct things wherever you want.
- **Tools are Next** - LLMs have landed. And the vibe is that improvements are stagnating.
  The next wave of LLM-based productivity will come from the tools that use LLMs well.

**Core functionality** allows your LLM to configure a project (e.g. a directory
containing Python files). The files in this project are automatically "chunked".
Each chunk is e.g. a Python function or a markdown section.
The LLM can then query the entire project for chunks with specific names or with
specific text in their contents. The LLM can then fetch the entire contents
of individual chunks.

**On top of this**, MCPunk provides tools for analysing git diffs to help
with PR reviews, and provides a task queue that LLMs can read and write, allowing
you to split work across multiple chats to keep context manageable.

All this with no SaaS, no pricing, nothing (well you need a claude SaaS sub).
Just you and Claude Desktop, with all tools running on your local machine after
one tiny snippet in `claude_desktop_config.json`.

# Getting started

First, [install uv](https://docs.astral.sh/uv/getting-started/installation/).

Next, put the following in your `claude_desktop_config.json`.
[Details about `claude_desktop_config.json` including location](https://glama.ai/blog/2024-11-25-model-context-protocol-quickstart#testing-mcp-using-claude-desktop).

`"command": "uvx",` might not work, and you may need to use e.g. `"command": "/Users/michael/.local/bin/uvx",`

```json
{
  "mcpServers": {
    "MCPunk": {
      "command": "uvx",
      "args": ["mcpunk"]
    }
  }
}
```

Next, start claude desktop and you should see the tools available after a small delay
![](assets/setup.png)

Next, ask it to set up a project like "hey pal can you set up the ~/git/mcpunk project".
Then start asking away, like "how is the tasks database schema structured?"

# Key Concepts

#### Roaming RAG

TODO discussion but for the moment see

- https://arcturus-labs.com/blog/2024/11/21/roaming-rag--make-_the-model_-find-the-answers/
- https://simonwillison.net/2024/Dec/6/roaming-rag/

#### Chunks

TODO discuss a whole lot more.

A chunk is a subsection of a file. For example,

- A single python function
- A markdown section
- All the imports from a Python file
- The diff of one file out of a multi-file diff

Chunks are created from a file by [chunkers](mcpunk/file_chunkers.py)
(currently only Python and Markdown but plans to add more builtin ones
plus [customisable ones](#roadmap))

When a project is set up in MCPunk, it goes through all files and applies
the first matching chunker to it. The LLM can then use tools to (1) query for files
containing chunks with specific text in them, (2) query all chunks in a specific
file, and (3) fetch the full contents of a chunk.

This basic foundation enables claude to effectively navigate relatively large
codebases by starting with a broad search for relevant files and narrowing in
on relevant areas.

# Common Usage Patterns

### Answer Questions About Your Codebase & Search for Bugs

(this is a genuine race condition in MCPunk but given how things are used
it's a big "who cares 🤷")

- **[User]** Hey pal can you please set up the ~/git/mcpunk repo, then help me
  troubleshoot why I'm sometimes seeing that with multiple concurrent clients
  the same task can be picked up twice
- **[Claude]** Call `configure_project`
- **[Claude]** Call `list_files_by_chunk_type_and_chunk_contents` searching for `task` and `get_task` callables
- **[Claude]** Call `list_all_chunk_names_in_file` for `db.py`
- **[Claude]** Call `chunk_details` for `db.py:get_task`
- **[Claude]** I see the potential issue - there's a race condition in the task
  retrieval process. The current implementation has a Time-Of-Check to Time-Of-Use
  (TOCTOU) vulnerability because the selection and update of the task aren't atomic....
- **[User]** Great job pal!

### PR Review Split Into Tasks

This demonstrates

- Grab a diff between current branch and another
- Putting tasks on a queue for other LLM chat sessions to perform
- Running tasks from the queue

.

- **[user]** Hey pal can you please set up the ~/git/mcpunk repo and have a
  look at the current branch versus `scratch/1.5`
- **[Claude]** Sets up ~/git/mcpunk and calls `diff_with_ref` for ref `scratch/1.5`
- **[Claude]** I see you've made several changes, primarily adding a new test
  file `tests/test_git_analysis.py`...
- **[user]** how does this fit into the rest of the codebase?
- **[Claude]** Makes 5 tool calls for listing files by chunks, listing chunks,
  fetching chunk details
- **[Claude]** I see - the code parses git reflog output to track recently
  checked out branches. The main function get_recent_branches takes a repo path
  and returns the last N branches that were checked out, using _branches_from_reflog
  as a helper to parse the raw reflog output.
- **[User]** If you were in a rush and had to direct someone to review this work,
  what would you direct them to look at? Please outline discrete pieces of work
- **[Claude]**
  - The `split("to ")[-1]` in _branches_from_reflog looks fragile
  - Test data only shows simple branch names, what about spaces/special chars?
  - Is example_reflog representative of real git reflog output?
  - Are we testing against actual git behavior?
- **[User]** Can you please go ahead and add a single task for each of these items,
  using the task tool. Each task must be totally self contained with all relevant context,
  such that a new person could pick it up and know exactly what to do.  For example,
  it must specify to set up the project, get the diff, and look at a specific area
  with refrenc to the remainder of the codebase, then mark the task as done with
  a relevant outcome note
- **[Claude]** (adds tasks)
  - `1.` Set up ~/git/mcpunk repo 2. Get diff between HEAD and scratch/1.5 3.
    Review _branches_from_reflog function in mcpunk/git_analysis.py, particularly
     the `split('to ')[-1]` logic 4. Check this against branch names containing
     spaces or special characters 5. If issues found, validate against git's reflog documentation
  - `1.` Set up ~/git/mcpunk repo 2. Get diff between HEAD and scratch/1.5 3.
    Compare example_reflog test data in tests/test_git_analysis.py against actual
    git reflog output from multiple repos 4. Verify it covers common reflog scenarios
    (merges, rebases, checkouts) 5. Document any missing patterns
  - `1.` Set up ~/git/mcpunk repo 2. Get diff between HEAD and scratch/1.5 3.
    Review get_recent_branches function in mcpunk/git_analysis.py 4. Verify there
    are integration tests that check the full function with a real git repo, not
    just the helper 5. If missing, document test gaps

Start a totally new chat:

- **[User]** Hey buddy can you please grab a task and complete it
- **[Claude]** grabs a task, sets up project, gets diff, digs around project
- **[Claude]** discusses details
- **[Claude]** marks task done with note:

```
Found potential issues with _branches_from_reflog function:
1. Current implementation is brittle as it uses simple string splitting
2. Could fail with branch names containing \"to \"
3. May break with non-standard reflog entries
Recommend using regex pattern matching to properly parse reflog format

follow_up_criticality: medium
```

### Work across multiple codebases

You can just ask your LLM to set up multiple projects, and it can freely query
across them. Handy if one depends on the other, and they're in different repos.
In this case the LLM should recognise this via imports.

# Limitations

- Sometimes LLM is poor at searching. e.g. search for "dependency", missing
  terms "dependencies". Room to stem things.
- Sometimes LLM will try to find a specific piece of critical code but fail to
  find it, then continue without acknowledging it has limited contextual awareness.
- "Large" projects are not well tested. A project with ~1000 Python files containing
  in total ~250k LoC works well. Takes ~5s to setup the project. As codebase
  size increases, time to perform initial chunking will increase, and likely
  more sophisticated searching will be required.

# Configuration

TODO but through env vars see [settings.py](mcpunk/settings.py)

# Roadmap

MCPunk is at a minimum usable state right now.

**Critical Planned functionality**

- Ability for users to provide custom code to perform chunking (critical)
- Add a bunch of prompts to help with using MCPunk. Without real "explain how to make
  a pancake to an alien"-type prompts things do fall a little flat.
- Repeat description in response - LLM has tendency to fetch tasks right after
  adding them to add note to add_tasks response noting not to fetch them unless
  explicitly instructed to do so. etc etc.

**High up on the roadmap**

- Improved logging, likely into the db itself
- Possibly stemming for search
- Change the whole "project" concept to not need files to actually exist - this
  leads to allowing "virtual" files inside the project.
  - Consider changing files from having a path to having a URI, so coule be like
    `file://...` / `http[s]://` / `gitdiff://` / etc arbitrary URIs
- Integrate with web searching
  - Flow like (1) LLM says "search for Caridina water parameters" (2) tool
    does web search and grabs the 10 highest pages and converts to markdown and
    chunks them and puts them in the virtual filesystem (3) LLM queries for chunks
    etc like usual.
- Chunking of git diffs. Currently, there's a tool to fetch an entire diff. This
  might be very large. Instead, the tool could be changed to `add_diff_to_project`
  and it puts files under the `gitdiff://` URI or under some fake path
- Database tweaks
  - Maybe migrations. More than likely just if db version has changed make a backup
    copy of the old one and start from scratch.
  - If db needs stay so simple, just switch to JSON file on disk. Multithread/process
    considerations.
- For small (say, <500 chars) files maybe just unconditionally put them as one
  chunk, not much point breaking them up.
- Switch up chunk fetching, like let's say
  - each chunk has a randomly generated id that's used to get its details
    (makes llm_known_chunks redundant 💩)
  - When listing chunks in a file, chunk id, number of  characters in chunk content
- Include module-level comments when extracting python module-level statements.
- Caching of a project, so it doesn't need to re-parse all files every time you
  restart MCP client
- Handle changed files sensibly, so you don't need to restart MCP client
  and re-add project on any file changes
- Ability to edit files - why not? Can do it like aider where LLM produces a diff.

**Just ideas**

- Something like tree sitter could possibly be used for a more generic chunker
- Better handling of large chunks
  - Configurable Max response size for chunks
  - Log warning for any chunk over max size when initialising project
- Tracking of characters sent/received, ideally by chat.
- State, logging, etc by chat

# Development

Largely still TODO this section

see [run_mcp_server.py](mcpunk/run_mcp_server.py).

If you set up claude desktop like below then you can restart it to see latest
changes as you work on MCPunk

```json
{
  "mcpServers": {
    "MCPunk": {
      "command": "/Users/michael/.local/bin/uvx",
      "args": [
        "--from",
        "/Users/michael/git/mcpunk",
        "--no-cache",
        "mcpunk"
      ]
    }
  }
}
```
