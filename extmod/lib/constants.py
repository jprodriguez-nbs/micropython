import machine



MACHINE_IRQ_WAKE = {
    #machine.IDLE: "IDLE",
    machine.SLEEP: "SLEEP",
    machine.DEEPSLEEP: "DEEPSLEEP",
}


MACHINE_RESERT_CAUSES = {
    machine.PWRON_RESET: "PWRON_RESET",
    machine.HARD_RESET: "HARD_RESET",
    machine.WDT_RESET: "WDT_RESET",
    machine.DEEPSLEEP_RESET: "DEEPSLEEP_RESET",
    machine.SOFT_RESET: "SOFT_RESET",
}

MACHINE_WAKE_UP_REASONS = {
    0: "RESET",
    1: "WAKE 1",
    machine.EXT0_WAKE: "EXT0_WAKE",
    machine.EXT1_WAKE: "EXT1_WAKE",
    machine.PIN_WAKE: "PIN_WAKE",
    machine.TIMER_WAKE: "TIMER_WAKE",
    machine.TOUCHPAD_WAKE: "TOUCHPAD_WAKE",
    machine.ULP_WAKE: "ULP_WAKE",
}



class UmdcEvents():

    VALUE_LOW = 0
    VALUE_NORMAL = 1
    VALUE_HIGH = 2

    STATUS_OFF = 0 # Also means disabled, finished
    STATUS_ON = 1 # Also means enabled, started

    STATUS_DISABLED = STATUS_OFF
    STATUS_ENABLED = STATUS_ON

    STATUS_FINISHED = STATUS_OFF
    STATUS_STARTED = STATUS_ON
    STATUS_CHANGED = 3

    # INPUTS
    AC220 = "ac"                # 220 AC power input
    MCB = "mcb"                 # Main Circuit Breaker (on input 1)
    BATTERY = "battery"         # Battery

    # CYCLES
    Wake = "wake"

    # Alarms
    Alarm = "alarm"


FW_VERSION="1.0.0"


K_ID = "id"
K_TZ = "tz"
K_WIFI = "wifi"
K_AP = "ap"
K_SSID = "ssid"
K_AGENT = "agent"
K_PROTOCOL = "protocol"
K_MQTT_BROKER_HOST = "mqtt_host"
K_MQTT_BROKER_PORT = "mqtt_port"
K_MQTT_USER = "mqtt_user"
K_MQTT_PSW = "mqtt_psw"
K_AGENT_INT = "agent_int"
K_AGENT_EXT = "agent_ext"
K_NTP = "ntp"
K_GPRS = "gprs"
K_APN = "apn"
K_USER = "user"
K_PSW = "psw"
K_ICCID = "iccid"

K_UPDATE_HOST = "update_host"
K_UPDATE_HOST_TYPE = "update_host_type"

K_TYPE = "type"
K_ADVANCED = "advanced"
K_WAKENING_PERIOD = "wakening_period_s"


K_CONFIG = "Config"
K_COMMAND = "Command"
K_MODBUS_REQUEST = "Modbus_Request"

K_CLOCK = "Clock"
K_RS485 = "RS485"
K_IOS = "IOs"
K_EI = "External_Inputs"
K_MESSAGES = "Messages"
K_ACQUISITION_TIME = "acquisition_time"
K_REPORT_TIME = "report_time"
K_REQUESTS = "requests"
K_DEBUG = "Debug"


K_OUTPUTS = "Outputs"
K_UPDATE = "Update"
K_RESET = "Reset"

# time shift from UTC to calculate local time, measured in hours
K_ADV_UTC_SHIFT = "utc_shift"

# Minimum battery level to activate the LOW alarm
K_ADV_V_BATT_LOW = "vbatt_low"

# Minimum battery level to activate the DEAD alarm
K_ADV_V_BATT_DEAD = "vbatt_dead"


KEY_START = "start"
KEY_END = "end"
KEY_DURATION = "duration"
KEY_VBATT = "vbatt"


KEY_STATUS = "status"
KEY_TS = "ts"
KEY_POWER = "power"
KEY_LAST_UPDATE_CHECK = "last_update_check"
KEY_ALARM = "alarm"
KEY_DIO = "dio"
KEY_AI1 = "ai1"
KEY_AI2 = "ai2"


EVENT_KEY_TYPE = "idevent"
EVENT_KEY_VALUE = "value"
EVENT_KEY_EXTRADATA = "extradata"


GET_HEADERS = {"Connection": "close"}
POST_HEADERS = {
    'content-type': 'application/json',
    "Connection": "close"
    }

"""
GET_HEADERS = {}
POST_HEADERS = {
    'content-type': 'application/json'
    }
"""


FN_STORED_MQTT_MESSAGES = "mqtt_messages.dat"
FN_CHECK_UPDATE = "check_update.dat"


D_SERIAL_FORMAT = {
    "0": {
      "format": "8n2",
      "bits": 8,
      "parity": None,
      "stop": 2,
      "desc": "No Parity 2Stop bits"
    },
    "1": {
      "format": "8o1",
      "bits": 8,
      "parity": 1,
      "stop": 1,
      "desc": "Odd Parity 1Stop bit"
      
    },
    "2": {
      "format": "8e1",
      "bits": 8,
      "parity": 0,
      "stop": 1,
      "desc": "Even Parity 1Stop bit"
    },
    "3": {
      "format": "8n1",
      "bits": 8,
      "parity": None,
      "stop": 1,
      "desc": "No Parity 1Stop bit"
    },
    "4": {
      "format": "8o2",
      "bits": 8,
      "parity": 1,
      "stop": 2,
      "desc": "Odd Parity 2Stop bits"
    },
    "5": {
      "format": "8e2",
      "bits": 8,
      "parity": 0,
      "stop": 2,
      "desc": "Even Parity 2Stop bits"
    }
}

def parity2str(p):
  if p is None:
    return "None"
  elif p == 0:
    return "Even"
  elif p == 1:
    return "Odd"
  else:
    return "Unknown" 