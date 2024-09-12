import machine, neopixel
import time


def demo(np):
    n = np.n

    # cycle
    if False:
        for i in range(4 * n):
            for j in range(n):
                np[j] = (0, 0, 0)
            np[i % n] = (255, 255, 255)
            np.write()
            time.sleep_ms(25)


    # bounce
    if False:
        for i in range(4 * n):
            for j in range(n):
                np[j] = (0, 0, 128)
            if (i // n) % 2 == 0:
                np[i % n] = (0, 0, 0)
            else:
                np[n - 1 - (i % n)] = (0, 0, 0)
            np.write()
            time.sleep_ms(60)

    # fade in/out
    for i in range(0, 8 * 256, 2):
        for j in range(n):
            if (i // 256) % 2 == 0:
                val = (i+j) & 0xff
            else:
                val = 255 - ((i+j) & 0xff)
            np[j] = (val, 0, 255-val)
        np.write()

    # clear
    for i in range(n):
        np[i] = (0, 0, 0)
    np.write()


def test_neopixel(pin_number, nb_pixel):
    np = neopixel.NeoPixel(machine.Pin(pin_number), nb_pixel)
    demo(np)
    
    