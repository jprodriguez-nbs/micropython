try:
    from pn532.interfaces.pn532i2c import Pn532I2c
    from pn532.interfaces.pn532spi import Pn532Spi
    from pn532.interfaces.pn532hsu import Pn532Hsu
except:        # Allow unit tests to run without importing interfaces
    Pn532Hsu = None
    Pn532Spi = None
    Pn532I2c = None


from pn532.nfc.pn532_log import DEBUG
from pn532.nfc import pn532
from pn532.nfc.pn532 import Pn532_Generic
from pn532.nfc.llcp import Llcp
from pn532.nfc.snep import Snep
from pn532.nfc.emulatetag import EmulateTag
