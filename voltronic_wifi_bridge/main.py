#!/bin/python
import argparse
import sys
import pprint
import time
import signal

from voltronic_wifi_bridge import voltronic_server
from voltronic_wifi_bridge import mqtt_client


class VoltronicRelay():
    def __init__(self):
        self.mqttc = None
        self.vserver = None
        self._cleaned_up = False
        self._run_parser()
    
    def _run_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("mqtthostname", help="host name of the mqtt server")
        parser.add_argument("mqttport", type=int, help="port of the mqtt server")
        parser.add_argument("-u", "--user", help="username for the mqtt server")
        parser.add_argument("-p", "--password", help="password for the mqtt server")
        parser.add_argument("-t", "--topic", help="mqtt topic base", default="voltronic")
        parser.add_argument("-P", "--port", type=int, help="the port to run the voltronic server on", default=502)
        args = parser.parse_args()
        pprint.pprint(args)
        if args.mqtthostname is not None:
            self.mqttc = mqtt_client.MQTTClient(args.mqtthostname, args.mqttport, args.topic, username=args.user, password=args.password)
            self.vserver = voltronic_server.VoltronicServer(args.port)
            self.vserver.register_mqtt(self.mqttc)
        return
    

    def _clean_up(self, signum, frame):
        print("cleaning up")
        self.vserver.exit()
        self.vserver.join()
        self.mqttc.loop_stop()
        self._cleaned_up = True
        return

    def run(self):
        signal.signal(signal.SIGINT, self._clean_up)
        signal.signal(signal.SIGTERM, self._clean_up)
        self.vserver.start()

        while not self._cleaned_up:
            time.sleep(1)
        return


def main():
    relay = VoltronicRelay()
    relay.run()

    return

if __name__ == '__main__':
    main()

