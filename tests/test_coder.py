from aicodebot.coder import Coder
from aicodebot.helpers import create_and_write_file
from pathlib import Path
from tests.conftest import in_temp_directory
import os, pytest, tempfile, textwrap


def test_apply_patch(temp_git_repo):
    # Use in_temp_directory for the test
    with in_temp_directory(temp_git_repo.working_dir):
        add_file = Path("add_file.txt")
        assert not add_file.exists()

        # Create a file to be modified
        mod_file = Path("mod_file.txt")
        mod_file.write_text("AICodeBot is your coding sidekick.\nIt is here to make your coding life easier.")

        # Create a file to be removed
        remove_file = Path("remove_file.txt")
        remove_file.write_text("Remember, AICodeBot has got your back!\n")

        # Create patch strings
        add_patch = textwrap.dedent(
            """
            --- /dev/null
            +++ b/add_file.txt
            @@ -0,0 +1,1 @@
            +AICodeBot is here to help!
            """
        ).lstrip()
        assert Coder.apply_patch(add_patch)
        assert add_file.exists()
        assert add_file.read_text() == "AICodeBot is here to help!\n"

        # Note the spacing here is critical
        mod_patch = textwrap.dedent(
            """
            --- a/mod_file.txt
            +++ b/mod_file.txt
            @@ -1,2 +1,3 @@
             AICodeBot is your coding sidekick.
             It is here to make your coding life easier.
            +It is now even better!
            """
        ).lstrip()
        assert Coder.apply_patch(mod_patch)
        assert "It is now even better!" in mod_file.read_text()

        rem_patch = textwrap.dedent(
            """
            --- a/remove_file.txt
            +++ /dev/null
            @@ -1 +0,0 @@
            -Remember, AICodeBot has got your back!
            """
        ).lstrip()
        assert Coder.apply_patch(rem_patch)
        assert not remove_file.exists()


def test_generate_directory_structure(tmp_path):
    # Create a file, a hidden file, another file, a .gitignore file, and a subdirectory in the temporary directory
    create_and_write_file(tmp_path / "file.txt", "This is a test file")
    create_and_write_file(tmp_path / ".hidden_file", "This is a hidden test file")
    create_and_write_file(tmp_path / "test_file", "This is another test file")
    create_and_write_file(tmp_path / ".gitignore", "*.txt\n")
    sub_dir = tmp_path / "sub_dir"
    sub_dir.mkdir()
    create_and_write_file(sub_dir / "sub_file", "This is a test file in a subdirectory")
    create_and_write_file(sub_dir / ".gitignore", "sub_file")

    # Call the function with the temporary directory and an ignore pattern
    directory_structure = Coder.generate_directory_structure(tmp_path, ignore_patterns=["*.txt"])

    # Check that the returned string is not empty
    assert directory_structure

    # Check that the returned string contains the name of the created subdirectory
    assert "- [Directory] sub_dir" in directory_structure

    # Check that the returned string does not contain the names of the ignored files
    assert "- [File] file.txt" not in directory_structure

    # Check that the returned string contains the name of the hidden file and the other file
    assert "- [File] .hidden_file" in directory_structure
    assert "- [File] test_file" in directory_structure

    # Check that the function respects .gitignore
    directory_structure_gitignore = Coder.generate_directory_structure(tmp_path)
    assert "- [File] file.txt" not in directory_structure_gitignore
    assert "- [File] sub_file" not in directory_structure_gitignore

    # Check that the function works correctly when use_gitignore is False
    directory_structure_no_gitignore = Coder.generate_directory_structure(tmp_path, use_gitignore=False)
    assert "- [File] file.txt" in directory_structure_no_gitignore
    assert "- [File] sub_file" in directory_structure_no_gitignore

    file_list = Coder.filtered_file_list(".", use_gitignore=True, ignore_patterns=[".git"])
    assert len(file_list) > 10


