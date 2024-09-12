#define MICROPY_HW_BOARD_NAME "ESP32-S3-N16R8 CNX-umdc"
#define MICROPY_HW_MCU_NAME "ESP32S3"


#define MICROPY_PY_MACHINE_DAC              (0)

// Enable UART REPL for modules that have an external USB-UART and don't use native USB.
#define MICROPY_HW_ENABLE_UART_REPL         (1)

#define MICROPY_HW_I2C0_SCL                 (9)
#define MICROPY_HW_I2C0_SDA                 (8)

//#define MICROPY_WRAP_MP_BINARY_OP (0)


//#define MICROPY_WRAP_MP_BINARY_OP(f) f
//#define MICROPY_WRAP_MP_EXECUTE_BYTECODE(f)  f
//#define MICROPY_WRAP_MP_LOAD_GLOBAL(f)  f
//#define MICROPY_WRAP_MP_LOAD_NAME(f)  f
//#define MICROPY_WRAP_MP_MAP_LOOKUP(f)  f
//#define MICROPY_WRAP_MP_OBJ_GET_TYPE(f)  f

//#define MICROPY_PY_NETWORK_WIZNET5K 5500


#define MICROPY_PY_DEFLATE (1)
#define MICROPY_PY_DEFLATE_COMPRESS (1)


#define MBEDTLS_SSL_PROTO_TLS1 (1)
#define MBEDTLS_SSL_PROTO_TLS1_1 (1)
#define MBEDTLS_SSL_PROTO_TLS1_2 (1)

#define MICROPY_GC_MULTIHEAP (1)