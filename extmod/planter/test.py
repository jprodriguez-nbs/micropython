import time
from machine import time_pulse_us


def test_adxl34x(cls):
    if cls.status.has_accelerometer:
        while True:
            print("%f %f %f" % cls.accelerometer.acceleration)

            print("Dropped: %s" % cls.accelerometer.events["freefall"])
            print("Tapped: %s" % cls.accelerometer.events["tap"])
            print("Motion detected: %s" % cls.accelerometer.events["motion"])
            time.sleep(1)


def median_of_n(p, n, timeout):
    # https://forum.micropython.org/viewtopic.php?t=5724
    # p = input pin
    # n = number of samples
    aux_set = []
    for _ in range(n):
        time_pulse_us(p, 1, timeout)
        v = time_pulse_us(p, 1, timeout)
        time_pulse_us(p, 0, timeout)
        v += time_pulse_us(p, 0, timeout)
        aux_set.append(v)
    aux_set.sort()
    return aux_set[n//2]



def test_frequency_measurement(cls):
    #p = Pin(PINOUT.DI_FLOW_SENSOR, Pin.IN)
    p = cls.di_flow_sensor
    tau = 0.25
    res = 0

    while True:
        res += tau * (median_of_n(p, 7, 5500) - res)
        if cls.status.has_mcp:
            v = cls.mcp.gpio
        else:
            v = 0
        if res > 0:
            print(res,"        ",1000000/res, "        ", "{0:b}".format(v), "          ","\r")
        else:
            print("NO PULSES   ", "{0:b}".format(v), "          ","\r")
        time.sleep(0.1)

    # YF-S201 Flow Sensor
    # Pulse frequency (Hz) / 7.5 = flow rate in L/min.
    # https://www.hobbytronics.co.uk/download/YF-S201.ino
    # Pulse frequency (Hz) = 7.5Q, Q is flow rate in L/min. (Results in +/- 3% range)
    # l_hour = (flow_frequency * 60 / 7.5); // (Pulse frequency x 60 min) / 7.5Q = flow rate in L/hour


def monitor_mcp(cls):
    if cls.status.has_mcp:
        while True:
            v = cls.mcp.gpio
            print("{0:b}".format(v))
            time.sleep(0.25)





