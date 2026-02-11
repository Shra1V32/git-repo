# Copyright (C) 2026 The Android Open Source Project
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

"""Unittests for the subcmds/init.py module (home directory check)."""

import os
import sys
import unittest
from unittest import mock

from subcmds import init


class InitHomeCheck(unittest.TestCase):
    """Check home directory warning in repo init."""

    def setUp(self):
        self.cmd = init.Init()
        self.cmd.manifest = mock.MagicMock()
        self.cmd.git_event_log = mock.MagicMock()
        self.cmd.client = mock.MagicMock()
        self.cmd.client.globalConfig = mock.MagicMock()

    @mock.patch("os.isatty")
    @mock.patch("os.getcwd")
    @mock.patch("os.path.expanduser")
    @mock.patch("os.path.realpath")
    @mock.patch("sys.stdin.readline")
    @mock.patch("wrapper.Wrapper")
    @mock.patch("git_command.git_require")
    @mock.patch("subcmds.init.logger.warning")
    def test_home_dir_abort(self, mock_warn, mock_git_require, mock_wrapper, mock_readline, mock_realpath, mock_expanduser, mock_getcwd, mock_isatty):
        """Test aborting when init-ing in home directory."""
        mock_isatty.return_value = True
        mock_getcwd.return_value = "/home/user"
        mock_expanduser.return_value = "/home/user"
        mock_realpath.side_effect = lambda x: x
        mock_readline.return_value = "n\n"

        opt, args = self.cmd.OptionParser.parse_args([])
        opt.quiet = False

        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stderr", new_callable=mock.MagicMock) as mock_stderr:
                self.cmd.Execute(opt, args)
        
        self.assertEqual(cm.exception.code, 1)
        # Check if the warning was logged
        mock_warn.assert_called_once()
        self.assertIn("initializing repo in your home directory", mock_warn.call_args[0][0])

    @mock.patch("os.isatty")
    @mock.patch("os.getcwd")
    @mock.patch("os.path.expanduser")
    @mock.patch("os.path.realpath")
    @mock.patch("sys.stdin.readline")
    @mock.patch("wrapper.Wrapper")
    @mock.patch("git_command.git_require")
    @mock.patch.object(init.Init, "_SyncManifest")
    @mock.patch("subcmds.init.logger.warning")
    def test_home_dir_continue(self, mock_warn, mock_sync_manifest, mock_git_require, mock_wrapper, mock_readline, mock_realpath, mock_expanduser, mock_getcwd, mock_isatty):
        """Test continuing when init-ing in home directory."""
        mock_isatty.return_value = True
        mock_getcwd.return_value = "/home/user"
        mock_expanduser.return_value = "/home/user"
        mock_realpath.side_effect = lambda x: x
        mock_readline.return_value = "y\n"
        
        # Mocking Wrapper and other things to avoid actual execution
        mock_wrapper_inst = mock_wrapper.return_value
        mock_wrapper_inst.Requirements.from_dir.return_value.get_hard_ver.return_value = (1, 0)
        mock_wrapper_inst.Requirements.from_dir.return_value.get_soft_ver.return_value = (1, 0)

        opt, args = self.cmd.OptionParser.parse_args([])
        opt.quiet = False
        opt.worktree = False

        # We need to mock more to let it finish Execute
        self.cmd.manifest.repoProject.GetRemote.return_value = mock.MagicMock()
        self.cmd.manifest.manifestProject.Exists = False

        with mock.patch("sys.stderr", new_callable=mock.MagicMock) as mock_stderr:
             with mock.patch("sys.stdout", new_callable=mock.MagicMock) as mock_stdout:
                self.cmd.Execute(opt, args)

        # Check if the warning was logged
        mock_warn.assert_called_once()
        self.assertIn("initializing repo in your home directory", mock_warn.call_args[0][0])
        mock_sync_manifest.assert_called_once()

    @mock.patch("os.isatty")
    @mock.patch("os.getcwd")
    @mock.patch("os.path.expanduser")
    @mock.patch("os.path.realpath")
    @mock.patch("wrapper.Wrapper")
    @mock.patch("git_command.git_require")
    @mock.patch.object(init.Init, "_SyncManifest")
    @mock.patch("subcmds.init.logger.warning")
    def test_non_home_dir(self, mock_warn, mock_sync_manifest, mock_git_require, mock_wrapper, mock_realpath, mock_expanduser, mock_getcwd, mock_isatty):
        """Test no warning when not in home directory."""
        mock_isatty.return_value = True
        mock_getcwd.return_value = "/home/user/project"
        mock_expanduser.return_value = "/home/user"
        mock_realpath.side_effect = lambda x: x
        
        mock_wrapper_inst = mock_wrapper.return_value
        mock_wrapper_inst.Requirements.from_dir.return_value.get_hard_ver.return_value = (1, 0)
        mock_wrapper_inst.Requirements.from_dir.return_value.get_soft_ver.return_value = (1, 0)

        opt, args = self.cmd.OptionParser.parse_args([])
        opt.quiet = False
        opt.worktree = False
        self.cmd.manifest.manifestProject.Exists = False

        with mock.patch("sys.stderr", new_callable=mock.MagicMock) as mock_stderr:
            with mock.patch("sys.stdout", new_callable=mock.MagicMock):
                self.cmd.Execute(opt, args)

        # Check if the warning was NOT logged
        mock_warn.assert_not_called()
        mock_sync_manifest.assert_called_once()

    @mock.patch("os.isatty")
    @mock.patch("os.getcwd")
    @mock.patch("os.path.expanduser")
    @mock.patch("os.path.realpath")
    @mock.patch("wrapper.Wrapper")
    @mock.patch("git_command.git_require")
    @mock.patch.object(init.Init, "_SyncManifest")
    @mock.patch("subcmds.init.logger.warning")
    def test_quiet_mode(self, mock_warn, mock_sync_manifest, mock_git_require, mock_wrapper, mock_realpath, mock_expanduser, mock_getcwd, mock_isatty):
        """Test no warning in quiet mode."""
        mock_isatty.return_value = True
        mock_getcwd.return_value = "/home/user"
        mock_expanduser.return_value = "/home/user"
        mock_realpath.side_effect = lambda x: x
        
        mock_wrapper_inst = mock_wrapper.return_value
        mock_wrapper_inst.Requirements.from_dir.return_value.get_hard_ver.return_value = (1, 0)
        mock_wrapper_inst.Requirements.from_dir.return_value.get_soft_ver.return_value = (1, 0)

        opt, args = self.cmd.OptionParser.parse_args([])
        opt.quiet = True
        opt.worktree = False
        self.cmd.manifest.manifestProject.Exists = False

        with mock.patch("sys.stderr", new_callable=mock.MagicMock) as mock_stderr:
            self.cmd.Execute(opt, args)

        # Check if the warning was NOT logged
        mock_warn.assert_not_called()
        mock_sync_manifest.assert_called_once()
