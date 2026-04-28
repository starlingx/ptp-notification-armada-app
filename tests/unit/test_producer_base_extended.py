"""
Additional coverage tests for
ptpeventproducer and client/base.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import time
import unittest
from unittest import mock


BROKER_URL_LOCAL = (
    'rabbit://a:a@127.0.0.1:5672/')
BROKER_URL_REMOTE = (
    'rabbit://a:a@10.0.0.1:5672/')


class TestPtpEventProducerExtended(
        unittest.TestCase):
    """Cover remaining ptpeventproducer methods."""

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_status(self, mock_broker):
        """Test publish_status sends event.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        result_local, result_remote = (
            producer.publish_status(
                {'state': 'Locked'}))
        self.assertIsNotNone(result_local)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_status_all_success(
            self, mock_broker):
        """Test publish_status_all succeeds.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        result = producer.publish_status_all(
            {'state': 'Locked'})
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_publish_status_all_retry_fail(
            self, mock_broker):
        """Test publish_status_all retry failure.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.registration_broker_client \
            .cast.side_effect = [
                Exception("e1"),
                Exception("e2"),
                Exception("e3")]
        result = producer.publish_status_all(
            {'state': 'Locked'}, retry=3)
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_start_status_listener(
            self, mock_broker):
        """Test start_status_listener.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        result = (
            producer.start_status_listener())
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_start_status_listener_all(
            self, mock_broker):
        """Test start_status_listener_all.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        result = (
            producer
            .start_status_listener_all())
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_start_listener_all_no_client(
            self, mock_broker):
        """Test listener_all with no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL)
        result = (
            producer
            .start_status_listener_all())
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_stop_status_listener(
            self, mock_broker):
        """Test stop_status_listener.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.stop_status_listener()
        mock_broker.return_value.remove_listener.assert_called()

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_stop_status_listener_all(
            self, mock_broker):
        """Test stop_status_listener_all.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.stop_status_listener_all()
        mock_broker.return_value.remove_listener.assert_called()

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_stop_listener_all_no_client(
            self, mock_broker):
        """Test stop_all with no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL)
        result = (
            producer
            .stop_status_listener_all())
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_is_listening_both(
            self, mock_broker):
        """Test is_listening with both brokers.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.local_broker_client \
            .is_listening.return_value = True
        producer.registration_broker_client \
            .is_listening.return_value = True
        self.assertTrue(producer.is_listening())

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_is_listening_local(
            self, mock_broker):
        """Test is_listening_local.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL)
        producer.local_broker_client \
            .is_listening.return_value = True
        result = producer.is_listening_local()
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_is_listening_all_no_client(
            self, mock_broker):
        """Test is_listening_all no client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL)
        result = producer.is_listening_all()
        self.assertFalse(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_is_listening_all(
            self, mock_broker):
        """Test is_listening_all with client.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.registration_broker_client \
            .is_listening.return_value = True
        result = producer.is_listening_all()
        self.assertTrue(result)

    @mock.patch(
        'trackingfunctionsdk.client'
        '.ptpeventproducer.BrokerClientBase')
    def test_del(self, mock_broker):
        """Test __del__ cleanup.

        mock_broker -- mocked BrokerClientBase
        """
        from trackingfunctionsdk.client \
            .ptpeventproducer import (
                PtpEventProducer)
        producer = PtpEventProducer(
            'node1', BROKER_URL_LOCAL,
            BROKER_URL_REMOTE)
        producer.__del__()
        self.assertIsNone(
            producer.local_broker_client)
        self.assertIsNone(
            producer
            .registration_broker_client)


class TestBrokerClientBaseExtended(
        unittest.TestCase):
    """Cover remaining client/base.py paths."""

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_refresh_start(
            self, mock_transport):
        """Test refresh starts server.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base \
            import BrokerClientBase
        client = BrokerClientBase(
            'test', BROKER_URL_LOCAL)
        with mock.patch(
                'trackingfunctionsdk.client.base'
                '.oslo_messaging'
                '.get_rpc_server') as mock_srv:
            mock_server = mock.MagicMock()
            mock_srv.return_value = mock_server
            client.add_listener(
                't', 's',
                [mock.MagicMock()])
        self.assertTrue(
            client.is_listening('t', 's'))

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_refresh_stop(
            self, mock_transport):
        """Test refresh stops server.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base \
            import BrokerClientBase
        client = BrokerClientBase(
            'test', BROKER_URL_LOCAL)
        with mock.patch(
                'trackingfunctionsdk.client.base'
                '.oslo_messaging'
                '.get_rpc_server') as mock_srv:
            mock_server = mock.MagicMock()
            mock_srv.return_value = mock_server
            client.add_listener(
                't', 's',
                [mock.MagicMock()])
            client.remove_listener('t', 's')
            mock_server.stop.assert_called()

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_refresh_error(
            self, mock_transport):
        """Test refresh handles error.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base \
            import BrokerClientBase
        client = BrokerClientBase(
            'test', BROKER_URL_LOCAL)
        with mock.patch(
                'trackingfunctionsdk.client.base'
                '.oslo_messaging'
                '.get_rpc_server',
                side_effect=Exception("fail")):
            client.add_listener(
                't', 's',
                [mock.MagicMock()])
        # Listener entry exists but server failed to start
        self.assertTrue(client.is_listening('t', 's'))

    @mock.patch(
        'trackingfunctionsdk.client.base'
        '.rpc_helper.get_transport')
    def test_any_listener_active(
            self, mock_transport):
        """Test any_listener with active ones.

        mock_transport -- mocked get_transport
        """
        from trackingfunctionsdk.client.base \
            import BrokerClientBase
        client = BrokerClientBase(
            'test', BROKER_URL_LOCAL)
        with mock.patch.object(
                client, '_refresh'):
            client.add_listener(
                't1', 's1', [])
            client.add_listener(
                't2', 's2', [])
        self.assertTrue(
            client.any_listener())
        with mock.patch.object(
                client, '_refresh'):
            client.remove_listener(
                't1', 's1')
        self.assertTrue(
            client.any_listener())
        with mock.patch.object(
                client, '_refresh'):
            client.remove_listener(
                't2', 's2')
        self.assertFalse(
            client.any_listener())


if __name__ == '__main__':
    unittest.main()
