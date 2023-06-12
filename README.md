# voltronic-wifi-bridge
Intercept the voltronic phone-home session for local management with mqtt and others


The inverters I have tested appear to phone home to ess.eybond.com on port 502 using a protocol similar to the one available on the serial port but wrapped in TCP and [some extra magic](Protocol.md)


## Usage

host this server somewhere private and either NAT or use static DNS to force the inverters to connect to it instaed of the remote server


```
usage: voltronic-wifi-bridge [-h] [-u USER] [-p PASSWORD] [-t TOPIC] [-P PORT] mqtthostname mqttport

positional arguments:
  mqtthostname          host name of the mqtt server
  mqttport              port of the mqtt server

options:
  -h, --help            show this help message and exit
  -u USER, --user USER  username for the mqtt server
  -p PASSWORD, --password PASSWORD
                        password for the mqtt server
  -t TOPIC, --topic TOPIC
                        mqtt topic base
  -P PORT, --port PORT  the port to run the voltronic server on
```

## Docker
There is and included dockerfile and docker compose to build and run the service inside docker


## Compatible Hardware
Many Voltronic inverters use very similar protocols.  Yours may work automatically or might need minor tweaking.  Feel free to let the project know if you test it with other hardware.

| Brand | Model | Firmware Versions | Compatibility |
| ---- | ---- | ---- | ---- |
| Maple Leaf Power Systems | 6500EX-48 | 00069.05/00012.21 | Works |



## TODO features (PRs welcome)
 - auto-reg home assistant mqtt
 - feed data to influxdb (multiple versions?)
 - passthrough to remote servers so the phone app still works
 - add support for other inverter models 


## References
https://github.com/manio/skymax-demo for CRC algorithm