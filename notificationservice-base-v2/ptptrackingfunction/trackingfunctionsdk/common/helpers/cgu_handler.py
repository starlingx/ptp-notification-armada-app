#
# Copyright (c) 2022-2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import os
import re

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper
from pynetlink import NetlinkDPLL, DpllPins, NetlinkException
from pynetlink import DeviceType, PinState, PinDirection, LockStatus

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

class CguHandler:
    """Class that implements methods to access CGU information"""

    def __init__(self, config_file, nmea_serialport=None, pci_addr=None,
                 cgu_path=None, clock_id=None):
        self._config_file = config_file
        self._nmea_serialport = nmea_serialport
        self._pci_addr = pci_addr
        self._cgu_path = cgu_path
        self._clock_id = clock_id
        self._pins = DpllPins()
        self._dpll = NetlinkDPLL()
        self._is_serial_module = False

        # Try to get clock-id
        try:
            if self._nmea_serialport and "tty" in self._nmea_serialport:
                self._is_serial_module = True

            LOG.debug("Searching for clock id")
            if self._clock_id is None:
                self._get_clock_id()
        except Exception as err:
            LOG.error(err)

    def _get_gnss_nmea_serialport_from_ts2phc_config(self):
        """Read a ts2phc config file and return the ts2phc.nmea_serialport"""

        try:
            with open(self._config_file, 'r', encoding='utf-8') as infile:
                for line in infile:
                    if constants.NMEA_SERIALPORT in line:
                        nmea_serialport = line.split(' ')[1].strip('\n')
                        break
            self._nmea_serialport = nmea_serialport
            self._is_serial_module = "tty" in nmea_serialport
            return
        except (FileNotFoundError, PermissionError) as err:
            LOG.error(err)
            raise

    def _convert_nmea_serialport_to_pci_addr(self):
        """Parse the nmea_serialport value into a PCI address so that we can
        later find the cgu.
        """

        # Validate if NMEA serial port is set
        if self._nmea_serialport is None:
            self._get_gnss_nmea_serialport_from_ts2phc_config()

        # Remove the /dev portion of the path
        nmea_serialport = self._nmea_serialport.split('/')[2]
        LOG.debug('Looking for nmea_serialport value: %s', nmea_serialport)
        try:
            with open(constants.UEVENT_FILE.format(self._nmea_serialport), 'r',
                      encoding='utf-8') as file:
                for line in file:
                    if constants.PCI_SLOT_NAME in line:
                        # Get the portion after the '=' sign
                        pci_addr = re.split('=', line)[1].strip('\n')
                        LOG.debug("Found with PCI addr: %s", pci_addr)
                        break
        except (FileNotFoundError, PermissionError) as err:
            LOG.error(err)
            raise

        self._pci_addr = pci_addr

    def _get_clock_id_by_pci_addr(self):
        """Get clock id by network card pci address"""

        # Validate if PCI address is set
        if self._pci_addr is None:
            self._convert_nmea_serialport_to_pci_addr()

        # Validate if PCI address have more than one network device
        net_devices = os.listdir(constants.SYS_DEV_NET.format(self._pci_addr))

        if len(net_devices) != 1:
            LOG.error("Error during PCI address translation. Net_devices = %s",
                      net_devices)
            return

        try:
            with open(constants.SYS_DEV_NET_ADDR.format(self._pci_addr,
                                                        net_devices[0]),
                      'r', encoding='utf-8') as file:
                phys_switch_id = file.read()
        except (FileNotFoundError, PermissionError) as err:
            LOG.error(err)
            raise

        self._clock_id = int(phys_switch_id.strip(), 16)
        LOG.info("Mac Address %s translated to clock id %s", phys_switch_id,
                 self._clock_id)

    def _get_clock_id_for_tty_dev(self):
        """Determine the clock_id based on ZL 3073 device"""
        try:
            with open(constants.ZL_MODULE_PATH_CLKID, 'r', encoding='utf-8') \
                 as infile:
                clock_id = infile.read()
            if not clock_id:
                raise ValueError("Clock ID is empty")

        except (FileNotFoundError, PermissionError, ValueError) as err:
            LOG.error(err)
            raise
        self._clock_id = int(clock_id.replace("\n",""))
        LOG.info("Module Address %s translated to clock id %s",
                 self._nmea_serialport,
                 self._clock_id)

    def _get_clock_id(self):
        """Get clock_id for the device"""
        if self._nmea_serialport is None:
            self._get_gnss_nmea_serialport_from_ts2phc_config()

        if self._is_serial_module:
            self._get_clock_id_for_tty_dev()
        else:
            self._get_clock_id_by_pci_addr()

    def _read_all_devices(self):
        """Read CGU information using netlink interface. Consider that there is
        no information saved from the last read.

        NetlinkException: error when Netlink wasn't initialized, or no info
            is read.
        """
        try:
            get_pins = self._dpll.get_all_pins()\
                .filter_by_device_clock_id(self._clock_id)\
                .filter_by_pin_state(PinState.CONNECTED)\
                .filter_by_pin_direction(PinDirection.INPUT)
            if len(get_pins) == 0:
                get_pins = None
                LOG.error("No pins found for clock id")

        except NetlinkException as err:
            get_pins = None
            LOG.error(err)

        self._pins = get_pins

    def _read_only_filtered(self):
        """Read CGU information using netlink interface. Consider the last used
        pins to save time.

        Raises:
            NetlinkException: error when Netlink wasn't initialized, or no info
            is read.
        """
        try:
            new_pins = DpllPins()

            # Create a set of pins to read
            pin_ids = {x.pin_id for x in self._pins}

            for pin_id in pin_ids:
                # Get pin (for each pin_id) and filter by device_id.
                aux = self._dpll.get_pins_by_id(pin_id)
                if not aux:
                    LOG.debug("Saved pin isn't accessible anymore. Forcing "
                              "full reading.")
                    return self._read_all_devices()
                dev_ids = {x.dev_id for x in self._pins if x.pin_id == pin_id}
                filtered_pins = {x for x in aux if x.dev_id in dev_ids}

                # If any pin is not connected, force full reading
                if len(filtered_pins) == 0 or \
                    any(x.pin_state != PinState.CONNECTED
                        for x in filtered_pins):
                    LOG.debug("Saved pin is not connected anymore. Forcing "
                              "full reading.")
                    return self._read_all_devices()

                new_pins.update(filtered_pins)

        except NetlinkException as err:
            new_pins = None
            LOG.error(err)

        self._pins = new_pins

    def read_cgu(self):
        """Read the CGU information using netlink interface."""
        if self._dpll is None:
            raise NetlinkException("Netlink family not initialized.")
        if self._clock_id is None:
            raise NetlinkException("Isn't possible to obtain the status of "
                                   "the device. Clock ID is None.")

        # To avoid unnecessary reads and save time, pins used by the device
        # will be saved and read separately.
        # Pins used will be saved during the reading.
        if not self._pins or len(self._pins) == 0:
            self._read_all_devices()
        else:
            self._read_only_filtered()

    def _get_status(self, device_type: DeviceType) -> str:
        """Get the device status from Netlink DPLL dictionary

        Args:
            device_type (DeviceType): Type of the device (eec or pps)

        Returns:
            str: device status
        """
        if not self._pins or len(self._pins) == 0:
            return LockStatus.UNDEFINED.value

        pin = self._pins.filter_by_device_type(device_type)
        if len(pin) == 0:
            return LockStatus.UNDEFINED.value

        return next(iter(pin)).lock_status.value

    def get_eec_status(self) -> str:
        """Get EEC status from Netlink DPLL dictionary

        Returns:
            str: EEC status
        """
        return self._get_status(DeviceType.EEC)

    def get_pps_status(self) -> str:
        """Get PPS status from Netlink DPLL dictionary

        Returns:
            str: PPS status
        """
        return self._get_status(DeviceType.PPS)

    def _get_current_reference(self, device_type: DeviceType) -> str:
        """Get the device status from Netlink DPLL dictionary

        Args:
            device_type (DeviceType): Type of the device (eec or pps)

        Returns:
            str: device status
        """
        if not self._pins or len(self._pins) == 0:
            return 'undefined'

        pin = self._pins.filter_by_device_type(device_type)
        if len(pin) == 0:
            return 'undefined'

        return next(iter(pin)).pin_board_label

    def get_pps_current_ref(self) -> str:
        """Get PPS current reference from Netlink DPLL dictionary

        Returns:
            str: PPS current reference
        """
        return self._get_current_reference(DeviceType.PPS)

    def get_eec_current_ref(self) -> str:
        """Get EEC current reference from Netlink DPLL dictionary

        Returns:
            str: EEC current reference
        """
        return self._get_current_reference(DeviceType.EEC)

    def _get_current_pin_type(self, device_type: DeviceType) -> str:
        """Get the pin type from Netlink DPLL dictionary

        Args:
            device_type (DeviceType): Type of the device (eec or pps)

        Returns:
            str: pin type
        """
        if not self._pins or len(self._pins) == 0:
            return 'undefined'

        pin = self._pins.filter_by_device_type(device_type)
        if len(pin) == 0:
            return 'undefined'

        return next(iter(pin)).pin_type

    def get_pps_pin_type(self) -> str:
        """Get PPS current pin type from Netlink DPLL dictionary

        Returns:
            str: PPS current pin type
        """
        return self._get_current_pin_type(DeviceType.PPS)

    def get_eec_pin_type(self) -> str:
        """Get EEC current pin type from Netlink DPLL dictionary

        Returns:
            str: EEC current pin type
        """
        return self._get_current_pin_type(DeviceType.EEC)
