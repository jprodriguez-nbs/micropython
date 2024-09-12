#
# This file is part of the micropython-esp32-ulp project,
# https://github.com/micropython/micropython-esp32-ulp
#
# SPDX-FileCopyrightText: 2018-2023, the micropython-esp32-ulp authors, see AUTHORS file.
# SPDX-License-Identifier: MIT

"""
Address / Register definitions for the ESP32-S2 SoC
"""

# Reference:
# https://github.com/espressif/esp-idf/blob/v5.0.2/components/soc/esp32s2/include/soc/reg_base.h

DR_REG_SYSTEM_BASE                      = 0x3f4c0000
DR_REG_SENSITIVE_BASE                   = 0x3f4c1000
DR_REG_INTERRUPT_BASE                   = 0x3f4c2000
DR_REG_DMA_COPY_BASE                    = 0x3f4c3000
DR_REG_EXTMEM_BASE                      = 0x61800000
DR_REG_MMU_TABLE                        = 0x61801000
DR_REG_ITAG_TABLE                       = 0x61802000
DR_REG_DTAG_TABLE                       = 0x61803000
DR_REG_AES_BASE                         = 0x6003a000
DR_REG_SHA_BASE                         = 0x6003b000
DR_REG_RSA_BASE                         = 0x6003c000
DR_REG_HMAC_BASE                        = 0x6003e000
DR_REG_DIGITAL_SIGNATURE_BASE           = 0x6003d000
DR_REG_CRYPTO_DMA_BASE                  = 0x6003f000
DR_REG_ASSIST_DEBUG_BASE                = 0x3f4ce000
DR_REG_DEDICATED_GPIO_BASE              = 0x3f4cf000
DR_REG_INTRUSION_BASE                   = 0x3f4d0000
DR_REG_UART_BASE                        = 0x3f400000
DR_REG_SPI1_BASE                        = 0x3f402000
DR_REG_SPI0_BASE                        = 0x3f403000
DR_REG_GPIO_BASE                        = 0x3f404000
DR_REG_GPIO_SD_BASE                     = 0x3f404f00
DR_REG_FE2_BASE                         = 0x3f405000
DR_REG_FE_BASE                          = 0x3f406000
DR_REG_FRC_TIMER_BASE                   = 0x3f407000
DR_REG_RTCCNTL_BASE                     = 0x3f408000
DR_REG_RTCIO_BASE                       = 0x3f408400
DR_REG_SENS_BASE                        = 0x3f408800
DR_REG_RTC_I2C_BASE                     = 0x3f408C00
DR_REG_IO_MUX_BASE                      = 0x3f409000
DR_REG_HINF_BASE                        = 0x3f40B000
DR_REG_I2S_BASE                         = 0x3f40F000
DR_REG_UART1_BASE                       = 0x3f410000
DR_REG_I2C_EXT_BASE                     = 0x3f413000
DR_REG_UHCI0_BASE                       = 0x3f414000
DR_REG_SLCHOST_BASE                     = 0x3f415000
DR_REG_RMT_BASE                         = 0x3f416000
DR_REG_PCNT_BASE                        = 0x3f417000
DR_REG_SLC_BASE                         = 0x3f418000
DR_REG_LEDC_BASE                        = 0x3f419000
DR_REG_CP_BASE                          = 0x3f4c3000
DR_REG_EFUSE_BASE                       = 0x3f41A000
DR_REG_NRX_BASE                         = 0x3f41CC00
DR_REG_BB_BASE                          = 0x3f41D000
DR_REG_TIMERGROUP0_BASE                 = 0x3f41F000
DR_REG_TIMERGROUP1_BASE                 = 0x3f420000
DR_REG_RTC_SLOWMEM_BASE                 = 0x3f421000
DR_REG_SYSTIMER_BASE                    = 0x3f423000
DR_REG_SPI2_BASE                        = 0x3f424000
DR_REG_SPI3_BASE                        = 0x3f425000
DR_REG_SYSCON_BASE                      = 0x3f426000
DR_REG_APB_CTRL_BASE                    = 0x3f426000  # Old name for SYSCON, to be removed
DR_REG_I2C1_EXT_BASE                    = 0x3f427000
DR_REG_SPI4_BASE                        = 0x3f437000
DR_REG_USB_WRAP_BASE                    = 0x3f439000
DR_REG_APB_SARADC_BASE                  = 0x3f440000
DR_REG_USB_BASE                         = 0x60080000
