#!/bin/python
import socket
import sys
import traceback
import threading
import time
import random
import pprint
from voltronic_wifi_bridge import voltronic_tools

class InvalidResponseException(Exception):
    "Used to indicate when a response doesn't seem to parse right"

class Query():
    
    _output_source_priority_map = {
        "0": "utility_solar_battery", # only use battery + solar when utility not available
        "1": "solar_utility_battery", # use solar and supplement from utility without touching battery (ish?)
        "2": "solar_battery_utility", # use solar and battery power, only touch utility when battery is too low
        "3": "unknown 3"
    }
    _charger_source_priority_map = {
        "0": "utility_first", # charge from solar when exists, utility when not
        "1": "solar_first", # charge from solar when exists, utility when not
        "2": "solar_and_utility", # charge from solar and utility at the same time
        "3": "only_solar", # only charge from solar
    }
    _message_preamble_bytes = b'\xFF\x04'

    def __init__(self, message, connection):
        self._msg = message
        self._connection = connection
        self._counter = self._connection._query_counter
        self._connection._query_counter += 1
        self._connection._queries[self.get_key()] = self
        self._created_time = time.time()
        self._message_generated_time = None

        return

    def should_give_up(self):
        # we should give up on this if it's been 10 seconds since the message generation was last called (probably when sent to network)
        return self._message_generated_time is not None and time.time() - self._message_generated_time > 10

    def get_packaged_message(self):
        # this takes a byte string message and packages it to be ready to go out the socket
        msg = self._msg
        packaged_msg = b''
        crc = voltronic_tools.cal_crc_half(msg)
        counter = self._counter & 0xFFFF
        packaged_msg = counter.to_bytes(2)
        packaged_msg += b'\x00\x01'
        packaged_msg += (len(msg)+5).to_bytes(2)
        packaged_msg += self._message_preamble_bytes
        packaged_msg += msg
        packaged_msg += crc
        packaged_msg += b"\x0d"

        self._message_generated_time = time.time()
        return packaged_msg
    
    def _check_nak(self, msg):
        return msg == b'(NAK'

    def process_response(self, msg):
        print("Got a response for message {} ({}) it was: {}".format(self.get_key(),self._msg, msg))
        return
    
    def _publish_mqtt_from_dict(self, dictionary, keylist=None):
        if keylist is None:
            keylist = dictionary.keys()
        for key in keylist:
            self._connection.publish_message(key, dictionary[key])
        return

    def get_key(self):
        # this key is used for the dictionary of sent queries
        return (self._counter & 0xFFFF).to_bytes(2)

class SetQuery(Query):
    _message_preamble_bytes = b'\x01\x04'

    def process_response(self, msg):
        print("Got a response for message {} ({}) it was: {}".format(self.get_key(),self._msg, msg))
        if self._check_nak(msg):
            print("Got a NAK, setting {} failed".format(self._msg))
        return

class SetChargePriority(SetQuery):
    def __init__(self, mapping_mode, connection):
        code = None
        for key, value in self._charger_source_priority_map.items():
            if mapping_mode == value:
                code = key
                break
        msg = b'PCP%02i' % (int(code))

        Query.__init__(self, msg, connection)
        return

class SetOutputPriority(SetQuery):
    def __init__(self, mapping_mode, connection):
        code = None
        for key, value in self._output_source_priority_map.items():
            if mapping_mode == value:
                code = key
                break
        msg = b'POP%02i' % (int(code))

        Query.__init__(self, msg, connection)
        return

class QueryProtocolID(Query):
    def __init__(self, connection):
        Query.__init__(self, b"QPI", connection)
        return
    
    def process_response(self, msg):
        print("Got a response for QPI message {} it was: {}".format(self.get_key(), msg))
        if self._check_nak(msg):
            print("Got a NAK, skipping processing of {}".format(self._msg))
        elif len(msg) == 5 and msg[0:3] == b'(PI':
            self._connection._protocol_version = int(msg[3:5].decode('ascii'))
            print("Protocol version is: {}".format(self._connection._protocol_version))
        else:
            raise InvalidResponseException("Invalid response to QPI query received: {}".format(msg))
        return

