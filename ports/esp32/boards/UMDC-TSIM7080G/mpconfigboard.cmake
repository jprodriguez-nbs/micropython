set(IDF_TARGET esp32s3)


set(SDKCONFIG_DEFAULTS
boards/sdkconfig.base
boards/sdkconfig.usb
boards/sdkconfig.ble
boards/sdkconfig.spiram_oct
boards/UMDC-TSIM7080G/sdkconfig.board
)




set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

set(MICROPY_PY_BLUETOOTH 1)
set(MICROPY_BLUETOOTH_NIMBLE 1)
set(MICROPY_BLUETOOTH_BTSTACK 1)

#set(MICROPY_PY_NETWORK_WIZNET5K W5500)
#set(MICROPY_PY_NETWORK_WIZNET5K 5500)
    

