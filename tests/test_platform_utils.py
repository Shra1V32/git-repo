# Copyright (C) 2021 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unittests for the platform_utils.py module."""

from pathlib import Path

import pytest

import platform_utils


def test_remove_missing_ok(tmp_path: Path) -> None:
    """Check missing_ok handling."""
    path = tmp_path / "test"

    # Should not fail.
    platform_utils.remove(path, missing_ok=True)

    # Should fail.
    with pytest.raises(OSError):
        platform_utils.remove(path)
    with pytest.raises(OSError):
        platform_utils.remove(path, missing_ok=False)

    # Should not fail if it exists.
    path.touch()
    platform_utils.remove(path, missing_ok=True)
    assert not path.exists()

    path.touch()
    platform_utils.remove(path)
    assert not path.exists()

    path.touch()
    platform_utils.remove(path, missing_ok=False)
    assert not path.exists()


def test_removedirs_nonexistent(tmp_path: Path) -> None:
    """removedirs should silently succeed on nonexistent paths."""
    platform_utils.removedirs(tmp_path / "does-not-exist")


def test_removedirs_symlink(tmp_path: Path) -> None:
    """removedirs should remove a symlink."""
    link = tmp_path / "link"
    link.symlink_to("target")
    platform_utils.removedirs(link)
    assert not link.exists()


def test_removedirs_empty_dir(tmp_path: Path) -> None:
    """removedirs should remove an empty directory."""
    d = tmp_path / "empty"
    d.mkdir()
    platform_utils.removedirs(d)
    assert not d.exists()


def test_removedirs_nested_empty_dirs(tmp_path: Path) -> None:
    """removedirs should remove nested empty directories."""
    d = tmp_path / "a" / "b" / "c"
    d.mkdir(parents=True)
    platform_utils.removedirs(tmp_path / "a")
    assert not (tmp_path / "a").exists()


def test_removedirs_symlinks_inside_dir(tmp_path: Path) -> None:
    """removedirs should remove symlinks inside a directory."""
    d = tmp_path / "dir"
    d.mkdir()
    (d / "link1").symlink_to("target1")
    (d / "link2").symlink_to("target2")
    platform_utils.removedirs(d)
    assert not d.exists()


def test_removedirs_preserves_user_files(tmp_path: Path) -> None:
    """removedirs should not delete regular files or their parent dirs."""
    d = tmp_path / "dir"
    d.mkdir()
    (d / "link").symlink_to("target")
    (d / "user-file.txt").write_text("keep me")
    platform_utils.removedirs(d)
    assert d.exists()
    assert not (d / "link").exists()
    assert (d / "user-file.txt").read_text() == "keep me"


def test_removedirs_deep_nested_with_symlinks(tmp_path: Path) -> None:
    """removedirs should handle deep nesting: sub/dir/target."""
    d = tmp_path / "sub" / "dir"
    d.mkdir(parents=True)
    (d / "link").symlink_to("target")
    platform_utils.removedirs(tmp_path / "sub")
    assert not (tmp_path / "sub").exists()


def test_removedirs_regular_file_noop(tmp_path: Path) -> None:
    """removedirs should not delete a regular file."""
    f = tmp_path / "file.txt"
    f.write_text("data")
    platform_utils.removedirs(f)
    assert f.exists()
