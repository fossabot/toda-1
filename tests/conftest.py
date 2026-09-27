"""Pytest fixtures for toda tests."""

import os
import shutil
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def manifest_file(temp_dir):
    """Create a factory for manifest files."""
    created_files = []

    def _create_manifest(content, filename="MANIFEST"):
        path = os.path.join(temp_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        created_files.append(path)
        return path

    yield _create_manifest


@pytest.fixture
def source_file(temp_dir):
    """Create a factory for source files to be symlinked."""

    def _create_source(content="test content", filename="source.txt"):
        path = os.path.join(temp_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        return path

    yield _create_source


@pytest.fixture
def source_dir(temp_dir):
    """Create a factory for source directories with files."""

    def _create_source_dir(dirname="srcdir", files=None):
        if files is None:
            files = {"file1.txt": "content1", "file2.txt": "content2"}
        dirpath = os.path.join(temp_dir, dirname)
        os.makedirs(dirpath, exist_ok=True)
        for fname, content in files.items():
            with open(os.path.join(dirpath, fname), "w") as f:
                f.write(content)
        return dirpath

    yield _create_source_dir


@pytest.fixture
def mock_args():
    """Create mock arguments object."""

    class MockArgs:
        def __init__(self):
            self.action = "inspect"
            self.dry_run = False
            self.manifest = "./MANIFEST"
            self.force = False
            self.strict = False
            self.verbose = 0
            self.dir = None
            self.no_preflight = True  # Skip preflight in tests
            self.format = "text"
            self.color = "never"
            self.only_changed = False
            self.section = []

    return MockArgs()
