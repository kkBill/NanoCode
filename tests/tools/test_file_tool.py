"""Tests for ReadFile and WriteFile tools."""

import pytest

from nanocode.tools.file_tool import ReadFile, WriteFile


@pytest.fixture
def read_file():
    return ReadFile()


@pytest.fixture
def write_file():
    return WriteFile()


@pytest.fixture
def mock_work_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("nanocode.tools.file_tool.WORK_DIR", tmp_path)
    return tmp_path


class TestReadFile:
    def test_read_existing_file(self, read_file, mock_work_dir):
        (mock_work_dir / "test.txt").write_text("hello world", encoding="utf-8")
        result = read_file.execute(filename="test.txt")
        assert result == "hello world"

    def test_read_empty_file(self, read_file, mock_work_dir):
        (mock_work_dir / "empty.txt").write_text("", encoding="utf-8")
        result = read_file.execute(filename="empty.txt")
        assert result == "(empty file)"

    def test_read_nonexistent_file(self, read_file, mock_work_dir):
        result = read_file.execute(filename="nonexistent.txt")
        assert "Error" in result

    def test_read_path_traversal(self, read_file, mock_work_dir):
        result = read_file.execute(filename="../../etc/passwd")
        assert "Error" in result

    def test_read_large_file_truncated(self, read_file, mock_work_dir):
        large_content = "x" * 60000
        (mock_work_dir / "large.txt").write_text(large_content, encoding="utf-8")
        result = read_file.execute(filename="large.txt")
        assert len(result) == 50000


class TestWriteFile:
    def test_write_new_file(self, write_file, mock_work_dir):
        result = write_file.execute(filename="out.txt", content="data")
        assert result == "File written successfully"
        assert (mock_work_dir / "out.txt").read_text(encoding="utf-8") == "data"

    def test_write_overwrite_existing(self, write_file, mock_work_dir):
        (mock_work_dir / "existing.txt").write_text("old", encoding="utf-8")
        result = write_file.execute(filename="existing.txt", content="new")
        assert result == "File written successfully"
        assert (mock_work_dir / "existing.txt").read_text(encoding="utf-8") == "new"

    def test_write_path_traversal(self, write_file, mock_work_dir):
        result = write_file.execute(filename="../../etc/passwd", content="hack")
        assert "Error" in result

    def test_write_empty_content(self, write_file, mock_work_dir):
        result = write_file.execute(filename="empty.txt", content="")
        assert result == "File written successfully"
        assert (mock_work_dir / "empty.txt").read_text(encoding="utf-8") == ""
