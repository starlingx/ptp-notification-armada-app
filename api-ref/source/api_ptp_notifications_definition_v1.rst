============================================
PTP Status Notifications API Definition v1
============================================

This document defines how a hosted application can subscribe to receive PTP
status notifications from the StarlingX platform and also how to pull notifications
on demand.

The interaction between the application and the platform is done with the
use of a Sidecar residing in the same pod.

The port of the Sidecar is exposed to the application by a downward API and
the address is the localhost of the pod where the application and the Sidecar
are running on. For example: http://127.0.0.1:{port}

--------------------
Create Subscription
--------------------

As the result of successfully executing this method, a new
subscription resource will be created and a variable value
(subscriptionId) will be used for representing this
resource. An initial PTP notification will be triggered,
showing the initial status of the PTP resource followed
by PTP status notifications if there is a change to the
PTP status.

************************************************
Subscribe to receiving PTP status notifications
************************************************

.. rest_method:: POST /ocloudNotifications/v1/subscriptions

**Normal response codes**

201

**Error response codes**

badRequest (400), itemNotFound (404), conflict(409)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides: ``*`` for all worker nodes, ``.`` for worker node where the application resides, node name specified by the downward API."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:8080/resourcestatus/ptp"

**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides, ``NodeName``: ``*`` for all worker nodes, ``.`` for worker node where the application resides, ``node name`` specified by the downward API."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:8080/resourcestatus/ptp"

::

   {
       "ResourceType": "PTP",
       "ResourceQualifier": {
           "NodeName": "controller-0"
       },
       "EndpointUri": "http://127.0.0.1:9090/v1/resource_status/ptp"
   }

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v1/resource_status/ptp",
       "ResourceQualifier": {
           "NodeName": "controller-0"
       },
       "ResourceType": "PTP",
       "SubscriptionId": "a904a444-7e30-11eb-9fd0-82e7589e5f61",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v1/subscriptions/a904a444-7e30-11eb-9fd0-82e7589e5f61"
   }

----------------------
Manage Subscriptions
----------------------

******************************
Query subscription resources
******************************

.. rest_method:: GET /ocloudNotifications/v1/subscriptions

**Normal response codes**

200

**Error response codes**

itemNotFound (404)

**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides, ``NodeName``: ``*`` for all worker nodes, ``.`` for worker node where the application resides, ``node name`` specified by the downward API."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:8080/resourcestatus/ptp"

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v1/resource_status/ptp",
       "ResourceQualifier": {
           "NodeName": "controller-0"
       },
       "ResourceType": "PTP",
       "SubscriptionId": "a904a444-7e30-11eb-9fd0-82e7589e5f61",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v1/subscriptions/a904a444-7e30-11eb-9fd0-82e7589e5f61"
   }

   {
       "EndpointUri": "http://127.0.0.1:9090/v1/resource_status/ptp_cluster",
       "ResourceQualifier": {
           "NodeName": "*"
       },
       "ResourceType": "PTP",
       "SubscriptionId": "e614a666-7e30-11eb-9fd0-2e87589e8a30",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v1/subscriptions/e614a666-7e30-11eb-9fd0-2e87589e8a30"
   }

This operation does not accept a request body.

****************************************
Query individual subscription resource
****************************************

.. rest_method:: GET /ocloudNotifications/v1/{SubscriptionId}

**Normal response codes**

200

**Error response codes**

itemNotFound (404)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."

**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides, ``NodeName``: ``*`` for all worker nodes, ``.`` for worker node where the application resides, ``node name`` specified by the downward API."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:8080/resourcestatus/ptp"

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v1/resource_status/ptp",
       "ResourceQualifier": {
           "NodeName": "controller-0"
       },
       "ResourceType": "PTP",
       "SubscriptionId": "a904a444-7e30-11eb-9fd0-82e7589e5f61",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v1/subscriptions/a904a444-7e30-11eb-9fd0-82e7589e5f61"
   }

This operation does not accept a request body

****************************************
Delete individual subscription resource
****************************************

.. rest_method:: DELETE /ocloudNotifications/v1/{SubscriptionId}

**Normal response codes**

204

**Error response codes**

itemNotFound (404)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."

This operation does not accept a request body.

--------------------------
Pull Status Notifications
--------------------------

******************************
Pull PTP status notifications
******************************

.. rest_method:: GET /ocloudNotifications/v1/{ResourceType}/CurrentState

**Normal response codes**

200

**Error response codes**

itemNotFound (404)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."

This operation does not accept a request body.
**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "EventData", "plain", "xsd:string", "Describes the synchronization state for PTP, State: ``Freerun``, ``Locked``, ``Holdover``."
   "EventTimestamp", "plain", "xsd:float", "This is the time that the event was detected (elapsed seconds since epoch time)."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides, ``NodeName``: ``*`` for all worker nodes, ``.`` for worker node where the application resides, ``node name`` specified by the downward API."
   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."

::

   {
       "EventData": {
          "State": "Freerun"
       },
       "EventTimestamp": 1614969298.8842714,
       "ResourceQualifier": {
          "NodeName": "controller-0"
       },
       "ResourceType": "PTP"
   }

This operation does not accept a request body.

--------------------
Push Notifications
--------------------

After a successful subscription (a subscription resource was created)
the application (e.g. vDU) will be able to receive PTP status notifications.
Note that notifications are sent to the application when there is a change
to the PTP synchronization state.

The notification will be sent to the endpoint reference (EndpointUri) provided
by the application during the creation of the subscription resource.
StarlingX platform includes the notification data in the payload body of
the POST request to the application's EndpointURI (http://127.0.0.1:{port}/{path}).

************************************************************
Send PTP status notifications to the application subscribed
************************************************************

.. rest_method:: POST {EndpointUri}

**Normal response codes**

204

**Error response codes**

badRequest (400), itemNotFound (404), tiemout(408)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "EventData", "plain", "xsd:string", "Describes the synchronization state for PTP, State: ``Freerun``, ``Locked``, ``Holdover``."
   "EventTimestamp", "plain", "xsd:float", "This is the time that the event was detected (elapsed seconds since epoch time)."
   "ResourceQualifier", "plain", "xsd:string", "The node name where PTP resides, ``NodeName``: ``*`` for all worker nodes, ``.`` for worker node where the application resides, ``node name`` specified by the downward API."
   "ResourceType", "plain", "xsd:string", "The resource to subscribe to, currently only ``PTP`` is supported."

::

   {
       "EventData": {
          "State": "Holdover"
       },
       "EventTimestamp": 1714929761.8942328,
       "ResourceQualifier": {
          "NodeName": "controller-0"
       },
       "ResourceType": "PTP"
   }
