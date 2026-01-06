============================================
PTP Status Notifications API Definition v2
============================================

This document defines how a hosted application can subscribe to receive PTP
status notifications from the StarlingX platform and also how to pull notifications
on demand.

The interaction between the application and the platform is done with the
use of a Sidecar residing in the same pod.

The port of the Sidecar is exposed to the application by a downward API and
the address is the localhost of the pod where the application and the Sidecar
are running on. For example: http://127.0.0.1:{port}

The version 2 of the API is documented in the O-RAN Working Group 6 O-Cloud
Notification API specification for Event Consumers v03.00.
Refer to https://www.o-ran.org/specifications for O-RAN specifications.

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

.. note::
   Subscriptions will not persist across system reboots.
   The consuming application must re-subscribe after a reboot.

   As a best practice, it is recommended to create any required subscriptions
   each time the application starts.

************************************************
Subscribe to receiving PTP status notifications
************************************************

.. rest_method:: POST /ocloudNotifications/v2/subscriptions

**Normal response codes**

201

**Error response codes**

badRequest (400), itemNotFound (404), conflict(409)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:9090/resourcestatus/ptp"

**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."
   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:9090/resourcestatus/ptp"

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/gnss-status/gnss-sync-status",
       "SubscriptionId": "704f21a0-19a3-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/704f21a0-19a3-11ed-854c-8a6cf180560d"
   }

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync",
       "SubscriptionId": "dcdae0de-19a3-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/dcdae0de-19a3-11ed-854c-8a6cf180560d"
   }

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/sync-status/sync-state",
       "SubscriptionId": "ca244f8a-1fec-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/ca244f8a-1fec-11ed-854c-8a6cf180560d"
   }

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/sync-status/os-clock-sync-state",
       "SubscriptionId": "8ded8d18-1fee-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/8ded8d18-1fee-11ed-854c-8a6cf180560d"
   }

----------------------
Manage Subscriptions
----------------------

******************************
Query subscription resources
******************************

.. rest_method:: GET /ocloudNotifications/v2/subscriptions

**Normal response codes**

200

**Error response codes**

itemNotFound (404)

**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "SubscriptionId", "plain", "csapi:UUID", "Identifier for the created subscription resource."
   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:9090/resourcestatus/ptp"

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/gnss-status/gnss-sync-status",
       "SubscriptionId": "704f21a0-19a3-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/704f21a0-19a3-11ed-854c-8a6cf180560d"
   }

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/sync-status/sync-state",
       "SubscriptionId": "ca244f8a-1fec-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/ca244f8a-1fec-11ed-854c-8a6cf180560d"
   }

This operation does not accept a request body.

****************************************
Query individual subscription resource
****************************************

.. rest_method:: GET /ocloudNotifications/v2/{SubscriptionId}

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
   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "UriLocation", "plain", "xsd:string", "The URI location to query the subscription resource created."
   "EndpointUri", "plain", "xsd:string", "Endpoint URI (a.k.a callback URI), e.g. http://127.0.0.1:9090/resourcestatus/ptp"

::

   {
       "EndpointUri": "http://127.0.0.1:9090/v2/resource_status/ptp",
       "ResourceAddress": "/./controller-0/sync/sync-status/os-clock-sync-state",
       "SubscriptionId": "8ded8d18-1fee-11ed-854c-8a6cf180560d",
       "UriLocation": "http://127.0.0.1:8080/ocloudNotifications/v2/subscriptions/8ded8d18-1fee-11ed-854c-8a6cf180560d"
   }

This operation does not accept a request body

****************************************
Delete individual subscription resource
****************************************

.. rest_method:: DELETE /ocloudNotifications/v2/{SubscriptionId}

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

.. rest_method:: GET /ocloudNotifications/v2/{ResourceAddress}/CurrentState

**Normal response codes**

200

**Error response codes**

itemNotFound (404)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported. PTP instance name is supported."

This operation does not accept a request body.
**Response parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "id", "plain", "xsd:string", "Identifies the event."
   "specversion", "plain", "xsd:string", "The version of the CloudEvents specification which the event uses. This enables the interpretation of the context."
   "source", "plain", "xsd:string", "Identifies the context in which an event happened."
   "type", "plain", "xsd:string", "This attribute contains a value describing the type of event related to the originating occurrence."
   "time", "plain", "xsd:string", "Time at which the event occurred."
   "data", "plain", "xsd:string", "Array of JSON objects defining the information for the event"
   "version", "plain", "xsd:string", "Version of the Notification API Schema generating the event."
   "values", "plain", "xsd:string", "A JSON array of values defining the event."
   "data_type", "plain", "xsd:string", "Type of value object. (notification | metric)"
   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "value_type", "plain", "xsd:string", "The type format of the value property (enumeration or metric)"
   "value", "plain", "xsd:string", "String representation of value in value_type format"

::

   {
      "id": "64b1c206-6e34-4825-aa1a-141027bb779a",
      "specversion": "1.0",
      "source": "/sync/sync-status/sync-state",
      "type": "event.sync.sync-status.synchronization-state-change",
      "time": "2024-11-15T15:22:33868726Z",
      "data": {
         "version": "1.0",
         "values": [
               {
                  "data_type": "notification",
                  "ResourceAddress": "/././sync/sync-status/sync-state",
                  "value_type": "enumeration",
                  "value": "LOCKED"
               }
         ]
      }
   }

