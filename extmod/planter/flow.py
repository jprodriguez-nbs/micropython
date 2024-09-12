import time
import os
import io
import sys

import logging

import gc
import machine
from machine import Pin, sleep, time_pulse_us, disable_irq, enable_irq, Timer
from micropython import const

import uasyncio as asyncio

import utime
import power_monitor as power_monitor

import planter_pinout as PINOUT

import colors

LIMIT_US_FOR_TIMER_INTERRUPT_PERIOD = const(1500)



_logger = logging.getLogger("Flow")
_logger.setLevel(logging.DEBUG)

pulses = 0
pulses_by_hysteresis = 0
di_flow_sensor = Pin(PINOUT.DI_FLOW_SENSOR, Pin.IN, pull=PINOUT.DI_FLOW_PULL)
_di_flow_interrupt_received = False
_di_flow_interrupt_pin = 0
_di_flow_count = 0

_di_flow_ticks_us_last_interrupt = 0
_di_flow_removed_pulses = 0
_di_flow_input_previous_value = 1

# PWM
_pwm_pin = machine.Pin(PINOUT.PWM_OUT, mode=Pin.OUT, value=0)
_pwm_pin.value(0)
_pwm = None
_pwm_duty = 0
_pwm_freq = PINOUT.PWM_FREQ

_filtered_di_flow_sensor = 1.0
_effective_di_flow_value = 1
_filtered_di_flow_sensor_fadding = 0.8

_previous_timer_2_ticks_us = 0
_avg_time_us = 0
start_us = 0
start_ms = 0
pulses_freq = 0
missed_pulses = 0

tim = None
_mcp = None

li_traces = None
irrigation_active = False

p13 = None

_last_falling_edge_us = 0


_flow_history = []
_last_pulses_increment_historized = 0
_last_pulses_count_historized = 0
_last_pulses_count_historized_us = 0
_instant_flow = 0
_pulses_per_second = 0


pulses_per_l = PINOUT.FLOW_PPL

#
# LOOP
#

loop = asyncio.get_event_loop()

#
#
#

flow_enable_hysteresis = True

def effective_pulses():
    global flow_enable_hysteresis
    global _di_flow_count
    global pulses_by_hysteresis

    if flow_enable_hysteresis:
        i_effective_pulses = pulses_by_hysteresis
    else:
        i_effective_pulses = _di_flow_count
    return i_effective_pulses

