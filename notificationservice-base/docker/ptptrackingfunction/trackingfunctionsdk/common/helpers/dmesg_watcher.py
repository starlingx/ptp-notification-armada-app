#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
from pygtail import Pygtail
from typing import List
from abc import ABC, abstractmethod

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers.gnss_monitor import Observer

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class DmesgSubject(ABC):
    @abstractmethod
    def attach(self, observer: Observer) -> None:
        pass

    @abstractmethod
    def detach(self, observer: Observer) -> None:
        pass

    @abstractmethod
    def notify(self) -> None:
        pass


class DmesgWatcher(DmesgSubject, ABC):
    _observers: List[Observer] = []
    _checklist = []
    _matched_line = ""

    def __init__(self, dmesg_log_file="/logs/kern.log"):
        self.dmesg_log_file = dmesg_log_file

    def parse_dmesg_event(self, dmesg_entry) -> None:
        for observer in self._observers:
            if observer.dmesg_values_to_check['pin'] in dmesg_entry \
                    and observer.dmesg_values_to_check['pci_addr'] in dmesg_entry:
                matched_line = dmesg_entry
                self.notify(observer, matched_line)

    def run_watcher(self) -> None:
        """
        This is intended to be run as a separate thread to follow the log file for events.
        There is currently no support in the NIC device drivers for udev events that
        would avoid polling/monitoring.
        """
        while True:
            for line in Pygtail(self.dmesg_log_file, offset_file="./kern.offset"):
                self.parse_dmesg_event(line)

    def attach(self, observer: Observer) -> None:
        LOG.info("DmesgWatcher: Attached an observer.")
        self._observers.append(observer)

    def notify(self, observer, matched_line) -> None:
        LOG.info("DmesgWatcher: Notifying observers.")
        observer.update(self, matched_line)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)
        LOG.debug("Removed an observer.")

