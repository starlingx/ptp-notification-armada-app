#coding=utf-8

from wsme import types as wtypes

RPC_ENDPOINT_BASE = {
    'Version': '1.0',
    'Namespace': 'notification',
    'Exchange': 'notification_exchange',
    'TransportEndpoint': '',
    'Topic': '',
    'Server': ''
}

class RpcEndpointInfo(wtypes.Base):
    TransportEndpoint = wtypes.text
    Exchange = wtypes.text
    Topic = wtypes.text
    Server = wtypes.text
    Version = wtypes.text
    Namespace = wtypes.text

    def __init__(self, transport_endpoint):
        self.endpoint_json = {
            'Version': RPC_ENDPOINT_BASE['Version'],
            'Namespace': RPC_ENDPOINT_BASE['Namespace'],
            'Exchange': RPC_ENDPOINT_BASE['Exchange'],
            'TransportEndpoint': transport_endpoint,
            'Topic': RPC_ENDPOINT_BASE['Topic'],
            'Server': RPC_ENDPOINT_BASE['Server']
        }
        super(RpcEndpointInfo, self).__init__(**self.endpoint_json)

    def to_dict(self):
        return self.endpoint_json
