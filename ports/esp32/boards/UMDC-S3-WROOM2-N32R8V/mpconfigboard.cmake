set(IDF_TARGET esp32s3)


set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    ${SDKCONFIG_IDF_VERSION_SPECIFIC}
    boards/sdkconfig.usb
    boards/sdkconfig.ble
    boards/sdkconfig.spiram_sx
    ${SDKCONFIG_DEFAULTS}
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram_oct
    boards/UMDC-S3-WROOM2-N32R8V/sdkconfig.board
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="Generic ESP32S3 module with Octal-SPIRAM"
)



set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

#set(MICROPY_PY_BLUETOOTH 1)
#set(MICROPY_BLUETOOTH_NIMBLE 1)
#set(MICROPY_BLUETOOTH_BTSTACK 1)

#set(MICROPY_PY_NETWORK_WIZNET5K W5500)
#set(MICROPY_PY_NETWORK_WIZNET5K 5500)
    

