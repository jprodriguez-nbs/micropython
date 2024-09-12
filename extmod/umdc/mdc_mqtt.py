#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# cython: language_level=3


import gc
import micropython
import machine
import tools
print("UMdcMqttParser")
tools.free(True)


import sys
#import json
#import re
#import binascii
import time
import datetime


import logging
import tools

class MdcMqttParser(object):

    #
    # Class-level properties
    #
    
    _logger = logging.getLogger("MdcMqttParser")
       
    
    #
    # Class-level constants
    #
    
    # Base topics
    # Field device to sever: GW_Energy_Exa/ICCID/MessageType
    # Server to field device: GW_Energy_CLNX_Server/ICCID/MessageType
    # ICCID is the unique identifier of the SIM card that the field device (gateway) uses to communicate with the network. It is used to identify the field device
    
    UP_TOPIC = 'GW_Energy_Exa'              # Used by the GW (field device) to publish to the PT-MDC-PRO server
    DOWN_TOPIC = 'GW_Energy_CLNX_Server'    # Used by the PT-MDC-PRO to publish to the GWs (field devices)
    
    
    # UP MESSAGE TYPES 
    
    
    IDENTIFICATION_MSG  = 'Idetification'
    STATUS_MSG          = 'Status' 
    CONFIG_REQUEST_MSG  = 'ConfigRequest'
    REPORT_MSG          = 'Report'
    
    
    MODBUS_RESPONSE_MSG = 'Modbus_Response'
    
    # Regular expression to get iccid and message type from uplink topic
    # First group is iccid
    # Second group is the message type
    UP_TOPIC_RE_PATTERN = UP_TOPIC+'\/(\w*)\/(\w*)'
    
    
    # DOWN MESSAGE TYPES (use format to replace iccid with the corresponding one)
    # CONFIG
    CONFIG_CLOCK_MSG = DOWN_TOPIC+'/{iccid}/Config/Clock'
    CONFIG_RS485_MSG = DOWN_TOPIC+'/{iccid}/Config/RS485' 
    CONFIG_IOS_MSG = DOWN_TOPIC+'/{iccid}/Config/IOs'
    CONFIG_EXT_INPUTS_MSG = DOWN_TOPIC+'/{iccid}/Config/External_Inputs'
    CONFIG_MESSAGES_MSG = DOWN_TOPIC+'/{iccid}/Config/Messages'
    
    #COMMAND
    COMMAND_OUTPUTS_MSG = DOWN_TOPIC+'/{iccid}/Command/Outputs'
    COMMAND_UPDATE_MSG = DOWN_TOPIC+'/{iccid}/Command/Update'
    COMMAND_RESET_MSG = DOWN_TOPIC+'/{iccid}/Command/Reset'
    COMMAND_MB_REQUEST_MSG = DOWN_TOPIC+'/{iccid}/Command/Modbus_Request'
    
    # Other constants
    DT_2019 = datetime.datetime(2019,1,1,0,0,0)  # 01/01/2019 at 00:00:00.
    
    # RS485 Configuration - Format
    RS485_FORMAT_NOP_2S  = 0 # No No Parity 2Stop bits
    RS485_FORMAT_ODD_1S  = 1 # Odd Parity 1Stop bit
    RS485_FORMAT_EVEN_1S = 2 # Even Parity 1Stop bit
    RS485_FORMAT_NOP_1S  = 3 # No Parity 1Stop bit
    RS485_FORMAT_ODD_2S  = 4 # Odd Parity 2Stop bits
    RS485_FORMAT_EVEN_2S = 5 # Even Parity 2Stop bits
 
    rtc = machine.RTC()
    
    def __init__(self):
        super(MdcMqttParser, self)

    
    
    ###################################
    #
    # Methods to build messages
    #
    ###################################
    
    
    @classmethod
    def decode_config_clock(cls, id, data):
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)<2:
                msg = "Invalid config_clock message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                'timestamp': int(parts[0]),
                'minute_within_hour': int(parts[1])
            }
            
            
        else:
            msg = "Invalid config_clock message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
    @classmethod
    def dt_now(cls):
        dt_tuple = cls.rtc.datetime()
        # (year, month, mday, week_of_year, hour, minute, second, milisecond)
        dt =datetime.datetime(dt_tuple[0],dt_tuple[1],dt_tuple[2],dt_tuple[4],dt_tuple[5],dt_tuple[6],dt_tuple[6]*1000)
        return dt
    
    @classmethod
    def time_since_2019(cls):
        ts = None
        minute_within_hour = None
        try:
            #now = datetime.datetime.utcnow()
            #minute_within_hour = now.minute
            now = cls.dt_now()
            dt_tuple = cls.rtc.datetime()
            # (year, month, mday, week_of_year, hour, minute, second, milisecond)
            minute_within_hour = int(dt_tuple[5])
            ts = int((now - MdcMqttParser.DT_2019).total_seconds())
        except Exception as ex:
            cls._logger.exc(ex,"time_since_2019")
        return (ts, minute_within_hour)
    
    @classmethod
    def time_since_2019_to_datetime(cls, ts_2019):
        dt_unix = MdcMqttParser.DT_2019 + datetime.timedelta(0,ts_2019)
        return dt_unix

    @classmethod
    def decode_config_rs485(cls, id, data):    
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)<2:
                msg = "Invalid config_rs485 message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                'baud': parts[0],
                'format': parts[1]
            }
            
            
        else:
            msg = "Invalid config_rs485 message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
    

    @classmethod
    def decode_config_external_inputs(cls, id, data):
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)<2:
                msg = "Invalid config_external_inputs message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                    'ext_inputs_id1': parts[0],
                    'ext_inputs_id2': parts[1]
                }
            
            
        else:
            msg = "Invalid config_external_inputs message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
   
    
    @classmethod
    def decode_config_messages(cls, id, data):        
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)<4:
                msg = "Invalid config_messages message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                    'timestamp': parts[0],
                    'minute_within_hour': parts[1],
                    'acquisition_time': parts[2],
                    'report_time': parts[3],
                    'requests': parts[4:]
                }
            
            
        else:
            msg = "Invalid config_messages message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    

    
     
    @classmethod
    def decode_command_outputs(cls, id, data):

        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)!=3:
                msg = "Invalid command_outputs message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                    'output_1': int(parts[0]),
                    'output_2': int(parts[1]),
                    'output_3': int(parts[2])
                }
            
            
        else:
            msg = "Invalid command_outputs message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
    
    
    @classmethod
    def decode_command_update(cls, id, data):
        
        result = None
   
        if data != '{}':
            msg = "Invalid command_update message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
    
    
    @classmethod
    def decode_command_reset(cls, id, data):     
        result = None
   
        if data != '{}':
            msg = "Invalid command_reset message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
        
    
    @classmethod
    def decode_modbus_request(cls, id, data):
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)!=1:
                msg = "Invalid modbus_request message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                    'request': parts[0]
                }
            
            
        else:
            msg = "Invalid modbus_request message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    
      
    @classmethod  
    def decode_debug_config(cls, id, data):
        result = None
        parts = tools.get_parts(data)
        
        if parts is not None:
            if len(parts)!=4:
                msg = "Invalid debug_config message from '{id}': '{data}'".format(id=id, data=data)
                raise Exception(msg)
            
            result = {
                    'send_ping': True if int(parts[0])==1 else False,
                    'send_traces': True if int(parts[1])==1 else False,
                    'modbus_debug_level': int(parts[2]),
                    'send_status': True if int(parts[3])==1 else False
                }
            
            
        else:
            msg = "Invalid debug_config message from '{id}': '{data}'".format(id=id, data=data)
            raise Exception(msg)
        
        return result
    