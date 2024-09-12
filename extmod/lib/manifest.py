# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    ".",
    (
        "axp202/axp202.py",
        "axp202/constants.py",

        "utils/httpclient.py",
        "utils/ota_logger.py",
        "utils/ota_updater.py",
        "utils/update_utils.py",

        "test/planter_ina3221.py",
        "test/planter_modbus.py",
        "test/planter_modem.py",
        "test/raw_ppp.py",
        "test/test_ppp.py",
        "test/test_water_level.py",
        "test/ulp_counter.py",

        "adxl34x.py",
        "arequests.py",
        "async_SIM800L.py",        
        "colors.py",
        "ina226.py",
        "ina3221.py",
        "logging.py",
        "mc3479.py",
        "mcp23017.py",
        "networkmgr.py",

        "nsClassWriter.py",
        "nsDataClass.py",
        "nsIrrigationData.py",
        "nsPlanterPowerData.py",
        "nsPlanterPowerTimeSeries.py",
        "nsPlanterStatusData.py",
        "nsRainData.py",
        
        "power_monitor.py",
        "ramblockdev.py",
        "raw_di.py",
        "SIM800L.py",
        "soil_moisture.py",
        "ssd1306.py",

        "switch.py",
        "time_it.py",
        "timetools.py",
        "tools.py",
        "ubutton.py",
        "uping.py",
        "wifimgr.py"
    ),
    opt=3,
)

