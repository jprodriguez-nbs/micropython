#define MICROPY_HW_BOARD_NAME "ESP32 CNX-umdc PCI-E with SPIRAM"
#define MICROPY_HW_MCU_NAME "ESP32"

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