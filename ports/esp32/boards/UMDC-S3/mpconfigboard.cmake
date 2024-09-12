set(IDF_TARGET esp32s3)


set(SDKCONFIG_DEFAULTS
boards/sdkconfig.base
boards/sdkconfig.usb
boards/sdkconfig.ble
boards/sdkconfig.spiram_sx
boards/ESP32_GENERIC_S3/sdkconfig.board
)

if(MICROPY_BOARD_VARIANT STREQUAL "SPIRAM_OCT")
    set(SDKCONFIG_DEFAULTS
        ${SDKCONFIG_DEFAULTS}
        boards/sdkconfig.240mhz
        boards/sdkconfig.spiram_oct
    )

    list(APPEND MICROPY_DEF_BOARD
        MICROPY_HW_BOARD_NAME="Generic ESP32S3 module with Octal-SPIRAM"
    )
endif()


set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

set(MICROPY_PY_BLUETOOTH 1)
set(MICROPY_BLUETOOTH_NIMBLE 1)
set(MICROPY_BLUETOOTH_BTSTACK 1)

#set(MICROPY_PY_NETWORK_WIZNET5K W5500)
#set(MICROPY_PY_NETWORK_WIZNET5K 5500)
    

