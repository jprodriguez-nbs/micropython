set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.ble
    boards/sdkconfig.240mhz
    boards/UMDC-PCIE/sdkconfig.board
)

set(SDKCONFIG_DEFAULTS
    ${SDKCONFIG_DEFAULTS}
    boards/sdkconfig.spiram
)

#list(APPEND MICROPY_DEF_BOARD
#    MICROPY_HW_BOARD_NAME="Generic ESP32 module with SPIRAM"
#)


set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

set(MICROPY_PY_BLUETOOTH 1)
set(MICROPY_BLUETOOTH_NIMBLE 1)
set(MICROPY_BLUETOOTH_BTSTACK 1)

#set(MICROPY_PY_NETWORK_WIZNET5K W5500)
#set(MICROPY_PY_NETWORK_WIZNET5K 5500)
    