#
# TIMER 2 is the timer that we use to monitor the digital input value
# and apply a filter averaging the last measures to determine
# if the input is a real 1 or 0, using hysteresis
#
def handle_timer_2(timer):
    global _di_flow_interrupt_received
    global _di_flow_interrupt_pin
    global _di_flow_count
    global pulses
    global _di_flow_ticks_us_last_interrupt
    global _di_flow_removed_pulses
    global _di_flow_input_previous_value
    global di_flow_sensor
    global _filtered_di_flow_sensor
    global _effective_di_flow_value
    global _previous_timer_2_ticks_us
    global _avg_time_us
    global pulses_by_hysteresis
    global start_us
    global pulses_freq
    global missed_pulses
    global _last_falling_edge_us
    global _flow_history
    global _last_pulses_count_historized
    global _last_pulses_count_historized_us
    global _last_pulses_increment_historized
    global _instant_flow
    global _pulses_per_second
    global flow_enable_hysteresis


    current_value = float(0.0)
    for i in range(10):
        current_value += float(di_flow_sensor.value())
    current_value = float(current_value / 10.0)
    _filtered_di_flow_sensor = (_filtered_di_flow_sensor * 0.6) + (current_value * 0.4) 

    now_us = utime.ticks_us()
    now_ms = utime.ticks_ms()
    elapsed_since_last_timer_int_us = utime.ticks_diff(now_us, _previous_timer_2_ticks_us)


    _avg_time_us = (_avg_time_us * 0.9) + (elapsed_since_last_timer_int_us * 0.1)

    i_effective_pulses = effective_pulses()

    #
    # Calculate pulses frequency
    #
    elapsed_since_start_ms = utime.ticks_diff(now_ms, start_ms)
    elapsed_since_start_s = float(elapsed_since_start_ms) / 1000.0
    if elapsed_since_start_s > 0.0:
        pulses_freq = float(i_effective_pulses) / elapsed_since_start_s
        if pulses_freq > 100:
            # This value is out of range.
            pulses_freq = 100
    else:
        pulses_freq = 0



    if elapsed_since_last_timer_int_us < LIMIT_US_FOR_TIMER_INTERRUPT_PERIOD:
        #
        # Calculate new value using hysteresis
        #
        new_value = _effective_di_flow_value
        if _effective_di_flow_value == 1:
            if _filtered_di_flow_sensor < 0.4:
                new_value = 0
        else:
            if _filtered_di_flow_sensor > 0.6:
                new_value = 1
    else:
        #
        # Use frequency because we have lost some pulses due to the timer not firing
        #

        missing_pulses = float(pulses_freq * elapsed_since_last_timer_int_us) /  1000000.0
        missed_pulses += missing_pulses
        pulses_by_hysteresis += int(missing_pulses)

        # Reset
        new_value = current_value
        _filtered_di_flow_sensor = current_value

    #
    # Apply hysteresis to calculate _effective_di_flow_value
    #
    if new_value != _effective_di_flow_value:
        _effective_di_flow_value = new_value

        if p13 is not None:
            # Output the effective value so it can be monitorized by LED and oscilloscope
            p13.value(_effective_di_flow_value)

        if new_value == 0:
            #_di_flow_count += 1
            pulses_by_hysteresis += 1


    _previous_timer_2_ticks_us = now_us

    elapsed_since_last_pulse_count_historized_us = utime.ticks_diff(now_us, _last_pulses_count_historized_us)
    if elapsed_since_last_pulse_count_historized_us >= 999000:

        pulses_increment = i_effective_pulses - _last_pulses_count_historized
        _flow_history.append((now_us, i_effective_pulses, pulses_increment))
        _last_pulses_count_historized = i_effective_pulses
        _last_pulses_count_historized_us = now_us
        _last_pulses_increment_historized = pulses_increment

        
        vol_l = ((float(pulses_increment) / float(pulses_per_l)))
        elapsed_seconds = elapsed_since_last_pulse_count_historized_us /  float(1000000)
        elapsed_minutes = elapsed_since_last_pulse_count_historized_us / float(60000000)
        # flow_lpm = pulses_per_second / PINOUT.FLOW_PULSE_FACTOR
        if elapsed_minutes > 0 and elapsed_seconds > 0:
            _instant_flow = vol_l / elapsed_minutes
            _pulses_per_second = pulses_increment / elapsed_seconds
        else:
            _instant_flow = 0
            _pulses_per_second = 0