class QuerySerial(Query):
    def __init__(self, connection):
        Query.__init__(self, b"QID", connection)
        return
    
    def process_response(self, msg):
        print("Got a response for QID message {} it was: {}".format(self.get_key(), msg))
        if self._check_nak(msg):
            print("Got a NAK, skipping processing of {}".format(self._msg))
        elif  len(msg) >= 2 and msg[0].to_bytes(1) == b'(':
            self._connection.register_serial_number(msg[1:].decode('ascii'))
            print("Serial is: {}".format(self._connection._inverter_serial_number))
        else:
            raise InvalidResponseException("Invalid response to QID query received: {}".format(msg))
        return

class QueryFirmware(Query):
    def __init__(self, connection, fwnumber=b''):
        self._fwnumber = fwnumber
        Query.__init__(self, b"QVFW" + self._fwnumber, connection)
        return
    
    def process_response(self, msg):
        print("Got a response for QFW message {} it was: {}".format(self.get_key(), msg))
        if self._check_nak(msg):
            print("Got a NAK, skipping processing of {}".format(self._msg))
        elif msg.startswith(b'(VERFW' + self._fwnumber + b':'):
            self._connection._firmware_versions[self._fwnumber] = msg.split(b':')[1].decode('ascii')
            print("firmware {} is: {}".format(self._fwnumber, self._connection._firmware_versions[self._fwnumber]))
            self._connection.publish_message("firmware_version" + self._fwnumber.decode('ascii'), self._connection._firmware_versions[self._fwnumber])
        elif msg.startswith(b'(VERFW:'):
            self._connection._firmware_versions[self._fwnumber] = msg.split(b':')[1].decode('ascii')
            print("firmware {} is: {} WARNING: the response was a bare VERFW:".format(self._fwnumber, self._connection._firmware_versions[self._fwnumber]))
            self._connection.publish_message("firmware_version" + self._fwnumber.decode('ascii'), self._connection._firmware_versions[self._fwnumber])
        else:
            raise InvalidResponseException("Invalid response to {} query received: {}".format(self._msg, msg))
        return    

    
class QueryPIRI(Query):
    def __init__(self, connection):
        Query.__init__(self, b"QPIRI", connection)
        return

    def process_response(self, msg):
        Query.process_response(self, msg)
        # TODO: update this to make it easier to add different device versions
        if len(msg) >= 70 and msg[0].to_bytes(1) == b'(':
            values_array = msg[1:].decode('ascii').split(" ")
            # 0     1    2     3    4    5    6    7    8    9    10   11   12 13  14  15 16 17 18 19 20 21 22   23 24 25  26 27
            # 120.0 54.1 120.0 60.0 54.1 6500 6500 48.0 51.0 44.0 56.0 56.0 3  020 020 1  1  2  9  01 0  7  53.0 0  1  480 0  000'
            # 120.0 54.1 120.0 60.0 54.1 6500 6500 48.0 51.0 44.0 56.0 56.0 3  020 020 1  1  2  9  01 0  7  53.0 0  1  480 0  000
            values = {
                "grid_rating_voltage": values_array[0],  # 120.0 
                "grid_rating_current_maybe": values_array[1],  # 54.1
                "output_rating_voltage": values_array[2],  # 120.0
                "output_rating_frequency": values_array[3],  # 60.0
                "output_rating_current_maybe": values_array[4],  # 54.1
                "output_rating_va": values_array[5],  # 6500
                "output_rating_w": values_array[6],  # 6500
                "battery_rating_voltage": values_array[7],  # 48.0
                "battery_recharge_voltage": float(values_array[8]),  # 51.0  # this might be the switch to grid voltage
                "battery_under_voltage": float(values_array[9]),  # 44.0
                "battery_bulk_voltage": float(values_array[10]),  # 56.0
                "battery_float_voltage": float(values_array[11]),  # 56.0
                "battery_type": values_array[12],  # 3  # from docs: 0: AGM 1: Flooded 2: User
                "max_ac_charging_current": float(values_array[13]),  # 020
                "current_max_charging_current": float(values_array[14]),  # 020
                "input_voltage_range": values_array[15],  # 1  # from docs: 0: appliance 1: UPS
                "output_source_priority": self._output_source_priority_map[values_array[16]], # from docs: 0: utility first 1: solar first 2: sbu first should check this on my unit  
                "charger_source_priority": self._charger_source_priority_map[values_array[17]], # from docs: 0: utility first 1: solar first 2: solar + utility 3: only solar charging first should check this on my unit  
                "parrallel_max_num": values_array[18], # from docs: 0: utility first 1: solar first 2: solar + utility 3: only solar charging first should check this on my unit  
                "machine_type": values_array[19], # from docs: 00: grid_tie 01: off_grid 10: hybrid  
                "topology": values_array[20], # from docs: 0: transformerless 1: transformer
                "output_mode": values_array[21], # from docs: 00: single 01: parallel 02: Phase 1 of 3 03: Phase 2 of 3 04: Phase 3 of 3  7 would be phase 2 of 2 180* 
                "battery_redischarge_voltage": values_array[22],  # 53.0
                "pv_ok_condition_for_parallel": values_array[23],  # 0: pv is ok if any inverter has solar  1: all inverters must have PV for solar
                "pv_power_balance": values_array[24],  # 0: pv max input is charge current  1: pv input is the max charge power + current load
                "25": values_array[25],  # 480   # not in docs
                "26": values_array[26],  # 0   # not in docs
                "27": values_array[27],  # 000   # not in docs
            }
            pprint.pprint(values)
            keys_to_send =  ["battery_recharge_voltage", "max_ac_charging_current", "current_max_charging_current", "output_source_priority", "charger_source_priority", "output_mode"]
            self._publish_mqtt_from_dict(values, keys_to_send)
        else:
            raise InvalidResponseException("Invalid response to QMOD query received: {}".format(msg))
        return

