# UPDATE libs, rebuild frozend and build

mkdir -p /media/jprodriguez/data/nbs_git/micropython/micropython/extmod/lib/
mkdir -p /media/jprodriguez/data/nbs_git/micropython/micropython/extmod/planter/

cd /media/jprodriguez/data/nbs_git/micropython/micropython/ports/esp32
cp -Rf /media/jprodriguez/data/nbs_git/ud-pyplanter/src/app/local/* /media/jprodriguez/data/nbs_git/ud-pyplanter-libs/lib/
cp -Rf /media/jprodriguez/data/nbs_git/ud-pyplanter-libs/* /media/jprodriguez/data/nbs_git/micropython/micropython/extmod/
cp -Rf /media/jprodriguez/data/nbs_git/ud-pyplanter/libs/manifest.py /media/jprodriguez/data/nbs_git/micropython/micropython/ports/esp32/boards/manifest.py
cp -Rf /media/jprodriguez/data/nbs_git/ud-pyplanter/src/app/local/* /media/jprodriguez/data/nbs_git/micropython/micropython/extmod/lib/.
cp -Rf /media/jprodriguez/data/nbs_git/ud-pyplanter/src/app/planter/* /media/jprodriguez/data/nbs_git/micropython/micropython/extmod/planter/
rm /media/jprodriguez/data/nbs_git/micropython/micropython/ports/esp32/build-PLANTER/frozen_content.c
make BOARD=PLANTER  -j16

# Save bin
cp build-PLANTER/micropython.bin /media/jprodriguez/data/nbs_git/planter.bin

# Flash erase and write
#/home/jprodriguez/.espressif/python_env/idf4.4_py3.9_env/bin/python ../../../../../../../../home/jprodriguez/esp/esp-idf/components/esptool_py/esptool/esptool.py -p /dev/ttyUSB0 -b 460800 --before default_reset --after hard_reset --chip esp32  write_flash --flash_mode dio --flash_size detect --flash_freq 40m 0x1000 build-PLANTER/bootloader/bootloader.bin 0x8000 build-PLANTER/partition_table/partition-table.bin 0x10000 build-PLANTER/micropython.bin
/home/jprodriguez/.espressif/python_env/idf4.4_py3.9_env/bin/python ../../../../../../../../home/jprodriguez/esp/esp-idf/components/esptool_py/esptool/esptool.py -p /dev/ttyACM0 -b 460800 --before default_reset --after hard_reset --chip esp32  write_flash --flash_mode dio --flash_size detect --flash_freq 40m 0x1000 build-PLANTER/bootloader/bootloader.bin 0x8000 build-PLANTER/partition_table/partition-table.bin 0x10000 build-PLANTER/micropython.bin
