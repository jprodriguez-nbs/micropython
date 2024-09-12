This module provides the functionality to compile assembly code in the ESP32

# Source

Code comes from 

origin  https://github.com/ThomasWaldmann/py-esp32-ulp.git (fetch)
origin  https://github.com/ThomasWaldmann/py-esp32-ulp.git (push)

folder esp32_ulp

# Manifest

manifest is written by us:

# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "esp32_ulp/__init__.py",
        "esp32_ulp/__main__.py",
        "esp32_ulp/assemble.py",
        "esp32_ulp/definesdb.py",
        "esp32_ulp/link.py",
        "esp32_ulp/nocomment.py",
        "esp32_ulp/opcodes_s2.py",
        "esp32_ulp/opcodes.py",
        "esp32_ulp/parse_to_db.py",
        "esp32_ulp/preprocess.py",
        "esp32_ulp/soc_s2.py",
        "esp32_ulp/soc_s3.py",
        "esp32_ulp/soc.py",
        "esp32_ulp/util.py"
    ),
    opt=3,
)

# Frozen

This is copied to micropython/extmod to include it in the frozen modules
