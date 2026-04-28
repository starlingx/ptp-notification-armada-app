"""
Unit tests for services: config_watcher,
health, and daemon helpers.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import json
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock



class TestConfigFileWatcher(unittest.TestCase):
    """Tests for ConfigFileWatcher."""

    def test_init(self):
        """Test ConfigFileWatcher init."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        callback = mock.MagicMock()
        watcher = ConfigFileWatcher(
            '/tmp/test', callback,
            debounce_seconds=1)
        self.assertEqual(
            watcher.watch_path, '/tmp/test')
        self.assertEqual(
            watcher.callback, callback)
        self.assertEqual(
            watcher.debounce_seconds, 1)
        self.assertIsNone(watcher.observer)

    def test_start_stop(self):
        """Test start and stop of watcher."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        with tempfile.TemporaryDirectory() \
                as tmpdir:
            callback = mock.MagicMock()
            watcher = ConfigFileWatcher(
                tmpdir, callback)
            watcher.start()
            self.assertIsNotNone(
                watcher.observer)
            watcher.stop()

    def test_debounce_mechanism(self):
        """Test debounce prevents rapid calls."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        callback = mock.MagicMock()
        watcher = ConfigFileWatcher(
            '/tmp', callback,
            debounce_seconds=0.1)
        watcher._on_config_change()
        watcher._on_config_change()
        watcher._on_config_change()
        time.sleep(0.3)
        self.assertEqual(
            callback.call_count, 1)

    def test_trigger_callback_exception(self):
        """Test callback exception handled."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        callback = mock.MagicMock(
            side_effect=Exception("test error"))
        watcher = ConfigFileWatcher(
            '/tmp', callback,
            debounce_seconds=0)
        # Should not raise despite callback exception
        watcher._trigger_callback()
        callback.assert_called_once()

    def test_stop_without_start(self):
        """Test stop when observer is None."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                ConfigFileWatcher)
        watcher = ConfigFileWatcher(
            '/tmp', mock.MagicMock())
        # Should not raise when stopping without start
        watcher.stop()
        self.assertIsNone(watcher.observer)


class TestConfigChangeHandler(unittest.TestCase):
    """Tests for _ConfigChangeHandler."""

    def test_on_created_conf_file(self):
        """Test on_created for .conf files."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                _ConfigChangeHandler)
        callback = mock.MagicMock()
        handler = _ConfigChangeHandler(callback)
        event = mock.MagicMock()
        event.is_directory = False
        event.src_path = '/tmp/test.conf'
        handler.on_created(event)
        callback.assert_called_once()

    def test_on_created_non_conf_file(self):
        """Test on_created ignores non-.conf."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                _ConfigChangeHandler)
        callback = mock.MagicMock()
        handler = _ConfigChangeHandler(callback)
        event = mock.MagicMock()
        event.is_directory = False
        event.src_path = '/tmp/test.txt'
        handler.on_created(event)
        callback.assert_not_called()

    def test_on_modified_conf_file(self):
        """Test on_modified for .conf files."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                _ConfigChangeHandler)
        callback = mock.MagicMock()
        handler = _ConfigChangeHandler(callback)
        event = mock.MagicMock()
        event.is_directory = False
        event.src_path = '/tmp/ptp4l.conf'
        handler.on_modified(event)
        callback.assert_called_once()

    def test_on_deleted_conf_file(self):
        """Test on_deleted for .conf files."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                _ConfigChangeHandler)
        callback = mock.MagicMock()
        handler = _ConfigChangeHandler(callback)
        event = mock.MagicMock()
        event.is_directory = False
        event.src_path = '/tmp/phc2sys.conf'
        handler.on_deleted(event)
        callback.assert_called_once()

    def test_on_created_directory_ignored(self):
        """Test directory events ignored."""
        from trackingfunctionsdk.services \
            .config_watcher import (
                _ConfigChangeHandler)
        callback = mock.MagicMock()
        handler = _ConfigChangeHandler(callback)
        event = mock.MagicMock()
        event.is_directory = True
        event.src_path = '/tmp/test.conf'
        handler.on_created(event)
        callback.assert_not_called()


class TestHealthServer(unittest.TestCase):
    """Tests for health server components."""

    def test_get_address_family_ipv4(self):
        """Test IPv4 address family."""
        from trackingfunctionsdk.services.health \
            import get_address_family
        result = get_address_family('127.0.0.1')
        self.assertEqual(
            result, socket.AF_INET)

    def test_get_address_family_ipv6(self):
        """Test IPv6 address family."""
        from trackingfunctionsdk.services.health \
            import get_address_family
        result = get_address_family('::1')
        self.assertEqual(
            result, socket.AF_INET6)

    def test_health_request_handler_response(self):
        """Test HealthRequestHandler response."""
        from trackingfunctionsdk.services.health \
            import HealthRequestHandler
        handler = mock.MagicMock(
            spec=HealthRequestHandler)
        response = (
            HealthRequestHandler
            .get_response(handler))
        data = json.loads(response)
        self.assertTrue(data['health'])


