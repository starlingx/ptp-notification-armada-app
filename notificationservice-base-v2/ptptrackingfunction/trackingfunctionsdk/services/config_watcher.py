#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class ConfigFileWatcher:
    """Monitor PTP configuration directory for changes and trigger reload"""

    def __init__(self, watch_path, callback, debounce_seconds=2):
        self.watch_path = watch_path
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.observer = None
        self._last_event_time = 0
        self._debounce_timer = None
        self._lock = threading.Lock()

    def start(self):
        """Start watching the configuration directory"""
        event_handler = _ConfigChangeHandler(self._on_config_change)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_path, recursive=False)
        self.observer.start()
        LOG.info("Config watcher started monitoring: %s", self.watch_path)

    def stop(self):
        """Stop watching the configuration directory"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            LOG.info("Config watcher stopped")

    def _on_config_change(self):
        """Handle config change with debouncing"""
        with self._lock:
            self._last_event_time = time.time()
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                self.debounce_seconds, self._trigger_callback)
            self._debounce_timer.start()

    def _trigger_callback(self):
        """Trigger callback after debounce period"""
        try:
            LOG.info("Config change detected, triggering reload")
            self.callback()
        except Exception as e:
            LOG.error("Error in config change callback: %s", e)


class _ConfigChangeHandler(FileSystemEventHandler):
    """Handle file system events for config files"""

    def __init__(self, on_change_callback):
        self.on_change_callback = on_change_callback

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.conf'):
            LOG.info("Config file created: %s", event.src_path)
            self.on_change_callback()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.conf'):
            LOG.info("Config file modified: %s", event.src_path)
            self.on_change_callback()

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.conf'):
            LOG.info("Config file deleted: %s", event.src_path)
            self.on_change_callback()