class QueryFlags(Query):
    def __init__(self, connection):
        # b'(EkxyzDabjuv'
        # I believe the letters after E are enabled and the letters after D are disabled
        Query.__init__(self, b"QFLAG", connection)
        return

class QueryPIGS(Query):
    def __init__(self, connection):
        Query.__init__(self, b"QPIGS", connection)
        return

    def process_response(self, msg):
        Query.process_response(self, msg)
        # TODO: update this to make it easier to add different device versions
        if len(msg) >= 70 and msg[0].to_bytes(1) == b'(':
            values_array = msg[1:].decode('ascii').split(" ")
            # 0     1    2     3    4    5    6   7   8     9   10  11   12   13    14    15    16       17 18 19    20
            # 120.4 59.9 120.4 59.9 1575 1481 024 232 53.70 000 100 0041 00.0 000.0 00.00 00000 00010000 00 00 00000 010
            # 118.9 60.0 118.9 60.0 1545 1424 023 232 53.60 000 099 0040 00.0 000.0 00.00 00000 00010000 00 00 00000 010
            values = {
                "grid_voltage": float(values_array[0]),  
                "grid_frequency": float(values_array[1]),
                "output_voltage": float(values_array[2]),
                "output_frequency": float(values_array[3]),
                "output_va": float(values_array[4]),
                "output_w": float(values_array[5]),
                "output_load_percent": float(values_array[6]),
                "bus_voltage": float(values_array[7]),
                "battery_voltage": float(values_array[8]),
                "battery_charging_current": float(values_array[9]),
                "battery_SOC": float(values_array[10]),
                "inverter_heatsink_temp": float(values_array[11]),
                "12": values_array[12],
                "13": values_array[13],
                "battery_voltage_scc_maybe": values_array[14],
                "battery_discharging_current": float(values_array[15]),
                "device_status_bitmap": values_array[16],
                "17": values_array[17],
                "18": values_array[18],
                "19": values_array[19],
                "20": values_array[20],
            }
            pprint.pprint(values)
            keys_to_send =  ["grid_voltage", "grid_frequency", "output_voltage", "output_frequency", "output_va", "output_w", "output_load_percent", "bus_voltage", "battery_voltage", "battery_charging_current", "battery_SOC", "inverter_heatsink_temp", "battery_discharging_current"]
            self._publish_mqtt_from_dict(values, keys_to_send)
            
        else:
            raise InvalidResponseException("Invalid response to QMOD query received: {}".format(msg))
        return