#
# di flow is the flow sensor digital input
# some times this input has noise that triggers the interrupt
# and we need to filter these interrupts using the help of the
# pulse analysis by hysteresis done in handle_timer_2
#
def handle_di_flow_interrupt(pin):
    global _di_flow_interrupt_received
    global _di_flow_interrupt_pin
    global _di_flow_count
    global pulses
    global _di_flow_ticks_us_last_interrupt
    global _di_flow_removed_pulses
    global _di_flow_input_previous_value
    global di_flow_sensor
    global _filtered_di_flow_sensor
    global _effective_di_flow_value
    global _last_falling_edge_us
    global flow_enable_hysteresis

    _di_flow_interrupt_received = True
    _di_flow_interrupt_pin = pin


    # Take multiple samples to be sure about the current value
    # This may filter some of the glitches
    current_value = float(0.0)
    for i in range(10):
        current_value += float(di_flow_sensor.value())
    current_value = float(current_value / 10.0)

    # Calculate how much time has passed since the last falling edge
    # because we can filter out pulses if this time is too short
    now_us = utime.ticks_us()
    now_ms = utime.ticks_ms()
    elapsed_since_last_falling_edge_us = utime.ticks_diff(now_us, _last_falling_edge_us)
    elapsed_since_last_timer_int_us = utime.ticks_diff(now_us, _previous_timer_2_ticks_us)

    # Calculate elapsed time since we started the irrigation
    elapsed_since_start_ms = utime.ticks_diff(now_ms, start_ms)
    elapsed_since_start_s = float(elapsed_since_start_ms) / 1000.0

    #
    # Calculate the pulses frequency since we started the irrigation
    #
    if elapsed_since_start_s > 0.0:
        i_effective_pulses = effective_pulses()
        pulses_freq = float(i_effective_pulses) / elapsed_since_start_s
        if pulses_freq > 100:
            # This value is out of range.
            pulses_freq = 100
        if pulses_freq>0:
            expected_period_us = float(1000000.0)/float(pulses_freq)
            expected_period_low_limit_us = float(1000000.0)/float(pulses_freq*1.5)
        else:
            expected_period_us = 0
            expected_period_low_limit_us = 0
    else:
        # start_ms is not initialised correctly, so we cannot calculate the pulses_freq
        pulses_freq = 0
        expected_period_us = 0
        expected_period_low_limit_us = 0
    


    if False:
        if current_value != _di_flow_input_previous_value:
            _di_flow_input_previous_value = current_value
            _di_flow_count += 1
            pulses += 1

            now_us = utime.ticks_us()
            elapsed_us = utime.ticks_diff(now_us, _di_flow_ticks_us_last_interrupt)
            if elapsed_us <= 200:
                # This is a glitch, remove 2
                pulses -= 2
                _di_flow_count -= 2
                _di_flow_removed_pulses += 2
            else:
                _di_flow_ticks_us_last_interrupt = now_us


    period_ok = elapsed_since_last_falling_edge_us >= expected_period_low_limit_us

    is_last_value_high_according_to_hysteresis = (_filtered_di_flow_sensor > 0.6 or flow_enable_hysteresis is False)

    if current_value <= 0.2 and is_last_value_high_according_to_hysteresis and period_ok:
        # Real falling edge
        # Period_ok check prevents from accumulating false falling edges while in high level
        _di_flow_count += 1
        pulses += 1
        _last_falling_edge_us = now_us
    else:
        if elapsed_since_last_timer_int_us < LIMIT_US_FOR_TIMER_INTERRUPT_PERIOD:
            # timer interrupts are working, so this is falling-edge interrupt is to be removed
            _di_flow_removed_pulses += 1
        else:
            # timer interrupts are not working, therefore we have to further analyse the situation
            if period_ok:
                # Accept the falling edge
                # Period_ok check prevents from losing falling edges while in low level because timer is not producing interrupts
                _di_flow_count += 1
                pulses += 1
                _last_falling_edge_us = now_us   
            else:
                # Period is not OK, therefore we reject the falling-edge interrupt
                _di_flow_removed_pulses += 1


def setup_interrupts():
    global di_flow_sensor
    global tim

    di_flow_sensor.irq(trigger=PINOUT.FLOW_IRQ_MODE, handler=handle_di_flow_interrupt)
    tim = Timer(2)
    tim.init(period=1, mode=machine.Timer.PERIODIC, callback=handle_timer_2)

def disable_interrupts():
    global di_flow_sensor
    global tim
    if di_flow_sensor is not None:
        di_flow_sensor.irq(trigger=0)
    if tim is not None:
        tim.deinit()

def pulse_count():
    return effective_pulses()


def flow_lpm():
    global _instant_flow
    global _pulses_per_second
    global _last_pulses_increment_historized

    return (_instant_flow, _pulses_per_second, _last_pulses_increment_historized)



def clear_pulses():
    global pulses
    global _di_flow_count
    global _di_flow_removed_pulses
    global _di_flow_input_previous_value
    global _effective_di_flow_value
    global _filtered_di_flow_sensor
    global _avg_time_us
    global pulses_by_hysteresis
    global start_ms
    global start_us
    global missed_pulses
    global _last_falling_edge_us

    global _flow_history
    global _last_pulses_count_historized
    global _last_pulses_count_historized_us
    global _last_pulses_increment_historized
    global _instant_flow
    global _pulses_per_second


    # Set pulses to 0
    missed_pulses = 0
    pulses = 0
    pulses_by_hysteresis = 0
    _di_flow_count = 0
    _di_flow_removed_pulses = 0
    _di_flow_input_previous_value = 1
    _effective_di_flow_value = 1
    _filtered_di_flow_sensor = 1.0
    _avg_time_us = 0
    start_ms = 0
    start_us = 0
    _last_falling_edge_us = 0
    _flow_history = []
    _last_pulses_count_historized = 0
    _last_pulses_count_historized_us = 0
    _last_pulses_increment_historized = 0
    _instant_flow = 0
    _pulses_per_second = 0


def set_pwm_freq(f):
    global _pwm_freq
    _pwm_freq = f

def set_pwm_duty(d):
    global _pwm_duty
    global _pwm
    if _pwm is None:
        return
    _pwm_duty = int(d)
    _pwm.duty(_pwm_duty)

