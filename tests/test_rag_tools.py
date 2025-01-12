from mcpunk.file_breakdown import Project as FileBreakdownProject
from mcpunk.tools import PROJECTS, configure_project
from tests.conftest import FileSet


def test_configure_project_basic(
    basic_file_set: FileSet,
    test_id: str,
) -> None:
    configure_project(root_path=basic_file_set.root, project_name=test_id)
    assert test_id in PROJECTS
    chunk_project = PROJECTS[test_id].chunk_project

    # Check that the chunk project created by the tool is the same as one created
    # by hand here. The point of this is to just check that the tool is instantiating
    # the project appropriately.
    expected_chunk_project = FileBreakdownProject(root=basic_file_set.root)
    expected_serialised_file_map = {
        str(x.abs_path): x.model_dump(mode="json") for x in expected_chunk_project.files
    }
    actual_serialised_file_map = {
        str(x.abs_path): x.model_dump(mode="json") for x in chunk_project.files
    }
    assert actual_serialised_file_map == expected_serialised_file_map
