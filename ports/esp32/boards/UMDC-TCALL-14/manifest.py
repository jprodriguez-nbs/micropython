#include("$(PORT_DIR)/boards/manifest.py")


freeze("$(PORT_DIR)/modules")
freeze("modules")


#require("ssd1306")

include("$(MPY_DIR)/extmod/asyncio")

# Useful networking-related packages.
require("bundle-networking")

# Require some micropython-lib modules.
#require("dht")
#require("ds18x20")
#require("neopixel")
#require("onewire")
#require("umqtt.robust")
#require("umqtt.simple")
#require("upysh")

require("datetime")

#freeze("$(MPY_DIR)/ports/esp8266/modules", "ntptime.py")
include("$(MPY_DIR)/extmod/asyncio/manifest.py")
#include("$(MPY_DIR)/extmod/webrepl/manifest.py")
#include("$(MPY_DIR)/extmod/MicroWebSrv2/manifest.py")
include("$(MPY_DIR)/extmod/uModBus/manifest.py")
#include("$(MPY_DIR)/extmod/lib/wiznet5k/manifest.py")
include("$(MPY_DIR)/extmod/lib/manifest.py")
include("$(MPY_DIR)/extmod/primitives/manifest.py")
#include("$(MPY_DIR)/extmod/planter/manifest.py")

require("aioble-peripheral")
require("aioble-server")
require("aioble-central")
require("aioble-client")
require("aioble-l2cap")
require("aioble-security")