class QueryMode(Query):
    def __init__(self, connection):
        Query.__init__(self, b"QMOD", connection)
        return

    def process_response(self, msg):
        print("Got a response for QMOD message {} it was: {}".format(self.get_key(), msg))
        if len(msg) == 2 and msg[0].to_bytes(1) == b'(':
            mode = msg[1].to_bytes(1).decode('ascii')
            modes = {
                'P': "power_on",
                'S': "standby",
                'L': "line",
                'B': "battery",
                'F': "fault",
                'H': "power_saving",
            }
            if mode in modes.keys():
                mode = modes[mode]
            print("Mode is: {}".format(mode))
            self._connection.publish_message("mode", mode)
        else:
            raise InvalidResponseException("Invalid response to QMOD query received: {}".format(msg))
        return

class QueryWarnings(Query):
    def __init__(self, connection):
        #    0    5    10   16   20
        # b'(100000000000000001000000000000000000'
        # individual bits are flag for warnings
        Query.__init__(self, b"QPIWS", connection)
        return

class VoltronicConnection(threading.Thread):
    def __init__(self, connection, address, mqtt_client=None):
        threading.Thread.__init__(self)

        self._connection = connection
        self._address = address
        self._exit_request = False
        self._to_send = []
        self._recv_buffer = bytearray()
        self._query_counter = random.randint(100, 90000) & 0xFFFF
        self._queries_lock = threading.Lock()
        self._queries = {}

        self._last_sent_time = time.time()
        self._invalidresponse_count = 0

        self._wifi_serial_number = None
        self._inverter_serial_number = None
        self._protocol_version = None
        self._firmware_versions = {}

        self._mqtt_client = mqtt_client
        return
    
    def register_serial_number(self, serial_number):
        # set serial number and register with mqtt

        if self._mqtt_client is not None:
            if self._inverter_serial_number is not None:
                self._mqtt_client.unregister_message_callback(self.handle_mqtt_message, "{}/command".format(self._inverter_serial_number))
            self._mqtt_client.register_message_callback(self.handle_mqtt_message, "{}/command".format(serial_number))
        
        self._inverter_serial_number = serial_number
        return
    
    def _cleanup_old_queries(self):
        # clean up any messages that didn't get a response
        keys_to_remove = []
        for key in self._queries.keys():
            if self._queries[key].should_give_up():
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self._queries.pop(key)
        return
    
    def publish_message(self, topicpart, message):
        # publish a message inside the base topic area
        if self._mqtt_client is None:
            raise Exception("Can't publish mqtt message, this connection has no mqtt client registered")
        if self._inverter_serial_number is None:
            raise Exception("Can't publish mqtt message, this connection hasn't discovered it's serial number yet")
        self._mqtt_client.publish_message("{}/{}".format(self._inverter_serial_number, topicpart), message)
        return
    
    def handle_mqtt_message(self, msg):
        print("got message in voltronic, topic: {}, message: {}".format(msg.topic, msg.payload))
        with self._queries_lock:
            payload = msg.payload.decode('ascii')
            if msg.topic.endswith("command/set_output_priority"):
                print("Reqesting Output Priority to be: {}".format(payload))
                self._to_send.append(SetOutputPriority(payload, self))
            elif msg.topic.endswith("command/set_charge_priority"):
                print("Reqesting Charging Priority to be: {}".format(payload))
                self._to_send.append(SetChargePriority(payload, self))

        return

    def run(self):
        print("New connection from address {}".format(pprint.pformat(self._address)))
        self._connection.settimeout(0.1)
        try:
            while not self._exit_request and self._invalidresponse_count < 10:
                try:
                    self._queue_messages_to_send()
                    if len(self._to_send) > 0:
                        if (len(self._queries) - len(self._to_send)) < 1:
                            # inverter appears to be sensitive to getting more than one or two command at once, so limit the send
                            query = self._to_send.pop(0)
                            msg = query.get_packaged_message()
                            self._connection.sendall(msg)
                            print("sent: {}".format(msg))
                        else:
                            self._cleanup_old_queries()

                    data = self._connection.recv(2000)
                    self._recv_buffer.extend(data)

                    while self._recv_message():
                        print("received a message")
                except socket.timeout:
                    pass
                except BrokenPipeError:
                    print("Connection from address {} has dropped".format(pprint.pformat(self._address)))
                    break
                except InvalidResponseException:
                    print(traceback.format_exc())
                    self._invalidresponse_count += 1
                except:
                    raise
            if self._invalidresponse_count > 10:
                # wait for shutdown to try to let the inverter settle
                time.sleep(10)
            # try to shut down the connection since we're exiting
            try:
                self._connection.shutdown(socket.SHUT_RDWR)
            except:
                pass        
        finally:
            print("closing connection for address {}".format(pprint.pformat(self._address)))
            self._connection.close()        
        return
    
    def _recv_message(self):
        # return true if we popped a message successfully
        successful_message = False
        # check if the buffer contains the signature of a message
        if len(self._recv_buffer) > 10:
            if self._recv_buffer[2:4] == b'\x00\x01' and (self._recv_buffer[6:8] == b'\xff\x04' or self._recv_buffer[6:8] == b'\x01\x04'):
                # this looks like a valid header, check length
                expected_length = (int.from_bytes(self._recv_buffer[4:6], "big") + 6)
                if len(self._recv_buffer) >= expected_length:
                    self._handle_message(self._recv_buffer[0:expected_length])
                    self._recv_buffer = self._recv_buffer[expected_length:]
                    successful_message = True
            else:
                #TODO: throw away data until we match the signature of a message start
                print("message signature not met, will probably loop forever")

        return successful_message

    def _handle_message(self, msg):
        # confirm the CRC on the message and parse
        crc = voltronic_tools.cal_crc_half(msg[8:-3])
        if crc != msg[-3:-1]:
            print("Failed CRC buffer contained: {}".format(msg))
            raise InvalidResponseException("CRC of received message doesn't match")

        if bytes(msg[0:2]) not in self._queries.keys():
            print("got a message we don't have a query for ({}); ignoring".format(msg[0:2]))
        else:
            query = self._queries.pop(bytes(msg[0:2]))
            print("Size of queries is: {}".format(len(self._queries)))
            query.process_response(msg[8:-3])

        return

    def _queue_messages_to_send(self):
        # check the timer and queue of ready
        if (time.time() - self._last_sent_time) > 5:
            with self._queries_lock:
                if self._protocol_version is None:
                    self._to_send.append(QueryProtocolID(self))
                elif self._inverter_serial_number is None:
                    self._to_send.append(QuerySerial(self))
                elif len(self._firmware_versions) < 2:
                    self._to_send.append(QueryFirmware(self))
                    self._to_send.append(QueryFirmware(self, b'2'))
                    self._to_send.append(QueryFirmware(self, b'3'))
                else:
                    for theclass in [QueryPIRI, QueryFlags, QueryPIGS, QueryMode, QueryWarnings]:
                        self._to_send.append(theclass(self))

                self._last_sent_time = time.time()
                print("queued messages")

        return

    def exit(self):
        self._exit_request = True
        return