class TestDaemonSourceType(unittest.TestCase):
    """Tests for daemon source_type mapping."""

    def test_source_type_mapping(self):
        """Test source_type has expected keys."""
        from trackingfunctionsdk.services.daemon \
            import source_type
        self.assertIn(
            '/sync/gnss-status'
            '/gnss-sync-status',
            source_type)
        self.assertIn(
            '/sync/ptp-status/clock-class',
            source_type)
        self.assertIn(
            '/sync/ptp-status/lock-state',
            source_type)
        self.assertIn(
            '/sync/sync-status'
            '/os-clock-sync-state',
            source_type)
        self.assertIn(
            '/sync/sync-status/sync-state',
            source_type)

    def test_source_type_values(self):
        """Test source_type values are events."""
        from trackingfunctionsdk.services.daemon \
            import source_type
        for key, value in source_type.items():
            self.assertTrue(
                value.startswith('event.sync.'))

    def test_ts2phc_generic_clock_missing(self):
        """Test generic clock missing pidfile."""
        from trackingfunctionsdk.services.daemon \
            import _ts2phc_uses_generic_clock
        result = _ts2phc_uses_generic_clock(
            'nonexistent-instance')
        self.assertFalse(result)

    def test_effective_holdover_no_devices(self):
        """Test holdover with no PTP devices."""
        from trackingfunctionsdk.services.daemon \
            import _get_ptp4l_effective_holdover
        with mock.patch(
                'trackingfunctionsdk.services'
                '.daemon'
                '._get_ptp_devices_for_config',
                return_value=set()):
            result = (
                _get_ptp4l_effective_holdover(
                    'ptp4l.conf', [], [], 30))
            self.assertEqual(result, 30)


class TestPtpEventProducerListenerEndpoint(
        unittest.TestCase):
    """Tests for ListenerEndpoint."""

    def test_init_no_handler(self):
        """Test init without handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        endpoint = (
            PtpEventProducer.ListenerEndpoint())
        self.assertIsNone(endpoint.handler)

    def test_init_with_handler(self):
        """Test init with handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        handler = mock.MagicMock()
        endpoint = (
            PtpEventProducer.ListenerEndpoint(
                handler=handler))
        self.assertEqual(
            endpoint.handler, handler)

    def test_query_status_with_handler(self):
        """Test QueryStatus with handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        handler = mock.MagicMock()
        handler.query_status.return_value = (
            {'status': 'ok'})
        endpoint = (
            PtpEventProducer.ListenerEndpoint(
                handler=handler))
        result = endpoint.QueryStatus(
            ctx=None, source='/sync')
        handler.query_status \
            .assert_called_once_with(
                source='/sync')
        self.assertEqual(
            result, {'status': 'ok'})

    def test_query_status_no_handler(self):
        """Test QueryStatus without handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        endpoint = (
            PtpEventProducer.ListenerEndpoint())
        result = endpoint.QueryStatus(ctx=None)
        self.assertIsNone(result)

    def test_trigger_delivery_with_handler(self):
        """Test TriggerDelivery with handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        handler = mock.MagicMock()
        handler.trigger_delivery \
            .return_value = True
        endpoint = (
            PtpEventProducer.ListenerEndpoint(
                handler=handler))
        result = endpoint.TriggerDelivery(
            ctx=None, data='test')
        handler.trigger_delivery \
            .assert_called_once_with(
                data='test')

    def test_trigger_delivery_no_handler(self):
        """Test TriggerDelivery no handler."""
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        endpoint = (
            PtpEventProducer.ListenerEndpoint())
        result = endpoint.TriggerDelivery(
            ctx=None)
        self.assertIsNone(result)


class TestPtpEventProducerInit(unittest.TestCase):
    """Tests for PtpEventProducer init."""

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_init_local_only(
            self, mock_broker):
        """Test init with local broker only.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        self.assertEqual(
            producer.node_name,
            'controller-0')
        self.assertIsNotNone(
            producer.local_broker_client)
        self.assertIsNone(
            producer
            .registration_broker_client)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_init_with_registration(
            self, mock_broker):
        """Test init with registration broker.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        local_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        remote_url = (
            'rabbit://admin:admin'
            '@10.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0',
            local_url, remote_url)
        self.assertIsNotNone(
            producer
            .registration_broker_client)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_status_local_success(
            self, mock_broker):
        """Test publish_status_local success.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        sync_path = (
            '/sync/ptp-status/lock-state')
        result = (
            producer.publish_status_local(
                {'state': 'Locked'},
                sync_path))
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_local_no_client(
            self, mock_broker):
        """Test publish_local with no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        producer.local_broker_client = None
        result = (
            producer.publish_status_local(
                {'state': 'Locked'}, '/sync'))
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_local_retry_exhausted(
            self, mock_broker):
        """Test publish_local retries exhausted.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        producer.local_broker_client \
            .cast.side_effect = [
                Exception("fail1"),
                Exception("fail2"),
                Exception("fail3")]
        result = (
            producer.publish_status_local(
                {'state': 'Locked'},
                '/sync', retry=3))
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_all_no_client(
            self, mock_broker):
        """Test publish_all no registration.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        result = producer.publish_status_all(
            {'state': 'Locked'})
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_start_listener_local(
            self, mock_broker):
        """Test start_status_listener_local.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        result = (
            producer
            .start_status_listener_local())
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_start_listener_local_no_client(
            self, mock_broker):
        """Test start_local with no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        producer.local_broker_client = None
        result = (
            producer
            .start_status_listener_local())
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_is_listening_no_clients(
            self, mock_broker):
        """Test is_listening with no clients.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        producer.local_broker_client = None
        result = producer.is_listening()
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_stop_listener_local_no_client(
            self, mock_broker):
        """Test stop_local with no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        producer = PtpEventProducer(
            'controller-0', broker_url)
        producer.local_broker_client = None
        result = (
            producer
            .stop_status_listener_local())
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
