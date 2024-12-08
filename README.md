# MCPunk 🤖

MCPunk provides tools for [Roaming RAG](https://arcturus-labs.com/blog/2024/11/21/roaming-rag--make-_the-model_-find-the-answers/)
with [Model Context Protocol](https://github.com/modelcontextprotocol).

MCPunk is built with the following in mind
- **Chat is king** - 
- **Human in the loop always** -
- **Context must be carefully managed** - as context 

**Core functionality** allows your LLM to configure a project (e.g. a directory 
containing Python files). The files in this project are automatically "chunked". 
Each chunk is e.g. a Python function or a markdown section.
The LLM can then query the entire project for chunks with specific names or with
specific text in their contents. The LLM can then fetch the entire contents
of individual chunks.


**On top of this**, MCPunk provides tools for analysing git diffs to help
with PR reviews, and provides a task queue that LLMs can read and write, allowing
you to split work across multiple chats to keep context manageable.

All this with no SaaS, no pricing, nothing. Just you and Claude Desktop.

# Setup

Just put the following in your `claude_desktop_config.json`

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

# Key Concepts

#### Roaming RAG

TODO

#### Chunks

TODO


# Common Usage Patterns

### Answer Questions About Your Codebase

TODO


### Search for Bugs

(this is a genuine race condition in MCPunk but given how things are used
it's a big "who cares")

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


### PR Review

TODO

### Split Work Into Tasks

TODO

# Limitations

- Sometimes LLM is poor at searching. e.g. search for "dependency", missing
  terms "dependencies". Room to stem things.
- Sometimes LLM will try to find a specific piece of critical code but fail to 
  find it, then continue without acknowledging it has limited contextual awareness.  


# Configuration

TODO

# Roadmap

MCPunk is at a minimum usable state right now.
Planned functionality
- Better ability to chunk git diffs
- Ability for users to provide custom code to perform chunking
- Improved logging, likely into the db itself
- Possibly stemming for search


# Development

TODO
