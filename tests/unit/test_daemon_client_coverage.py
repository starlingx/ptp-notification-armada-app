"""
Tests for daemon, client/base, rpc_helper,
and health to increase coverage.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import json
import tempfile
import time
import unittest
from unittest import mock


from trackingfunctionsdk.common.helpers import (
    constants)
from trackingfunctionsdk.model.dto.ptpstate import (
    PtpState)
from trackingfunctionsdk.model.dto.gnssstate import (
    GnssState)
from trackingfunctionsdk.model.dto.osclockstate import (
    OsClockState)
from trackingfunctionsdk.model.dto.overallclockstate \
    import OverallClockState



class TestDaemonHelpers(unittest.TestCase):
    """Test daemon module-level functions."""

    def test_get_ptp_devices_missing_config(self):
        """Test with missing config file.

        Returns empty set for nonexistent file.
        """
        from trackingfunctionsdk.services.daemon \
            import _get_ptp_devices_for_config
        result = _get_ptp_devices_for_config(
            '/nonexistent.conf')
        self.assertEqual(result, set())

    def test_get_ptp_devices_with_file(self):
        """Test with valid config file.

        Returns set of PTP device names.
        """
        from trackingfunctionsdk.services.daemon \
            import _get_ptp_devices_for_config
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write("[global]\n[ens1f0]\n")
            config_path = tmp_file.name
        try:
            with mock.patch(
                    'trackingfunctionsdk.services'
                    '.daemon.utils'
                    '.get_interface_phc_device',
                    return_value='ptp0'):
                result = (
                    _get_ptp_devices_for_config(
                        config_path))
            self.assertIn('ptp0', result)
        finally:
            os.unlink(config_path)

    def test_effective_holdover_shared(self):
        """Test effective holdover with shared dev.

        Returns GNSS holdover when devices shared.
        """
        from trackingfunctionsdk.services.daemon \
            import _get_ptp4l_effective_holdover
        with mock.patch(
                'trackingfunctionsdk.services.daemon'
                '._get_ptp_devices_for_config',
                side_effect=[
                    {'ptp0'}, {'ptp0'}]), \
             mock.patch(
                'trackingfunctionsdk.services.daemon'
                '._ts2phc_uses_generic_clock',
                return_value=False), \
             mock.patch(
                'trackingfunctionsdk.services.daemon'
                '.instance_config_parser'
                '.get_instance_gnss_holdover_time',
                return_value=20):
            result = _get_ptp4l_effective_holdover(
                'ptp4l.conf',
                ['gnss.conf'],
                ['gnss-inst'], 30)
        self.assertEqual(result, 20)

    def test_effective_holdover_generic(self):
        """Test holdover with generic clock.

        Returns default when generic clock used.
        """
        from trackingfunctionsdk.services.daemon \
            import _get_ptp4l_effective_holdover
        with mock.patch(
                'trackingfunctionsdk.services.daemon'
                '._get_ptp_devices_for_config',
                side_effect=[
                    {'ptp0'}, {'ptp0'}]), \
             mock.patch(
                'trackingfunctionsdk.services.daemon'
                '._ts2phc_uses_generic_clock',
                return_value=True):
            result = _get_ptp4l_effective_holdover(
                'ptp4l.conf',
                ['gnss.conf'],
                ['gnss-inst'], 30)
        self.assertEqual(result, 30)

    def test_effective_holdover_no_shared(self):
        """Test holdover with no shared devices.

        Returns default when no shared devices.
        """
        from trackingfunctionsdk.services.daemon \
            import _get_ptp4l_effective_holdover
        with mock.patch(
                'trackingfunctionsdk.services.daemon'
                '._get_ptp_devices_for_config',
                side_effect=[
                    {'ptp0'}, {'ptp1'}]):
            result = _get_ptp4l_effective_holdover(
                'ptp4l.conf',
                ['gnss.conf'],
                ['gnss-inst'], 30)
        self.assertEqual(result, 30)

    def test_source_type_keys(self):
        """Test source_type dict has 8 entries."""
        from trackingfunctionsdk.services.daemon \
            import source_type
        self.assertEqual(len(source_type), 8)

    def test_process_worker_default_exists(self):
        """Test ProcessWorkerDefault is callable."""
        from trackingfunctionsdk.services.daemon \
            import ProcessWorkerDefault
        self.assertTrue(
            callable(ProcessWorkerDefault))


class TestPtpWatcherDefaultInit(unittest.TestCase):
    """Test PtpWatcherDefault __init__."""

    def _build_daemon_context(self):
        """Build a daemon context JSON string.

        Returns JSON string with daemon config.
        """
        return json.dumps({
            'PTP4L_INSTANCES': ['ptp-inst1'],
            'GNSS_INSTANCES': ['gnss-inst1'],
            'GNSS_CONFIGS': ['/tmp/gnss.conf'],
            'PHC2SYS_CONFIG':
                constants.PHC2SYS_CONFIG_PATH
                + 'phc2sys-phc2sys-test.conf',
            'PHC2SYS_SERVICE_NAME':
                'phc2sys-test',
            'THIS_NODE_NAME': 'controller-0',
            'THIS_NAMESPACE': 'notification',
            'NOTIFICATION_TRANSPORT_ENDPOINT':
                'rabbit://admin:admin'
                '@127.0.0.1:5672/',
            'REGISTRATION_TRANSPORT_ENDPOINT':
                'rabbit://admin:admin'
                '@127.0.0.1:5672/',
        })

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_init(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test PtpWatcherDefault initialization.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        self.assertEqual(
            watcher.node_name, 'controller-0')
        self.assertIn(
            'ptp-inst1',
            watcher.ptptracker_context)
        self.assertIn(
            'gnss-inst1',
            watcher.gnsstracker_context)
        self.assertIsNotNone(
            watcher.osclocktracker_context)
        self.assertIsNotNone(
            watcher.overalltracker_context)
        self.assertTrue(
            watcher.forced_publishing)

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_signal_ptp_event(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test signal_ptp_event sets event.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        watcher.signal_ptp_event()
        self.assertTrue(event.is_set())

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_signal_ptp_event_no_event(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test signal_ptp_event with no event.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            None, '{}', daemon_context)
        watcher.signal_ptp_event()
        mock_producer.return_value.publish_status.assert_not_called()

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_get_ptp_status_simulated(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test PTP status with simulated device.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        watcher.ptp_device_simulated = True
        ptp_monitor = mock.MagicMock()
        ptp_monitor.set_ptp_sync_state \
            .return_value = None
        old_time = time.time() - 100
        get_ptp = (
            watcher
            ._PtpWatcherDefault__get_ptp_status)
        new_event, state, _ = get_ptp(
            30, 2, PtpState.Freerun,
            old_time, ptp_monitor)
        self.assertTrue(new_event)
        self.assertEqual(state, PtpState.Locked)

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_get_ptp_status_real(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test PTP status with real device.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        watcher.ptp_device_simulated = False
        ptp_monitor = mock.MagicMock()
        ptp_monitor.set_ptp_sync_state \
            .return_value = None
        ptp_monitor.get_ptp_sync_state \
            .return_value = (
                True, PtpState.Locked,
                time.time())
        get_ptp = (
            watcher
            ._PtpWatcherDefault__get_ptp_status)
        new_event, state, _ = get_ptp(
            30, 2, PtpState.Freerun,
            time.time(), ptp_monitor)
        self.assertTrue(new_event)

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_get_gnss_status(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test GNSS status retrieval.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        gnss_monitor = mock.MagicMock()
        gnss_monitor.get_gnss_status \
            .return_value = (
                True, GnssState.Synchronized,
                time.time())
        get_gnss = (
            watcher
            ._PtpWatcherDefault__get_gnss_status)
        new_event, state, _ = get_gnss(
            GnssState.Failure_Nofix,
            time.time(), gnss_monitor)
        self.assertTrue(new_event)

    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpEventProducer')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.OsClockMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.PtpMonitor')
    @mock.patch(
        'trackingfunctionsdk.services.daemon'
        '.GnssMonitor')
    def test_get_os_clock_status(
            self, mock_gnss, mock_ptp,
            mock_osclock, mock_producer):
        """Test OS clock status retrieval.

        mock_gnss -- mocked GnssMonitor
        mock_ptp -- mocked PtpMonitor
        mock_osclock -- mocked OsClockMonitor
        mock_producer -- mocked PtpEventProducer
        """
        from trackingfunctionsdk.services.daemon \
            import PtpWatcherDefault
        import threading
        event = threading.Event()
        daemon_context = (
            self._build_daemon_context())
        watcher = PtpWatcherDefault(
            event, '{}', daemon_context)
        watcher.os_clock_monitor \
            .os_clock_status.return_value = (
                True, OsClockState.Locked,
                time.time())
        get_os = (
            watcher
            ._PtpWatcherDefault__get_os_clock_status)
        new_event, state, _ = get_os(
            30, 2, OsClockState.Freerun,
            time.time())
        self.assertTrue(new_event)


class TestBrokerClientBase(unittest.TestCase):
    """Tests for client/base.py BrokerClientBase."""

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_init(self, mock_transport):
        """Test BrokerClientBase initialization.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        self.assertEqual(
            client.broker_name, 'test')
        self.assertEqual(client.listeners, {})

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_add_remove_listener(
            self, mock_transport):
        """Test add and remove listener.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        with mock.patch.object(
                client, '_refresh'):
            client.add_listener(
                'topic1', 'server1', [])
            self.assertTrue(
                client.is_listening(
                    'topic1', 'server1'))
            client.remove_listener(
                'topic1', 'server1')
            self.assertFalse(
                client.is_listening(
                    'topic1', 'server1'))

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_any_listener(self, mock_transport):
        """Test any_listener detection.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        self.assertFalse(client.any_listener())
        with mock.patch.object(
                client, '_refresh'):
            client.add_listener('t', 's', [])
        self.assertTrue(client.any_listener())

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.oslo_messaging.get_rpc_client')
    def test_cast(
            self, mock_rpc, mock_transport):
        """Test cast sends notification.

        mock_rpc -- mocked get_rpc_client
        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        client.cast(
            'topic1', 'NotifyStatus',
            notification='test')
        mock_rpc.assert_called_once()

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.oslo_messaging.get_rpc_client')
    def test_call(
            self, mock_rpc, mock_transport):
        """Test call queries status.

        mock_rpc -- mocked get_rpc_client
        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        client.call(
            'topic1', 'server1', 'QueryStatus')
        mock_rpc.assert_called_once()

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_is_listening_empty(
            self, mock_transport):
        """Test is_listening with no listeners.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base import (
            BrokerClientBase)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        client = BrokerClientBase(
            'test', broker_url)
        self.assertFalse(
            client.is_listening('x', 'y'))


class TestRpcHelper(unittest.TestCase):
    """Tests for rpc_helper."""

    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.rpc_helper.oslo_messaging'
        '.get_rpc_transport')
    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.rpc_helper.oslo_messaging'
        '.set_transport_defaults')
    def test_get_transport(
            self, mock_defaults, mock_get):
        """Test get_transport calls oslo.

        mock_defaults -- mocked set_defaults
        mock_get -- mocked get_rpc_transport
        """
        from trackingfunctionsdk.common.helpers \
            import rpc_helper
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import RpcEndpointInfo
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        endpoint = RpcEndpointInfo(broker_url)
        rpc_helper.get_transport(endpoint)
        mock_defaults.assert_called_once()
        mock_get.assert_called_once()

    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.rpc_helper.oslo_messaging'
        '.get_rpc_client')
    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.rpc_helper.oslo_messaging'
        '.get_rpc_transport')
    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.rpc_helper.oslo_messaging'
        '.set_transport_defaults')
    def test_setup_client(
            self, mock_defaults,
            mock_get_transport,
            mock_get_client):
        """Test setup_client creates RPC client.

        mock_defaults -- mocked set_defaults
        mock_get_transport -- mocked transport
        mock_get_client -- mocked get_rpc_client
        """
        from trackingfunctionsdk.common.helpers \
            import rpc_helper
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import RpcEndpointInfo
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        endpoint = RpcEndpointInfo(broker_url)
        rpc_helper.setup_client(
            endpoint, 'topic', 'server')
        mock_get_client.assert_called_once()


class TestHealthServerCoverage(unittest.TestCase):
    """Additional health server tests."""

    def test_health_server_init(self):
        """Test HealthServer initialization."""
        from trackingfunctionsdk.services.health \
            import HealthServer
        with mock.patch(
                'trackingfunctionsdk.services'
                '.health.HTTPServer'):
            server = HealthServer()
            self.assertIsNotNone(server)

    def test_health_server_run(self):
        """Test HealthServer run starts thread."""
        from trackingfunctionsdk.services.health \
            import HealthServer
        with mock.patch(
                'trackingfunctionsdk.services'
                '.health.HTTPServer'):
            server = HealthServer()
            server.thread = mock.MagicMock()
            server.run()
            server.thread.start \
                .assert_called_once()


if __name__ == '__main__':
    unittest.main()