def get_pwm_duty():
    global _pwm_duty
    return _pwm_duty

async def ramp_pwm(final_dc, duration_s):
    factor = 1000/PINOUT.PWM_RAMPUP_STEP_DURATION_MS
    initial_dc = int(get_pwm_duty())
    steps = max(int(duration_s*factor),1)
    dc_step = int((final_dc - initial_dc) / steps)
    _logger.debug("Ramp PWM from {i} to {f} in {d} [s] in {s} steps of {dc_step}".format(i=initial_dc, f=final_dc, d=duration_s, s=steps, dc_step=dc_step))
    if dc_step != 0:
        try:
            for dc in range(initial_dc, final_dc, dc_step):
                set_pwm_duty(dc)
                await asyncio.sleep_ms(PINOUT.PWM_RAMPUP_STEP_DURATION_MS)
        except Exception as ex:
            _logger.exc(ex,"failed to ramp_pwm to {f} in {d} [s]: {e}".format(f=final_dc, d=duration_s, e=str(ex)))
    set_pwm_duty(final_dc)


async def enable_pump(value):
    if _mcp is not None:
        if value:
            _mcp.portb.gpio |= PINOUT.DO_B_PUMP_BIT
        else:
            _mcp.portb.gpio &= ~PINOUT.DO_B_PUMP_BIT


async def measurement_task():
    global irrigation_active
    global li_traces

    elapsed_ms = 0
    ticks_ms_last_measure = 0
    while irrigation_active:
        now_ms = utime.ticks_ms()
        elapsed_ms = utime.ticks_diff(now_ms, ticks_ms_last_measure)
        if elapsed_ms >= 10000:
            ticks_ms_last_measure = now_ms
            m = await power_monitor.cycle(False)
            now_ms = utime.ticks_ms()
            elapsed_ms = utime.ticks_diff(now_ms, start_ms)
            
            trace = "e={e:>6} [ms] - p={p} ({p2}, m={m}), pv = [{pv}], batt = [{batt}], pump = [{pump}], filtered {f}, effective {ef}, avg_t2_us = {at2}, pulse freq {freq} [Hz]".format(
                    e=elapsed_ms, p=pulses, p2=pulses_by_hysteresis, m=missed_pulses, pv=m['pv'], batt=m['batt'], pump=m['pump'],
                    f = _filtered_di_flow_sensor, ef = _effective_di_flow_value, at2=_avg_time_us, freq=pulses_freq)
            li_traces.append(trace)
        await asyncio.sleep_ms(1000)


async def init_irrigation_cycle(mcp, a_flow_enable_hysteresis=True):
    global _mcp
    global _pwm_pin
    global _pwm
    global _pwm_duty
    global pulses
    global _di_flow_count
    global _di_flow_removed_pulses
    global _di_flow_input_previous_value
    global _effective_di_flow_value
    global _filtered_di_flow_sensor
    global _avg_time_us
    global pulses_by_hysteresis
    global start_ms
    global start_us
    global missed_pulses
    global li_traces
    global irrigation_active


    global _flow_history
    global _last_pulses_count_historized
    global _last_pulses_count_historized_us
    global flow_enable_hysteresis


    _mcp = mcp
    flow_enable_hysteresis = a_flow_enable_hysteresis

    # Set pulses to 0
    clear_pulses()

    # Set ISR
    setup_interrupts()


    if _pwm is None:
        # Create the PWM once network communication has been executed, so we don't
        # have the pump with duty 0 making noise and waiting for the communication
        # to finish
        _pwm_duty = 0
        _pwm = machine.PWM(_pwm_pin)
        _pwm.freq(PINOUT.PWM_FREQ)
        _pwm.duty(0)
    
    set_pwm_duty(0)
    
    start_ms = utime.ticks_ms()
    start_us = utime.ticks_us()

    _flow_history = []
    _last_pulses_count_historized = 0
    _last_pulses_count_historized_us = start_us

    await ramp_up()

    li_traces = []
    irrigation_active = True
    loop.create_task(measurement_task())



async def ramp_up():
    global _pwm
    global _pwm_duty
    global _pwm_pin

    # Ramp up
    # Take a power measurement just at the start
    await power_monitor.cycle(False)

    # Ramp up
    await ramp_pwm(1023, PINOUT.PWM_RAMPUP_DURATION_S)

    # Remove pwm and leave fix to 1
    del _pwm
    _pwm = None
    _pwm_duty = 0
    _pwm_pin.value(1)

    gc.collect()

    # Take a power measurement just at the end of the ramp
    await power_monitor.cycle(False)


