The following files are firmware that should work on most ESP32-S3-based
boards with 32MiB of flash, including WROOM and MINI modules.

This firmware supports configurations with and without SPIRAM (also known as
PSRAM) and will auto-detect a connected SPIRAM chip at startup and allocate
the MicroPython heap accordingly. However if your board has Octal SPIRAM, then
use the "spiram-oct" variant.

                        FLASH               PSRAM
ESP32-S3-WROOM-1-N16R8 16 MB (Quad SPI) 8 MB (Octal SPI) –40 ~ 65

16MB SPI QUAD SPI FLASH
8MB PSRAM OCTAL SPI