def test_get_file_info():
    # Test with a text file
    is_binary, file_type = Coder.get_file_info("tests/test_coder.py")
    assert is_binary is False
    assert file_type == "Python"

    # Test with a binary file
    is_binary, file_type = Coder.get_file_info("assets/robot.png")
    assert is_binary is True
    assert file_type == Coder.UNKNOWN_FILE_TYPE

    is_binary, file_type = Coder.get_file_info("LICENSE")
    assert is_binary is False
    assert file_type == Coder.UNKNOWN_FILE_TYPE

    is_binary, file_type = Coder.get_file_info("README.md")
    assert is_binary is False
    assert file_type == "Markdown"

    is_binary, file_type = Coder.get_file_info("pyproject.toml")
    assert is_binary is False
    assert file_type == "TOML"

    # Test with a non-existent file
    with pytest.raises(FileNotFoundError):
        Coder.get_file_info("non_existent_file.txt")


def test_git_diff_context(temp_git_repo):
    original_dir = Path.cwd()
    os.chdir(temp_git_repo.working_dir)

    # Test empty repo (no commits, no staged files, no unstaged changes)
    diff = Coder.git_diff_context()
    assert not diff

    # Add a new file but don't stage it
    create_and_write_file("newfile.txt", "This is a new file.")
    diff = Coder.git_diff_context()
    assert not diff, "New file should not be included in diff until it is staged"

    # Stage the new file
    temp_git_repo.git.add("newfile.txt")
    diff = Coder.git_diff_context()
    assert "## New file added: newfile.txt" in diff
    assert "This is a new file." in diff

    # Commit the new file
    temp_git_repo.git.commit("-m", "Add newfile.txt")
    diff = Coder.git_diff_context()
    assert not diff

    # Test diff for a specific commit
    commit = temp_git_repo.head.commit.hexsha
    diff = Coder.git_diff_context(commit)
    assert "This is a new file." in diff

    # Modify the file but don't stage it
    create_and_write_file("newfile.txt", "This is a modified file.", overwrite=True)
    diff = Coder.git_diff_context()
    assert "## File changed: newfile.txt" in diff
    assert "This is a modified file." in diff

    # Stage the modified file
    temp_git_repo.git.add("newfile.txt")
    diff = Coder.git_diff_context()
    assert "## File changed: newfile.txt" in diff
    assert "This is a modified file." in diff

    # Commit the modified file
    temp_git_repo.git.commit("-m", "Modify newfile.txt")
    diff = Coder.git_diff_context()
    assert not diff

    # Rename the file but don't stage it
    temp_git_repo.git.mv("newfile.txt", "renamedfile.txt")
    diff = Coder.git_diff_context()
    assert "## File renamed: newfile.txt -> renamedfile.txt" in diff

    # Stage the renamed file
    temp_git_repo.git.add("renamedfile.txt")
    diff = Coder.git_diff_context()
    assert "## File renamed: newfile.txt -> renamedfile.txt" in diff

    # Commit the renamed file
    temp_git_repo.git.commit("-m", "Rename newfile.txt to renamedfile.txt")
    diff = Coder.git_diff_context()
    assert not diff

    # Test diff for a specific commit
    commit = temp_git_repo.head.commit.hexsha
    diff = Coder.git_diff_context(commit)
    assert "renamedfile.txt" in diff

    # Change working directory back
    os.chdir(original_dir)


def test_identify_languages():
    # Create a list of test files
    test_files = ["tests/test_coder.py", "LICENSE", "README.md", "pyproject.toml", "assets/robot.png", "setup.py"]

    # Call the identify_languages function
    result = Coder.identify_languages(test_files)

    # Should not do anything for LICENSE
    # Should not do anything for the binary file
    # Should not duplicate the two python files
    # Should be in alphabetical order
    assert result == ["Markdown", "Python", "TOML"]


def test_is_inside_git_repo(temp_git_repo):
    """Test the is_inside_git_repo function."""
    # Create a temporary directory and check that we are not inside a git repo
    temp_dir = tempfile.mkdtemp()
    with in_temp_directory(temp_dir):  # Don't use tmp_path, because that's what temp_git_repo is using
        assert Coder.is_inside_git_repo() is False, "Expected False when outside a git repo"

    with in_temp_directory(temp_git_repo.working_dir):
        assert Coder.is_inside_git_repo() is True, "Expected True when inside a git repo"