async def ramp_down():
    global _pwm
    global _pwm_duty
    global _pwm_pin

    await power_monitor.cycle(False)

    if _pwm is None:
        # Create the PWM once network communication has been executed, so we don't
        # have the pump with duty 0 making noise and waiting for the communication
        # to finish
        _pwm = machine.PWM(_pwm_pin)
        _pwm.freq(PINOUT.PWM_FREQ)
        _pwm.duty(1023)
        set_pwm_duty(1023)

    # Ramp down
    await ramp_pwm(0, PINOUT.PWM_RAMPUP_DURATION_S)

    # Remove pwm
    del _pwm
    _pwm = None
    _pwm_duty = 0
    _pwm_pin.value(0)

    gc.collect()

    # Take a power measurement just at the end of the ramp down
    await power_monitor.cycle(False)


async def end_irrigation_cycle():
    global _pwm_pin
    global _pwm
    global _pwm_duty
    global pulses
    global _di_flow_count
    global _di_flow_removed_pulses
    global _di_flow_input_previous_value
    global _effective_di_flow_value
    global _filtered_di_flow_sensor
    global _avg_time_us
    global pulses_by_hysteresis
    global start_ms
    global start_us
    global missed_pulses
    global li_traces
    global irrigation_active


    irrigation_active = False

    await ramp_down()

    disable_interrupts()
    end_ms = utime.ticks_ms()
    total_ms = utime.ticks_diff(end_ms, start_ms)

    # Take a power measurement
    m = await power_monitor.cycle(False)

    for t in li_traces:
        print(t)
    li_traces = None


    # Display final pulses and volume
    i_effective_pulses = effective_pulses()
    vol_l = ((float(i_effective_pulses) / pulses_per_l)) 
    ce_mwh = power_monitor.accumulated_power('12v', 'pump', start_ms, end_ms)

    _logger.debug("pulses = (int = {p}, hist = {p2}, removed = {r}, missed = {m}), vol = {vol_l} [l], energy {e} [mWh], pv = [{pv}], batt = [{batt}], pump = [{pump}]".format(
        p=pulses, p2=pulses_by_hysteresis, m=missed_pulses, r=_di_flow_removed_pulses, vol_l = vol_l, e=ce_mwh, pv=m['pv'], batt=m['batt'], pump=m['pump']))

    gc.collect()

    return (pulses, pulses_by_hysteresis, missed_pulses, _di_flow_removed_pulses, vol_l, ce_mwh)


def set_pulses_per_l(v):
    global pulses_per_l
    pulses_per_l = v


async def test(i2c, mcp, duration):
    global _mcp
    global start_ms

    _mcp = mcp
    # Enable power
    _mcp.portb.gpio |= 0x0E


    # Setup power monitor for 12v bus
    power_monitor.init(i2c, ["12v"])

    await enable_pump(True)

    # Enable outputs
    full_explanation = "{c}Start pump{n}".format(
        c=colors.BOLD_PURPLE, n=colors.NORMAL)
    _logger.debug(full_explanation)


    await init_irrigation_cycle(mcp, True)

    elapsed_ms =0
    duration_ms = duration * 1000
    while elapsed_ms < duration_ms:
        now_ms = utime.ticks_ms()
        elapsed_ms = utime.ticks_diff(now_ms, start_ms)
        await asyncio.sleep_ms(1000)

    
    (pulses, pulses_by_hysteresis, missed_pulses, removed_pulses, vol_l, ce_mwh) = await end_irrigation_cycle()

    full_explanation = "{c}Stop pump{n}".format(
        c=colors.BOLD_PURPLE, n=colors.NORMAL)
    _logger.debug(full_explanation)
    await enable_pump(False)

    i_effective_pulses = effective_pulses()
    full_explanation = "{c}End irrigation cycle{n} after {e} [s], pulses {p}, vol_l {v}, ce_mwh {ce}".format(
        c=colors.BOLD_PURPLE, n=colors.NORMAL, e=elapsed_ms/1000, p=i_effective_pulses, v=vol_l, ce=ce_mwh)
    _logger.info(full_explanation)