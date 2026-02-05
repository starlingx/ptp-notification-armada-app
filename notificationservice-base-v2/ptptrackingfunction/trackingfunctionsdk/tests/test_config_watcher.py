#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import tempfile
import time
import unittest
from mock import Mock
from trackingfunctionsdk.services.config_watcher import ConfigFileWatcher


class TestConfigFileWatcher(unittest.TestCase):
    """Test cases for ConfigFileWatcher"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.callback_mock = Mock()
        self.watcher = None

    def tearDown(self):
        """Clean up test fixtures"""
        if self.watcher:
            self.watcher.stop()
        # Clean up test directory
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)

    def test_watcher_initialization(self):
        """Test watcher can be initialized"""
        watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=1
        )
        self.assertEqual(watcher.watch_path, self.test_dir)
        self.assertEqual(watcher.callback, self.callback_mock)
        self.assertEqual(watcher.debounce_seconds, 1)

    def test_watcher_start_stop(self):
        """Test watcher can start and stop"""
        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=1
        )
        self.watcher.start()
        self.assertIsNotNone(self.watcher.observer)
        self.assertTrue(self.watcher.observer.is_alive())

        self.watcher.stop()
        time.sleep(0.5)
        self.assertFalse(self.watcher.observer.is_alive())

    def test_file_created_triggers_callback(self):
        """Test that creating a .conf file triggers callback"""
        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)  # Let watcher initialize

        # Create a config file
        test_file = os.path.join(self.test_dir, 'test.conf')
        with open(test_file, 'w') as f:
            f.write('test')

        # Wait for debounce + processing
        time.sleep(1)

        self.callback_mock.assert_called_once()

    def test_file_modified_triggers_callback(self):
        """Test that modifying a .conf file triggers callback"""
        # Create file first
        test_file = os.path.join(self.test_dir, 'test.conf')
        with open(test_file, 'w') as f:
            f.write('initial')

        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)

        # Modify the file
        with open(test_file, 'w') as f:
            f.write('modified')

        time.sleep(1)

        self.callback_mock.assert_called_once()

    def test_file_deleted_triggers_callback(self):
        """Test that deleting a .conf file triggers callback"""
        # Create file first
        test_file = os.path.join(self.test_dir, 'test.conf')
        with open(test_file, 'w') as f:
            f.write('test')

        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)

        # Delete the file
        os.remove(test_file)

        time.sleep(1)

        self.callback_mock.assert_called_once()

    def test_non_conf_file_ignored(self):
        """Test that non-.conf files are ignored"""
        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)

        # Create a non-config file
        test_file = os.path.join(self.test_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')

        time.sleep(1)

        self.callback_mock.assert_not_called()

    def test_debouncing_multiple_changes(self):
        """Test that multiple rapid changes result in single callback"""
        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=1
        )
        self.watcher.start()
        time.sleep(0.2)

        # Create multiple files rapidly
        for i in range(3):
            test_file = os.path.join(self.test_dir, f'test{i}.conf')
            with open(test_file, 'w') as f:
                f.write(f'test{i}')
            time.sleep(0.1)

        # Wait for debounce
        time.sleep(1.5)

        # Should only be called once due to debouncing
        self.assertEqual(self.callback_mock.call_count, 1)

    def test_directory_changes_ignored(self):
        """Test that directory creation/deletion is ignored"""
        self.watcher = ConfigFileWatcher(
            self.test_dir,
            self.callback_mock,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)

        # Create a subdirectory
        subdir = os.path.join(self.test_dir, 'subdir')
        os.mkdir(subdir)

        time.sleep(1)

        self.callback_mock.assert_not_called()

        # Clean up
        os.rmdir(subdir)

    def test_callback_exception_handling(self):
        """Test that exceptions in callback don't crash watcher"""
        def failing_callback():
            raise RuntimeError("Test exception")

        self.watcher = ConfigFileWatcher(
            self.test_dir,
            failing_callback,
            debounce_seconds=0.5
        )
        self.watcher.start()
        time.sleep(0.2)

        # Create a file - should not crash despite callback exception
        test_file = os.path.join(self.test_dir, 'test.conf')
        with open(test_file, 'w') as f:
            f.write('test')

        time.sleep(1)

        # Watcher should still be running
        self.assertTrue(self.watcher.observer.is_alive())


if __name__ == '__main__':
    unittest.main()