class VoltronicServer(threading.Thread):
    def __init__(self, portnumber):
        threading.Thread.__init__(self)

        self._portnumber = portnumber
        self._exit_request = False
        self._inverter_connections = []

        self._mqtt_client = None
        return
    
    def register_mqtt(self, mqtt_client):
        self._mqtt_client = mqtt_client
        return

    def run(self):
        # create and start listening on the socket
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.bind(("0.0.0.0", self._portnumber))
            self._sock.settimeout(1) 
            self._sock.listen()

            while not self._exit_request:
                try:
                    connection, addr = self._sock.accept()
                    inverter_connection = VoltronicConnection(connection, addr, mqtt_client=self._mqtt_client)
                    self._inverter_connections.append(inverter_connection)
                    inverter_connection.start()
                except socket.timeout:
                    pass
                except:
                    raise

                print("waiting")
            try:
                self.shutdown_inverter_connections()
            except:
                pass
            self._sock.shutdown(socket.SHUT_RDWR)

        finally:
            print("closing socket connection")
            self._sock.close()
        return

    def shutdown_inverter_connections(self):
        # TODO: add ability to remove from connection list
        for inverter_connection in self._inverter_connections:
            inverter_connection.exit()
        for inverter_connection in self._inverter_connections:
            inverter_connection.join()
        return

    def exit(self):
        self._exit_request = True
        return


if __name__ == "__main__":
    # test server directly
    testserver = VoltronicServer(3502)
    testserver.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        testserver.exit()
    testserver.exit()
    testserver.join()
