# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    ".",
    (

        "constants.py",
        "umdc_config.py",

        "utils/httpclient.py",
        "utils/ota_logger.py",
        "utils/ota_updater.py",
        "utils/update_utils.py",

        "test/planter_modbus.py",

        "arequests.py",
        "async_SIM800L.py",        
        "colors.py",
        "logging.py",

        "modem.py",
        "mqtt_as.py",
        "mqtt_as_timeout.py",
        "networkmgr.py",

        "nsClassWriter.py",
        "nsDataClass.py",
        "nsUmdcStatusData.py",
        
        "switch.py",
        "time_it.py",
        "timetools.py",
        "tools.py",
        "ubutton.py",
        "uping.py",
        "wifimgr.py",
        
        "umdc/__init__.py",
        "umdc/comm.py",
        "umdc/core.py",
        "umdc/mb_task.py",
        "umdc/mqtt_task.py",
        "umdc/status.py",
        "umdc/mdc_mqtt.py",
    ),
    opt=3,
)

