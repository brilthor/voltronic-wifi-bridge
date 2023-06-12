#!/bin/python
import time
import paho.mqtt.client as mqtt
import threading




class MQTTClient():
    def __init__(self, mqtt_hostname, mqtt_port, base_topic, username = None, password = None):
        self._mqtt_hostname = mqtt_hostname
        self._mqtt_port = mqtt_port
        self._username = username
        self._password = password

        self._base_topic = base_topic


        self._client = self._register_client()
        print("about to connect")
        self._client.connect(self._mqtt_hostname, self._mqtt_port, 60)
        self.loop_start()
        print("connected")

        self._message_callback_registrations_lock = threading.Lock()
        self._message_callback_registrations = []

        return
    
    def register_message_callback(self, callback, topicmatch):
        print("starting registering callback")
        reg = {
            "topicmatch": topicmatch,
            "callback": callback
        }
        with self._message_callback_registrations_lock:
            self._message_callback_registrations.append(reg)
        print("finishing registering callback")
        return

    def unregister_message_callback(self, callback, topicmatch):
        print("starting unregistering callback")
        removelist = []
        with self._message_callback_registrations_lock:
            for index, value in enumerate(self._message_callback_registrations):
                if value["topicmatch"] == topicmatch and value["callback"] == callback:
                    removelist.append(index)
            
            for index in sorted(removelist,reverse=True):
                self._message_callback_registrations.pop(index)
        print("finished unregistering callback")
        return
    
    def publish_message(self, topicpart, message):
        # publish a message inside the base topic area
        self._client.publish("{}/{}".format(self._base_topic, topicpart), message)
        return


    def _register_client(self):

        client = mqtt.Client("voltronic-wifi-bridge")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_publish = self.on_publish
        client.username_pw_set(self._username, password=self._password)

        return client

    def on_connect(self, client, userdata, flags, rc):
        
        print("Connected with result code "+str(rc))

        print("about to publish")
        client.publish("{}/connected".format(self._base_topic), time.time())

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        print("about to subscribe")
        client.subscribe("{}/#".format(self._base_topic))
        print("subscribed")
        return

    def on_message(self, client, userdata, msg):
        print("Got message {} on topic {}".format(msg.payload, msg.topic))

        with self._message_callback_registrations_lock:
            for reg in self._message_callback_registrations:
                # print("checking match with: {}".format(reg["topicmatch"]))
                if msg.topic.startswith("{}/{}".format(self._base_topic, reg["topicmatch"])):
                    print("Message matched; doing callback")
                    reg["callback"](msg)

        return

    def on_publish(self, client, userdata, mid):
        #print("on_publish called")

        return

    def loop_start(self):
        self._client.loop_start()
        return

    def loop_stop(self):
        self._client.loop_stop()
        return   

