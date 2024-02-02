The following files are firmware that should work on most ESP32-S3-based
boards with 32MiB of flash, including WROOM and MINI modules.

This firmware supports configurations with and without SPIRAM (also known as
PSRAM) and will auto-detect a connected SPIRAM chip at startup and allocate
the MicroPython heap accordingly. However if your board has Octal SPIRAM, then
use the "spiram-oct" variant.

16MB SPI OCTAL SPI FLASH
8MB PSRAM OCTAL SPI

https://shop.m5stack.com/products/m5stack-cores3-esp32s3-lotdevelopment-kit

# Features

Developed based on ESP32, support WiFi @16M Flash, 8M PSRAM
Built-in camera, proximity sensor, speaker, power indicator, RTC, I2S amplifier, dual microphone, condenser touch screen, power button, reset button, gyroscope
TF card slot
High-strength glass
Support OTG and CDC functions
AXP2101 power management, low power design
Supported programming platforms: Arduino, UIFlow

# Includes

1 × CoreS3
1 × DinBase

# Applications

IoT development
Various DIY project development
Smart home control system
Industrial automation control system

# Specification

Resources	Parameters
MCU	ESP32-S3@Xtensa LX7, 16MFLASH AND 8M-PSRAM, WIFI, OTGCDC functions
Touch the IPS LCD screen	2.0"@320*240 ILI9342C
Camera	GC0308@30 megapixels
Proximity sensors	LTR-553ALS-WA
Power management chip	AXP2101
Six-axis attitude sensor	BMI270
magnetometer	BMM150
RTC	BM8563
Speaker	16bits-I2S power amplifier chip AW88298@1W
Audio decoding chip	ES7210, dual microphone inputs
Product Size	54 x 54 x 16mm
Package Size	101x64x34mm
Product Weight	73.3g
Package Weight	97.8g

# DIN Base pin map

Port A (red): Pin G2/G1 - I2C
Port B (black): I=8 / O=9  - Pin G9/G8 - GPIO
Port C (blue): R=18 / T=17 - Pin G18/G17 - UART RX/TX


# I2C Address

Chip	        ADDRESS     FUNCTION
GC0308 ADDR	    0X21        30w pixel camera
LTR553 ADDR	    0x23        LTR-553ALS-WA proximity sensor
AXP2101 ADDR	0x34        Power Management IC
AW88298 ADDR	0x36        high-fidelity 16-bit I2S power amplifier
FT6336 ADDR	    0x38        CAP.TOUCH
ES7210 ADDR	    0x40        audio decoding chip
BM8563 ADDR	    0x51        RTC
AW9523 ADDR	    0x58        Speaker: 16bits-I2S power amplifier chip AW88298@1W
BMI270 ADDR	    0x69        Six-axis attitude sensor
BMM150 ADDR	    0x10        magnetometer

# Embedded USB-serial/jtag


https://github.com/espressif/openocd-esp32/blob/master/contrib/60-openocd.rules
https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/jtag-debugging/
https://docs.espressif.com/projects/esp-idf/zh_CN/v4.4/esp32s3/api-reference/kconfig.html#config-esp-console-uart

https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/jtag-debugging/configure-builtin-jtag.html

## JTAG

https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/jtag-debugging/index.html#introduction
