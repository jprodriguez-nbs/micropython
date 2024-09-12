# https://github.com/peterhinch/micropython-mqtt/tree/master/mqtt_as


import gc
import micropython
import machine
import tools
print("UMDC MQTT Task")
tools.free(True)

#import esp32
#import os

import  asyncio
import logging
import colors
#import ubinascii
#import ntptime
import utime

import umdc_pinout as PINOUT

if PINOUT.PING_ENABLED:
    import uping

import umdc.mdc_mqtt as mdc_mqtt
gc.collect()
print("Load mqtt_as")
from mqtt_as_timeout import MQTTClient
from mqtt_as import config
#import ssl as ssl
print("mqtt_as loaded")
gc.collect()

if PINOUT.IMPORT_FROM_APP:
    import frozen.umdc_config as CFG
    import app.umdc.mb_task as mb_task
    import app.umdc.comm as comm
else:
    import umdc_config as CFG
    import umdc.mb_task as mb_task
    import umdc.comm as comm

from constants import *

#from primitives import queue
#import deflate
import json



gc.collect()

class MqttTask(object):

    
    def set_mqtt_cb(self, coro):
        self._mqtt_cb = coro
    
    async def mqtt_send_identity(self, client, core):
        iccid = None
        imei = None
        revision = None
        if core:
            if core.networkMgr:
                n = core.networkMgr
                iccid = n._iccid
                imei = n._imei
                revision = n._revision
                
        identity_payload = '{{{sn};{hw_ver};{fw_ver};{imei};{modem_model_fw_sw_vr}}}'.format(
                sn =  iccid,
                hw_ver = 'hw_ver',
                fw_ver = 'fw_ver',
                imei = imei,
                modem_model_fw_sw_vr = revision
        )
        await self.mqtt_send(client, 'Identification', identity_payload)

    
    async def mqtt_request_config(self, client):
        request_payload = mdc_mqtt.MdcMqttParser.encode_config_request(None)
        await self.mqtt_send(client, 'Config_Request', request_payload)


    
    async def mqtt_send_status(self, client):
        
        self._ts_last_status_sent = utime.time()
        
        (timestamp, minute_within_hour) = mdc_mqtt.MdcMqttParser.time_since_2019()
        
        if self._status is not None:
            battery = self._status.battery
            low_bat = self._status.low_bat
            temp = self._status.temp
            supply_fail = 0 if self._status.ac220 else 1
            di1 = 1 if self._status.di1 else 0
            di2 = 1 if self._status.di2 else 0
            slave_fail = self._status.mb_slave_fail
            reset_count = self._status.reset_count
            socket_time_alive = self._status.socket_time_alive
            socket_time_down = self._status.socket_time_down
        else:
            battery = 0
            low_bat = False
            temp = 0
            supply_fail = 0
            di1 = 0
            di2 = 0
            slave_fail = 0
            reset_count = 0
            socket_time_alive = 0
            socket_time_down = 0
            
        rssi = self._networkMgr.rssi()
        
        status_payload = '{{{battery};{timestamp};{temp};{rssi};{con_tech};{low_bat};{supply_fail};{slave_fail};{input_1};{input_2};{input_3};{reset_count};{socket_time_alive};{socket_time_down}}}'.format(
            battery=battery, 
            timestamp = timestamp,
            temp=temp, 
            rssi=rssi or -115, 
            con_tech = 'GSM',
            low_bat = low_bat,
            supply_fail = supply_fail,
            slave_fail = slave_fail,
            input_1 = di1,
            input_2 = di2,
            input_3 = 0,
            reset_count = reset_count,
            socket_time_alive = socket_time_alive,
            socket_time_down = socket_time_down
        )
        
        await self.mqtt_send(client, 'Status', status_payload, store_if_not_sent=True)


    async def send_modbus_response(self, response):
        payload = '{{{response}}}'.format(response=response)
        await self.mqtt_send(self._mqtt, 'Modbus_Response', payload)
        
    async def send_report(self, ts, li_responses):
        try:
            if self._status:
                batt = self._status.battery
            else:
                batt = 0
            try:
                valid_responses = [i for i in li_responses if i is not None]
                responses_str = ";".join([i for i in li_responses if i is not None])
            except Exception as ex:
                responses_str = ""
                debug_msg = "mqtt_task.send_report failed to join responses '{l}' ({t})".format(l=str(li_responses), t=str(type(li_responses)))
                self._logger.exc(ex,debug_msg)
                
            payload = '{{{batt};{ts};{responses}}}'.format(batt=batt, ts=ts, responses=responses_str)
            await self.mqtt_send(self._mqtt, 'Report', payload, store_if_not_sent=True)
        except Exception as ex:
            responses_str = ""
            debug_msg = "mqtt_task.send_report failed"
            self._logger.exc(ex,debug_msg)

    async def mqtt_request_config(self, client):
        await self.mqtt_send(client, 'Config_Request', '{}')

    
    async def mqtt_subscribe(self, client, core):
        
        topic = "{b}#".format(b=self._topic_base)
        self._logger.debug("Subscribe to MQTT topic {t}".format(t=topic))
        #self._mqtt.subscribe(b"#")
        await client.subscribe(topic.encode('utf-8'), 1) # Renew subscription
        
        ts_now = utime.time()
        self._mqtt_last_subscription_ts = ts_now

        # Send identity
        await self.mqtt_send_identity(client, core)

        # Send status
        await self.mqtt_send_status(client)
        
        # Request configuration
        await self.mqtt_request_config(client)


    async def get_connection_status(self, client):
        isconnected = False
        broker_up = False
        sock_connection_attempts = 0
        if client is not None:
            try:
                isconnected = client.isconnected()
                broker_up = await client.broker_up()
                sock_connection_attempts = client.sock_connection_attempts
            except:
                pass
        
        c_str = "{g}connected{n}".format(g=colors.BOLD_GREEN, n=colors.NORMAL) if isconnected else "{r}not connected{n}".format(r=colors.BOLD_RED, n=colors.NORMAL)
        if isconnected:
            b_str = "{g}UP{n}".format(g=colors.BOLD_GREEN, n=colors.NORMAL) if broker_up else "{r}DOWN{n}, {nb} attempts to connect".format(r=colors.BOLD_RED, n=colors.NORMAL, nb=sock_connection_attempts)
        else:
            b_str = "{r}UNKNOWN{n}".format(r=colors.BOLD_RED, n=colors.NORMAL)
        
        is_up = isconnected and broker_up
        
        if sock_connection_attempts > 10:
            print("Reboot because sock_connection_attempts is {v}".format(v=sock_connection_attempts))
            tools.do_reboot()
        
        return (is_up, c_str, b_str)
    
    async def store_message(self, topic, payload):
        try:
            await self._store_lock.acquire()
            o = {'t':topic, 'p':payload}
            o_str = json.dumps(o)+"\r\n"
            fn = FN_STORED_MQTT_MESSAGES
            with open(fn, "ab") as f:
                    try:
                        f.write(o_str)
                    except Exception as ex:  # open failed
                        self._logger.exc(ex, "Failed to write in append_to_file '{fn}'".format(fn=fn))
        except Exception as ex:  # open failed
            self._logger.exc(ex, "Failed to append_to_file '{fn}'".format(fn=fn))
        finally:
            self._store_lock.release()
        gc.collect()

    
    async def send_stored_messages(self, client):
        try:
            fn = FN_STORED_MQTT_MESSAGES
            await self._store_lock.acquire()
            self._ts_last_stored_messages_check = utime.time()
            
            (is_up, c_str, b_str) = await self.get_connection_status(client)
            if is_up:
                
                if tools.file_exists(fn):
                    self._logger.debug("Send messages stored in {fn}".format(fn=fn))
                    all_ok = True
                    with open(fn, "rb") as f:
                        while all_ok:
                            l = f.readline()
                            if not l:
                                break
                            else:
                                # unpack
                                o = json.loads(l)
                                topic = o['t']
                                payload = o['p']
                                # send
                                try:
                                    self._logger.debug(" + MQTT send stored message {t} - {p}".format(t=topic, p=payload))
                                    await client.publish(topic, payload, retain=True, qos = 1, timeout = 2500)
                                except asyncio.TimeoutError as ex:
                                    # Failed to publish the message in the provided time
                                    self._logger.error ("Failed to publish to {topic} because a timeout".format(topic=topic))   
                                    all_ok = False  
                        if all_ok is False:
                            # Error -> do not remove the sent messages, we will send them again
                            pass
                            
                    if all_ok:
                        self._logger.debug("Remove file {fn}".format(fn=fn))
                        # Clear file
                        import os
                        os.remove(FN_STORED_MQTT_MESSAGES)
                
            
        except Exception as ex:  # open failed
            self._logger.exc(ex, "Failed to send_stored_messages '{fn}'".format(fn=fn))
        finally:
            self._store_lock.release()
        gc.collect()
    
    
    async def mqtt_send(self, client, command, payload, store_if_not_sent=False):
        try:
            topic = "{base}/{iccid}/{command}".format(
                base = mdc_mqtt.MdcMqttParser.UP_TOPIC,
                iccid = self._iccid,
                command=command
                )
            
            try:
                (is_up, c_str, b_str) = await self.get_connection_status(client)
            except Exception as ex:
                is_up = False
                c_str = b_str = "ERROR"
            
            self._logger.debug("{t} -> {payload} | Client {c} Broker {b} -> {a}".format(t=topic, payload=payload, c = c_str, b=b_str, a = "publish" if is_up else "store"))
            
            if is_up:
                try:
                    await client.publish(topic, payload, retain=True, qos = 1, timeout = 2500)
                except asyncio.TimeoutError as ex:
                    # Failed to publish the message in the provided time
                    self._logger.error ("Failed to publish to {topic} because a timeout".format(topic=topic))
                    if store_if_not_sent:
                        await self.store_message(topic, payload)
            else:
                if store_if_not_sent:
                    await self.store_message(topic, payload)
                
        except Exception as ex:
            errorMsg = "mqtt_send Error: {e}".format(e=ex)
            self._logger.exc(ex, errorMsg)

    
    async def set_status(self, status):
        self._status = status


    
    def stop(self):
        self._stop = True

    async def execute_reset(self, core, reason):
        if core:
            self._logger.debug("execute_reset - reason: {r}".format(r=reason))
            await core.do_reset()
        pass

    async def execute_update(self, core):
        if self._status and core:
            self._logger.debug("execute_update")
            self._status._last_update_check = None
            self._status.store_status()
            tools.set_check_update()
            #await self.execute_reset(core)
            # Soft Reset using deepsleep
            #machine.deepsleep(500)
            machine.reset()
            pass  
    
    async def process_messages(self, core, payload):
        try:
            d = mdc_mqtt.MdcMqttParser.decode_config_messages(self._iccid, payload)
            v2 = {
                K_ACQUISITION_TIME: d['acquisition_time'],
                K_REPORT_TIME: d['report_time'],
                K_REQUESTS: d['requests']
            }        
            has_changed = CFG.update_params_key(K_MESSAGES, v2)
            
            self._logger.debug("process_messages: {d} (has_changed={c})".format(d=str(v2), c=has_changed))
            if has_changed:
                if core is not None:
                    core.update_modbus_messages(d)
                else:
                    self._logger.error("process_messages error: core is None")
        except Exception as ex:
            self._logger.exc(ex, "mqtt_task.process_messages error: {e}".format(e=str(ex)))  
            raise
        pass
    
    async def process_outputs(self, payload):
        d = mdc_mqtt.MdcMqttParser.decode_command_outputs(self._iccid, payload)
        if self._core is not None:
            self._core.command_outputs(d)
        pass
    
    async def process_modbus_request(self, core, payload):
        d = mdc_mqtt.MdcMqttParser.decode_modbus_request(self._iccid, payload)
        if core and d:
            await core.modbus_request(d['request'])
        pass
    
    async def set_clock(self, core, payload):
        d = mdc_mqtt.MdcMqttParser.decode_config_clock(self._iccid, payload)
        if core and d:
            await core.set_clock(d['timestamp'])
        
      
    async def process_debug_config(self, core, payload):
        d = mdc_mqtt.MdcMqttParser.decode_debug_config(self._iccid, payload)
        if d:
            self._send_ping = d['send_ping']
            self._send_traces = d['send_traces']
            if d['send_status']:
                self.set_send_status()
            if core:
                core.set_modbus_debug(d['modbus_debug_level'])
        pass
        
    async def messages(self, client, core):  # Respond to incoming messages
        try:
            async for topic, msg, retained in self._mqtt.queue:
                await asyncio.sleep(0)  # Allow other instances to be scheduled
                topic = topic.decode()
                command = topic[self._topic_base_length:]
                payload = msg.decode()
                debug_msg = "{t} -> command='{c}', payload='{p}', retained={r}".format(t=topic, c=command, p=payload, r=retained)
                self._logger.debug(debug_msg)
                

                if self._mqtt_cb is not None:
                    try:
                        # Call the provided callback
                        await self._mqtt_cb(client, topic, payload)
                    except Exception as ex:
                        self._logger.exc(ex, "mqtt_task.messages exeption in callback: {e}".format(e=str(ex)))  
                
                else:
                    unknwon_command = False
                    if K_CONFIG in topic:
                        if K_CLOCK in topic:
                            await self.set_clock(core, payload)
                        elif K_RS485 in topic:
                            has_changed = CFG.update_params_key(K_RS485, payload)
                            if has_changed:
                                await self.execute_reset(core, "RS485 config has changed")   
                        elif K_IOS in topic:
                            has_changed = CFG.update_params_key(K_IOS, payload)
                            if has_changed:
                                await self.execute_reset(core, "IOs config has changed")
                        elif K_EI in topic:
                            has_changed = CFG.update_params_key(K_EI, payload)
                            if has_changed:
                                await self.execute_reset(core, "External Inputs config has changed")
                        elif K_MESSAGES in topic:
                            await self.process_messages(core, payload)
                            pass                

                        else:
                            unknwon_command = True
                            
                    elif K_COMMAND in topic:
                        if K_OUTPUTS in topic:
                            await self.process_outputs(payload)
                        if K_UPDATE in topic:
                            await self.execute_update(core) 
                        if K_RESET in topic:
                            await self.execute_reset(core, "RESET command received from server") 
                    elif K_MODBUS_REQUEST in topic:
                        await self.process_modbus_request(core, payload)
                    elif K_DEBUG in topic:
                        await self.process_debug_config(core, payload)
                        pass  
                    else:
                        unknwon_command = True
                    
                    
                    if unknwon_command:
                        self._logger.error("mqtt_task.messages error: unknown command {c} in topic {t} with message {p}".format(c=command, t=topic, p=msg))  
                
                    
                
        except Exception as ex:
            self._logger.exc(ex, "mqtt_task.messages error: {e}".format(e=str(ex)))  
            raise
        
    
    async def up(self, client, core, f_subscribe):  # Respond to connectivity being (re)established
        try:
            while self._stop is False:
                try:
                    await client.up.wait()  # Wait on an Event
                    client.up.clear()
                    ts_now = utime.time()
                    if self._status:
                        self._status.socket_ts_last_up = ts_now
                        if self._status.socket_ts_last_down is not None and self._status.socket_ts_last_down>0:
                            elapsed_s = ts_now-self._status.socket_ts_last_down
                            if self._status.socket_ts_last_down > 0:
                                if self._status.socket_time_down is not None:
                                    self._status.socket_time_down = self._status.socket_time_down + elapsed_s
                                else: 
                                    self._status.socket_time_down = elapsed_s
                                
                            elapsed_str = "after {e} [s]".format(e=elapsed_s)
                        else:
                            elapsed_str = "for first time"
                    else:
                        elapsed_str=""
                    print('{g}UP{n} -> We are connected to broker {e}.'.format(g=colors.BOLD_GREEN,n=colors.NORMAL,e=elapsed_str))
                    
                    # Subscribe again
                    await f_subscribe(client, core)
                    
                    # Send stored messages
                    await self.send_stored_messages(client)
                except Exception as ex:
                    self._logger.exc(ex, "mqtt_task.up error: {e}".format(e=str(ex)))  
                    raise

                
        except Exception as ex:
            self._logger.exc(ex, "mqtt_task.up error: {e}".format(e=str(ex)))  
            raise

    
    async def down(self, client, core):
        try:
            while True:
                try:
                    await client.down.wait()  # Pause until outage
                    client.down.clear()
                    ts_now = utime.time()
                    if self._status:
                        self._status.socket_ts_last_down = ts_now
                        if self._status.socket_ts_last_up is not None:
                            elapsed_s = ts_now-self._status.socket_ts_last_up
                            if self._status.socket_ts_last_up is not None and self._status.socket_ts_last_up > 0:
                                if self._status.socket_time_alive is not None:
                                    self._status.socket_time_alive = self._status.socket_time_alive + elapsed_s
                                else: 
                                    self._status.socket_time_alive = elapsed_s
                            elapsed_str = "after {e} [s]".format(e=elapsed_s)
                        else:
                            elapsed_str = "for first time"
                    else:
                        elapsed_str =""
                    print('{p}MQTT Connection DOWN{n} -> VPN/WiFi or broker is down {e}.'.format(p=colors.BOLD_PURPLE,n=colors.NORMAL,e=elapsed_str))
                except Exception as ex:
                    self._logger.exc(ex, "mqtt_task.down error: {e}".format(e=str(ex)))  
                    raise
        except Exception as ex:
            self._logger.exc(ex, "mqtt_task.down error: {e}".format(e=str(ex)))  
            raise
            
    
    async def mqtt_task(self):
        try:

            self._logger.debug("MQTT task started - wait for networkMgr to connect")
            while not self._networkMgr.isconnected():
                await asyncio.sleep_ms(1000)
                self._logger.debug("MQTT task waiting for networkmgr to connect")

            aux = self._networkMgr.iccid() 
            if aux is not None:
                self._iccid = aux 

            self._topic_base = "GW_Energy_CLNX_Server/{iccid}/".format(iccid=self._iccid)
            self._topic_base_length = len(self._topic_base)
                    
            self._logger.debug("MQTT task - NetworkMgr is connected - ICCID = {iccid}".format(iccid=self._iccid))
                

                    
            use_ssl = self._mqtt_port == 8883
                    
            config['client_id']=  self._iccid
            config["queue_len"] = 1  # Use event interface with default queue size
            config['server']=  self._mqtt_host
            config['port']=  self._mqtt_port
            config['user']=  self._mqtt_user
            config['password']=  self._mqtt_psw
            config['ssl']=  use_ssl
            config['async']=  False
            MQTTClient.DEBUG = True  # Optional: print diagnostic messages    
            
            if use_ssl:
                ssl_params={
                    'server_hostname':self._mqtt_host}
                config['ssl_params']=  ssl_params
            
            self._logger.debug("MQTT create client")
            
            #self._mqtt = MQTTClient(client_id=self._iccid, server=self._mqtt_host, port=self._mqtt_port, user = None, password = None,ssl = True,keepalive=60)
            self._mqtt = MQTTClient(config, self._networkMgr)
            self._mqtt.DEBUG = True
                    
            while True:
                
                _connection_str = self._networkMgr.connection_str()
                
                if PINOUT.PING_ENABLED:    
                    try:
                        self._logger.debug("\n\nmqtt_task - {c} - Ping server: {h}".format(c=_connection_str, h=self._mqtt_host))
                        #uping.ping(self._mqtt_host)
                        uping.ping(PINOUT.PING_TARGET)
                        tools.free()
                    except Exception as ex:
                        self._logger.error("mqtt_task.ping({h}) error: {e}".format(h=self._mqtt_host, e=str(ex)))  
                
                tools.free()
                
                await comm.get_test()
                
                self._logger.debug("\n\nmqtt_task - {c} - connect to {h}:{p}".format(c=_connection_str, h=self._mqtt_host, p=self._mqtt_port))  
                try:
                    await self._mqtt.connect()
                    break
                except Exception as ex:
                    self._logger.exc(ex, "MQTT task failed to connect. Exception: {e} -> try again".format(e=str(ex)))
                    await comm.get_test()
                
                # Failed to connect: sleep and try again
                asyncio.sleep(1)
            
            if "up" not in self._tasks:
                self._tasks["up"] = asyncio.create_task(self.up(self._mqtt, self._core, self.mqtt_subscribe))
            if "message" not in self._tasks:
                self._tasks["message"] = asyncio.create_task(self.messages(self._mqtt, self._core))
            if "down" not in self._tasks:
                self._tasks["down"] = asyncio.create_task(self.down(self._mqtt, self._core))
                
                
            idx = 0
            connection_down_count = 0
            max_connection_down_count = 240
            while (self._stop is False):
                            
                try:
                    await asyncio.sleep_ms(500)
                    if PINOUT.WDT_ENABLED:
                        #self._wdt.feed()
                        pass
                    (is_up, c_str, b_str) = await self.get_connection_status(self._mqtt)
                    if is_up:
                        connection_down_count = 0
                        try:
                            if self._send_ping:
                                # Send ping to test connection
                                idx += 1
                                if idx > 20:
                                    payload = tools.ping_payload(mb_task._di_slave_ok)
                                    await self.mqtt_send(self._mqtt, 'Ping', payload)
                                    idx = 0
                        except Exception as ex:
                            print(str(ex))
                            pass
                        
                        
                        try:
                            # Send status periodically
                            ts_now = utime.time()
                            if self._ts_last_status_sent is None:
                                self.send_status_event.set()
                            else:
                                elapsed_since_last_status = ts_now - self._ts_last_status_sent
                                if elapsed_since_last_status > PINOUT.STATUS_REFRESH_PERIOD_S:
                                    self.send_status_event.set()
                            
                            # Check if status needs to be sent
                            if self.send_status_event.is_set():
                                self.send_status_event.clear()
                                await self.mqtt_send_status(self._mqtt)
                        except Exception as ex:
                            print(str(ex))
                            pass
                        
                        try:
                            # Check stored messages periodically
                            if self._ts_last_stored_messages_check is None:
                                self.check_stored_messages.set()
                            else:
                                elapsed_since_last_stored_messages_check = ts_now - self._ts_last_stored_messages_check
                                if elapsed_since_last_stored_messages_check > PINOUT.STORED_MESSAGES_CHECK_PERIOD_S:
                                    self.check_stored_messages.set()
                            
                            # Check if status needs to be sent
                            if self.check_stored_messages.is_set():

                                    self.check_stored_messages.clear()
                                    await self.send_stored_messages(self._mqtt)
                        except Exception as ex:
                            print(str(ex))
                            pass
            
                        if self._send_traces:
                            try:
                                traces = logging.get_traces()
                                if traces and len(traces)>0:
                                    payload = json.dumps(traces)
                                    logging.clear_traces()
                                    await self.mqtt_send(self._mqtt, 'Traces', payload)
                            except Exception as ex:
                                print(str(ex))
                                pass
            
                    else:
                        isconnected = self._mqtt.isconnected()
                        if isconnected is False:
                            connection_down_count = connection_down_count + 1
                        if connection_down_count > max_connection_down_count:
                            print("Reboot because connection_down_count is {v}".format(v=connection_down_count))
                            tools.do_reboot()
                
                except Exception as ex:
                    self._logger.exc(ex,"MQTT task exception: {e} -> cycle interrupted".format(e=str(ex)))
        
        except Exception as ex:
            self._logger.exc(ex,"MQTT task exception: {e} -> end task".format(e=str(ex)))
        
        finally:
            if self._mqtt:
                self._mqtt.close()
                self._mqtt = None        
        
        self._logger.debug("Exit MQTT task -> reboot")
        tools.do_reboot()

    def set_send_status(self):
        self.send_status_event.set()

    def __init__(self, core, status, networkMgr):
        super(MqttTask, self).__init__()
        
        self._core = core
        self._status = status
        self._networkMgr = networkMgr

        self._logger = logging.getLogger("MqttTask")
        self._logger.setLevel(logging.DEBUG)

        self._stop = False

        self._mqtt = None
        self._iccid = None
        self.__config = CFG.config()
        self._topic_base = None
        self._topic_base_length = 0
        
        self._store_lock = asyncio.Lock()
        
        try:    
                
            if CFG.K_MQTT_BROKER_PORT in  self.__config:
                self._mqtt_port = self.__config[CFG.K_MQTT_BROKER_PORT]
            else:
                self._mqtt_port = 8883
                
        except Exception as ex:
            self._logger.error("Failed to get MQTT broker port from config: {e}".format(e=str(ex)))
            
        try:    
                
            if CFG.K_MQTT_BROKER_HOST in  self.__config:
                self._mqtt_host = self.__config[CFG.K_MQTT_BROKER_HOST]
            else:
                self._mqtt_host = "intxmdcotp02.sdg.abertistelecom.local"
                
        except Exception as ex:
            self._logger.error("Failed to get MQTT broker host from config: {e}".format(e=str(ex)))
    
        try:    
                
            if CFG.K_MQTT_USER in  self.__config:
                self._mqtt_user = self.__config[CFG.K_MQTT_USER]
            else:
                self._mqtt_user = "exatronic"
                
        except Exception as ex:
            self._logger.error("Failed to get MQTT broker user from config: {e}".format(e=str(ex)))
    
        try:    
                
            if CFG.K_MQTT_PSW in  self.__config:
                self._mqtt_psw = self.__config[CFG.K_MQTT_PSW]
            else:
                self._mqtt_psw = "33xaAt.r0ny0"
                
        except Exception as ex:
            self._logger.error("Failed to get MQTT broker password from config: {e}".format(e=str(ex)))
    
    
        self._mqtt_cb = None

        gc.collect()    
        print(tools.free(True))
        
        self._mqtt_last_subscription_ts = 0
        self._tasks = {}
        #self._queue = queue.Queue(5)
    
        self._config = CFG.config()
        
        if K_GPRS in self._config and K_ICCID in self._config[K_GPRS]:
            self._iccid = self._config[K_GPRS][K_ICCID]
        else:
            self._iccid = None
            
        self.send_status_event = asyncio.Event()
        self.check_stored_messages = asyncio.Event()
        
        self._ts_last_status_sent = None
        self._ts_last_stored_messages_check = None
        
        self._send_ping = True
        self._send_traces = False