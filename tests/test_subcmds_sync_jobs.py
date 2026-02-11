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

"""Unittests for the subcmds/sync.py module (jobs limit)."""

import os
import unittest
from unittest import mock

from subcmds import sync


class SyncJobsLimit(unittest.TestCase):
    """Check jobs limit in repo sync."""

    def setUp(self):
        self.cmd = sync.Sync()

    @mock.patch("subcmds.sync._rlimit_nofile")
    @mock.patch("os.cpu_count")
    def test_jobs_limit(self, mock_cpu_count, mock_rlimit):
        """Test that jobs are limited to 24."""
        mock_cpu_count.return_value = 64
        mock_rlimit.return_value = (1024, 1024)

        mp = mock.MagicMock()
        mp.manifest.default.sync_j = None
        mp.manifest.default.sync_j_max = None

        opt, args = self.cmd.OptionParser.parse_args(["--jobs=50"])
        self.cmd.ValidateOptions(opt, args)
        
        with mock.patch("subcmds.sync.logger.warning") as mock_warning:
            self.cmd._ValidateOptionsWithManifest(opt, mp)
            self.assertEqual(opt.jobs, 24)
            self.assertEqual(opt.jobs_network, 24)
            self.assertEqual(opt.jobs_checkout, 24)
            
            # Check if warning was issued
            found = False
            for call in mock_warning.call_args_list:
                msg = call[0][0]
                if "is limited to %d" in msg:
                    found = True
                    break
            self.assertTrue(found, f"Warning not found in calls: {mock_warning.call_args_list}")

    @mock.patch("subcmds.sync._rlimit_nofile")
    @mock.patch("os.cpu_count")
    def test_jobs_limit_manifest(self, mock_cpu_count, mock_rlimit):
        """Test that jobs are limited to 24 even if manifest says more."""
        mock_cpu_count.return_value = 64
        mock_rlimit.return_value = (1024, 1024)

        mp = mock.MagicMock()
        mp.manifest.default.sync_j = 100
        mp.manifest.default.sync_j_max = None

        opt, args = self.cmd.OptionParser.parse_args([])
        self.cmd.ValidateOptions(opt, args)
        
        with mock.patch("subcmds.sync.logger.warning") as mock_warning:
            self.cmd._ValidateOptionsWithManifest(opt, mp)
            self.assertEqual(opt.jobs, 24)
            
            # Check if warning was issued
            found = False
            for call in mock_warning.call_args_list:
                msg = call[0][0]
                if "is limited to %d" in msg:
                    found = True
                    break
            self.assertTrue(found, f"Warning not found in calls: {mock_warning.call_args_list}")

    @mock.patch("subcmds.sync._rlimit_nofile")
    @mock.patch("os.cpu_count")
    def test_jobs_limit_under(self, mock_cpu_count, mock_rlimit):
        """Test that jobs are NOT limited if under 24."""
        mock_cpu_count.return_value = 64
        mock_rlimit.return_value = (1024, 1024)

        mp = mock.MagicMock()
        mp.manifest.default.sync_j = None
        mp.manifest.default.sync_j_max = None

        opt, args = self.cmd.OptionParser.parse_args(["--jobs=10"])
        self.cmd.ValidateOptions(opt, args)
        
        with mock.patch("subcmds.sync.logger.warning") as mock_warning:
            self.cmd._ValidateOptionsWithManifest(opt, mp)
            self.assertEqual(opt.jobs, 10)
            
            # Check if NO limit warning was issued
            warning_calls = [call for call in mock_warning.call_args_list if "is limited to 24" in call[0][0]]
            self.assertEqual(len(warning_calls), 0)
