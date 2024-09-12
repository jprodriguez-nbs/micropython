# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "uModBus/async_serial.py",
        "uModBus/common.py",
        "uModBus/const.py",
        "uModBus/functions.py",
        "uModBus/serial.py",
        "uModBus/tcp.py",
    ),
    opt=3,
)