::

   [
      {
         "id": "ce5cf018-1f65-451a-94a0-93c99663c1b9",
         "specversion": "1.0",
         "source": "/sync/ptp-status/clock-class",
         "type": "event.sync.ptp-status.ptp-clock-class-change",
         "time": "2024-11-15T15:22:22689503Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "metric",
                     "ResourceAddress": "/././ptp-inst1/sync/ptp-status/clock-class",
                     "value_type": "metric",
                     "value": "6"
                  }
               ]
         }
      },
      {
         "id": "549312e5-3065-4731-b098-e0582d1d8b7f",
         "specversion": "1.0",
         "source": "/sync/ptp-status/clock-class",
         "type": "event.sync.ptp-status.ptp-clock-class-change",
         "time": "2024-11-15T15:22:23228905Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "metric",
                     "ResourceAddress": "/././ptp-inst2/sync/ptp-status/clock-class",
                     "value_type": "metric",
                     "value": "6"
                  }
               ]
         }
      }
   ]

::

   [
      {
         "id": "db9308a5-f030-4a9c-b535-164f836cfd60",
         "specversion": "1.0",
         "source": "/sync/ptp-status/lock-state",
         "type": "event.sync.ptp-status.ptp-state-change",
         "time": "2024-11-15T15:22:22689480Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "notification",
                     "ResourceAddress": "/././ptp-inst1/sync/ptp-status/lock-state",
                     "value_type": "enumeration",
                     "value": "LOCKED"
                  }
               ]
         }
      },
      {
         "id": "fbda383f-ee5d-4df4-82cb-f6f9c4447fe7",
         "specversion": "1.0",
         "source": "/sync/ptp-status/lock-state",
         "type": "event.sync.ptp-status.ptp-state-change",
         "time": "2024-11-15T15:22:23228893Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "notification",
                     "ResourceAddress": "/././ptp-inst2/sync/ptp-status/lock-state",
                     "value_type": "enumeration",
                     "value": "LOCKED"
                  }
               ]
         }
      }
   ]

::

   [
      {
         "id": "6348989f-4ae6-4a27-9381-189fdf5b1884",
         "specversion": "1.0",
         "source": "/sync/sync-status/os-clock-sync-state",
         "type": "event.sync.sync-status.os-clock-sync-state-change",
         "time": "2024-11-15T15:22:33864925Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "notification",
                     "ResourceAddress": "/././sync/sync-status/os-clock-sync-state",
                     "value_type": "enumeration",
                     "value": "LOCKED"
                  }
               ]
         }
      }
   ]

::

   [
      {
         "id": "0adfb163-20fa-43ac-94c1-bc9bbc06e5c8",
         "specversion": "1.0",
         "source": "/sync/gnss-status/gnss-sync-status",
         "type": "event.sync.gnss-status.gnss-state-change",
         "time": "2024-11-15T15:22:33753153Z",
         "data": {
               "version": "1.0",
               "values": [
                  {
                     "data_type": "notification",
                     "ResourceAddress": "/././ts1/sync/gnss-status/gnss-sync-status",
                     "value_type": "enumeration",
                     "value": "SYNCHRONIZED"
                  }
               ]
         }
      }
   ]


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

.. rest_method:: POST {CallbackUri}

**Normal response codes**

204

**Error response codes**

badRequest (400), itemNotFound (404), tiemout(408)

**Request parameters**

.. csv-table::
   :header: "Parameter", "Style", "Type", "Description"
   :widths: 20, 20, 20, 60

   "id", "plain", "xsd:string", "Identifies the event."
   "specversion", "plain", "xsd:string", "The version of the CloudEvents specification which the event uses. This enables the interpretation of the context."
   "source", "plain", "xsd:string", "Identifies the context in which an event happened."
   "type", "plain", "xsd:string", "This attribute contains a value describing the type of event related to the originating occurrence."
   "time", "plain", "xsd:string", "Time at which the event occurred."
   "data", "plain", "xsd:string", "Array of JSON objects defining the information for the event."
   "version", "plain", "xsd:string", "Version of the Notification API Schema generating the event."
   "values", "plain", "xsd:string", "A JSON array of values defining the event."
   "data_type", "plain", "xsd:string", "Type of value object. (notification | metric)"
   "ResourceAddress", "plain", "xsd:string", "Specifies a hierarchical path which consists of the resource. Only the current cluster and node is supported."
   "value_type", "plain", "xsd:string", "The type format of the value property (enumeration or metric)"
   "value", "plain", "xsd:string", "String representation of value in value_type format."

::

   {
       "id": "d38af5a6-70bb-4b3d-892a-df50cf2fdb09",
       "specversion": "1.0",
       "source": "/sync/sync-status/sync-state",
       "type": "event.sync.sync-status.synchronization-state-change",
       "time": "2022-08-12T19:20:54896244Z",
       "data": {
         "version": "1.0",
         "values": [
            {
               "data_type": "notification",
               "ResourceAddress": "/././sync/sync-status/sync-state",
               "value_type": "enumeration",
               "value": "HOLDOVER"
            }
         ]
      }
   }