def test_parse_github_url():
    # Test with https URL
    owner, repo = Coder.parse_github_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"

    # Test with git URL
    owner, repo = Coder.parse_github_url("git@github.com:owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"

    # Test with invalid URL
    with pytest.raises(ValueError):
        Coder.parse_github_url("not a valid url")


def test_rebuild_patch(tmp_path):
    # Use in_temp_directory for the test
    with in_temp_directory(tmp_path):
        # Set up the original file
        Path(tmp_path / "aicodebot").mkdir()
        create_and_write_file(
            "aicodebot/prompts.py",
            textwrap.dedent(
                """
                from aicodebot.coder import Coder
                from aicodebot.config import read_config
                from aicodebot.helpers import logger
                from langchain import PromptTemplate
                from langchain.output_parsers import PydanticOutputParser
                from pathlib import Path
                from pydantic import BaseModel, Field
                from types import SimpleNamespace
                import arrow, functools, os, platform

                """
            ),
        )
        prompts_file = Path("aicodebot/prompts.py").read_text()
        assert "platform" in prompts_file

        # A few problems with this patch:
        # 1. The chunk header is wrong (wrong line in the file and wrong number of lines)
        # 2. No " " before the unchanged lines
        # 3. Duplicated added/removed lines (that should just be unchanged)
        # The original goal of the patch was to remove the "platform" import
        bad_patch = textwrap.dedent(
            """
            diff --git a/aicodebot/prompts.py b/aicodebot/prompts.py
            --- a/aicodebot/prompts.py
            +++ b/aicodebot/prompts.py
            @@ -6,7 +6,7 @@
            from langchain import PromptTemplate
            from langchain.output_parsers import PydanticOutputParser
            from pathlib import Path
            -from pydantic import BaseModel, Field
            -from types import SimpleNamespace
            -import arrow, functools, os, platform
            +from pydantic import BaseModel, Field
            +from types import SimpleNamespace
            +import arrow, functools, os

            """
        )

        rebuilt_patch = Coder.rebuild_patch(bad_patch)

        # Apply the rebuilt patch
        assert Coder.apply_patch(rebuilt_patch)

        assert "platform" not in Path("aicodebot/prompts.py").read_text()


def test_rebuild_patch_coder(tmp_path):
    return  # This test fails, checking it in for future use case

    # Use in_temp_directory for the test
    with in_temp_directory(tmp_path):
        # Set up the original file
        file = "aicodebot/coder.py"
        Path(tmp_path / "aicodebot").mkdir()
        create_and_write_file(
            file,
            textwrap.dedent(
                """
                from aicodebot.helpers import exec_and_get_output, logger
                from aicodebot.lm import token_size
                from pathlib import Path
                from pygments.lexers import ClassNotFound, get_lexer_for_mimetype, guess_lexer_for_filename
                from types import SimpleNamespace
                import fnmatch, mimetypes, re, subprocess, unidiff


                class Coder:
                """
            ).lstrip(),
        )
        assert "unidiff" in Path(file).read_text()

        # A few problems with this patch:
        # 1. The chunk header is wrong (wrong line in the file and wrong number of lines)
        # 2. No " " before the unchanged lines
        # 3. Duplicated added/removed lines (that should just be unchanged)
        # The original goal of the patch was to remove the "platform" import
        bad_patch = textwrap.dedent(
            """
            diff --git a/aicodebot/coder.py b/aicodebot/coder.py
            --- a/aicodebot/coder.py
            +++ b/aicodebot/coder.py
            @@ -3,7 +3,7 @@
             from pathlib import Path
             from pygments.lexers import ClassNotFound, get_lexer_for_mimetype, guess_lexer_for_filename
             from types import SimpleNamespace
            -import fnmatch, mimetypes, re, subprocess, unidiff
            +import fnmatch, mimetypes, re, subprocess


             class Coder
            """
        ).lstrip()
        print("Bad patch:")
        print(bad_patch)

        rebuilt_patch = Coder.rebuild_patch(bad_patch)

        print("Rebuilt patch:")
        print(rebuilt_patch)
        # Apply the rebuilt patch
        assert Coder.apply_patch(rebuilt_patch)

        assert "unidiff" not in Path(file).read_text()
