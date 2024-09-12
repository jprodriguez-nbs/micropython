set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram
    boards/PLANTER/sdkconfig.board
)

if(NOT MICROPY_FROZEN_MANIFEST)
    set(MICROPY_FROZEN_MANIFEST ${MICROPY_PORT_DIR}/boards/manifest.py)
endif()

