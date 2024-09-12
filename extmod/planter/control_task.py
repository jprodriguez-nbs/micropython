import utime
import colors
import logging
import machine
import time
import esp32
import hwversion
import uasyncio as asyncio
import io
import sys
import gc
import json


from networkmgr import NetworkMgr
from planter import sm_task

import planter_pinout as PINOUT
import planter.comm as COMM
import planter.config as CFG
import planter.display as PL_DISPLAY
import planter.flow as flow
from planter.status import PlanterEvents, PlanterStatus
from planter.config import K_WAKENING_PERIOD

import ulp.ulp_pulse as ulp_pulse

from machine import Pin

import power_monitor as power_monitor

#import webapp

_control_sleep_lock = asyncio.Lock()

_logger = logging.getLogger("CONTROL")
_logger.setLevel(logging.DEBUG)
_rtc = machine.RTC()

_sm_control_debug_msg = ""
_ts_next_pump_start = 0

flow_ppl = None
_raw_rain_pulses = None

def calc_ts_next_pump_start(status):
    global _sm_control_debug_msg
    global _ts_next_pump_start

    ts_now = utime.time()
    cmt = status.get_control_mode_tuple()
    (cm_p, cm_c, cm_sm, cm_f, cm_d) = cmt
    ts_last_pump_start = status.ts_last_pump_start

    # Starting point is max future value
    ts_next_pump_start = sys.maxsize

    try:
        if ts_last_pump_start is not None:
            elapsed_since_last_pump = ts_now - ts_last_pump_start
        else:
            # Estimate as 'yesterday'
            elapsed_since_last_pump = ts_now - (3600*24) - 240
    except Exception as ex:
        _logger.exc(ex,"calc_ts_next_pump_start - Failed to calculate elapsed_since_last_pump: {e}".format(e=str(ex)))
        elapsed_since_last_pump = ts_now - (3600*24) - 240


    current_second = ts_now % (3600*24)

    irr_cause_p = False
    irr_cause_sm = False
    irr_cause_c = False
    irr_cause_m = False


    bWaterLevelLow = status.level_low
    batt_v = status.batt_v
    bCanStart = True
    reason = None

    vbatt_min_for_pump = status.get_vbatt_min_for_pump()

    if batt_v < vbatt_min_for_pump and PINOUT.ENABLE_PUMP_AND_BATTERY_CHECKS:
        # Cannot start irrigation because battery voltage is low
        reason = "Cannot start irrigation because battery voltage {v} [V] is below threshold {th} [V]".format(v=batt_v, th=vbatt_min_for_pump)
        bCanStart = False
        # Set the ts_last_pump_start so we can go to sleep
        status.ts_last_pump_start = ts_now


    forcedirrigation = False
    forcedirrigation_str = "False"
    li_downlink_messages = status.downlink_messages
    if li_downlink_messages is not None:
        for dlmsg in li_downlink_messages:
            if 'forcedirrigation' in dlmsg['Topic']:
                forcedirrigation = True
                forcedirrigation_str = "{c}True{n}".format(c=colors.BOLD_PURPLE, n=colors.NORMAL)
                break


    if forcedirrigation:
        cm_p = False
        cm_sm = False
        cm_c = False
        cm_d = False
        cm_f = True
        



    if cm_p:
        try:
            aux = ts_last_pump_start + status.periodic_mode_pump_period_s
            if aux < ts_next_pump_start:
                ts_next_pump_start = aux
                if bCanStart and ((ts_next_pump_start - ts_now) < 0):
                    irr_cause_p = True
                    _logger.info("CM_P - start because periodic pump. last {l}, period {p}, now {now}, next {n}".format(
                        l=ts_last_pump_start, p=status.periodic_mode_pump_period_s, now=ts_now, n=ts_next_pump_start
                    ))
        except Exception as ex:
            _logger.exc(ex,"calc_ts_next_pump_start CM_P - Failed to calculate ts_next_pump_start: {e}".format(e=str(ex)))

    elif cm_sm:
        try:
            a = status.soil_moisture_data_available

            (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s) = status.get_sm_params()

            sm = status.soil_moisture_vwc
            aux = "CM_S: data available {a}, sm {sm}, th {th} and elapsed {e} [s] since last pump, min period {p} [s]".format(
                        a=a, sm=sm, th = sm_low_th, e = elapsed_since_last_pump,
                        e = elapsed_since_last_pump, p = sm_pump_min_period_s
                    )
            if aux != _sm_control_debug_msg:
                _sm_control_debug_msg = aux
                _logger.debug(aux)

            if (sm < sm_low_th) and a:
                if bCanStart and (elapsed_since_last_pump > sm_pump_min_period_s):
                    _logger.info("CM_S: start because soil moisture {sm} < {th} and elapsed {e} since last pump".format(
                        sm=sm, th = sm_low_th, e = elapsed_since_last_pump
                    ))
                    aux = ts_now
                    irr_cause_sm = True
                else:
                    aux = ts_now + sm_pump_min_period_s - elapsed_since_last_pump
                    irr_cause_sm = True

                if aux < ts_next_pump_start:
                    ts_next_pump_start = aux
        except Exception as ex:
            _logger.exc(ex,"calc_ts_next_pump_start CM_SM - Failed to calculate ts_next_pump_start: {e}".format(e=str(ex)))

    elif cm_c and bCanStart:
        try:
            debug_calendar_mode = logging.INFO
            cs_hh = int(current_second // 3600)
            cs_mm = (current_second % 3600) // 60
            cs_ss = current_second % 60
            dt = _rtc.datetime()
            aux = 3600*24*2
            if debug_calendar_mode<=logging.DEBUG:
                _logger.debug("current_second = {cs} ({hh:02}:{mm:02}:{ss:02}) - Calendar = {c}".format(cs=current_second, hh=cs_hh, mm=cs_mm, ss=cs_ss, c=str(status.calendar)))

            selected_start_s=None
            calendar_discarded_because_sm = False
            sm = None
            
            a = status.soil_moisture_data_available
            if a:
                (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s) = status.get_sm_params()
                sm = status.soil_moisture_vwc
            
            for start_s, cal_data in status.calendar.items():
                if (start_s is not None) and (cal_data is not None):
                    pending_to_cal_start_s = start_s - current_second
                    cal_moisture_low_th = cal_data[CFG._CAL_DATA_MOISTURE_LOW_TH_POSITION]
                    cal_start_str = cal_data[CFG._CAL_DATA_START_STR_POSITION]
                    if pending_to_cal_start_s < 0:
                        pending_to_cal_start_s = pending_to_cal_start_s + (3600*24) # Next day
                    elapsed_since_start_s = current_second - start_s
                    d2 = max(cal_data[CFG._CAL_DATA_MAX_DURATION_POSITION], PINOUT.POWERUP_TIME_S*5)*2
                    
                    skip_cal_because_sm = False
                    if cal_moisture_low_th is not None:
                        a = status.soil_moisture_data_available
                        if a:
                            if sm is not None and sm > cal_moisture_low_th:
                                # The calendar rule has a soil moisture threshold
                                # and the current soil moisture is higher than the threshold specified in the calendar
                                # therefore se are not going to activate the irrigation because this rule
                                skip_cal_because_sm = True
                                calendar_discarded_because_sm = True
                    
                    if skip_cal_because_sm is False:
                        if elapsed_since_start_s > 0 and elapsed_since_start_s < d2 and elapsed_since_last_pump > d2:
                            aux = 0
                            irr_cause_c = True
                            msg = "CM_C: Start because calendar control - Start at {start} (pending {pc} [s]), now {hh:02}:{mm:02}:{ss:02} ({cs}), elapsed since last pump {e} [s]".format(
                                        start = cal_start_str, pc=pending_to_cal_start_s, cs=current_second, hh=dt[4], mm=dt[5], ss=dt[6],
                                        e=elapsed_since_last_pump)
                            _logger.debug(msg)
                            selected_start_s = start_s
                            
                        if pending_to_cal_start_s < aux:
                            aux = pending_to_cal_start_s
                            if debug_calendar_mode<=logging.DEBUG:
                                msg = "CM_C: New value - Start at {start} (pending {pc} [s]), now {hh:02}:{mm:02}:{ss:02} ({cs}) elapsed since last pump {e} [s] -> pending {ps} [s] to start".format(
                                            start = cal_start_str, pc=pending_to_cal_start_s, cs=current_second, hh=dt[4], mm=dt[5], ss=dt[6],
                                            e=elapsed_since_last_pump, ps=aux)
                                _logger.debug(msg)
                            selected_start_s = start_s
                        else:
                            if debug_calendar_mode<=logging.DEBUG:
                                msg = "CM_C: DISCARDED - Start at {start} (pending {pc} [s]) discarded because now {hh:02}:{mm:02}:{ss:02} ({cs}) and pending {ps} ".format(
                                            start = cal_start_str, pc=pending_to_cal_start_s, cs=current_second, hh=dt[4], mm=dt[5], ss=dt[6], ps=aux)
                                _logger.debug(msg)
                    else:
                        if debug_calendar_mode<=logging.DEBUG:
                            msg = "CM_C: DISCARDED - Start at {start} (pending {pc} [s]) discarded because now {hh:02}:{mm:02}:{ss:02} ({cs}) and pending {ps}, soil moisture low threshold is {th} and current soil moisture is {sm} ".format(
                                        start = cal_start_str, pc=pending_to_cal_start_s, cs=current_second, hh=dt[4], mm=dt[5], ss=dt[6], ps=aux, th=cal_moisture_low_th, sm=sm)
                            _logger.debug(msg)    
                
                else:
                    msg = "CM_C: DISCARDED invalid configuration data start_s '{start}' - cal_data '{cal_data}'".format(
                        start = str(start_s), cal_data=str(cal_data))
                    _logger.error(msg)

            if selected_start_s is None:
                if calendar_discarded_because_sm is False:
                    msg = "CM_C: There is no valid calendar register for today, so it is not possible to irrigate by calendar."
                    _logger.error(msg)       
                else:
                    msg = "CM_C: The soil moisture is higher than the threshold configured in the calendar, so irrigation is disabled."
                    _logger.error(msg)     
                    
            if debug_calendar_mode > logging.DEBUG:
                if selected_start_s is not None and current_second is not None:
                    pending_to_cal_start_s = selected_start_s - current_second
                    if pending_to_cal_start_s < 0:
                        pending_to_cal_start_s = pending_to_cal_start_s + (3600*24) # Next day
                    cal_data = status.calendar[selected_start_s]
                    msg = "CM_C: Start at {start} (pending {pc} [s]), now {hh:02}:{mm:02}:{ss:02} ({cs}) elapsed since last pump {e} [s], soil moisture low threshold is {th} and current soil moisture is {sm} -> pending {ps} [s] to start".format(
                                start = cal_start_str, pc=pending_to_cal_start_s, cs=current_second, hh=dt[4], mm=dt[5], ss=dt[6],
                                e=elapsed_since_last_pump, ps=aux, th=cal_moisture_low_th, sm=sm)
                    _logger.info(msg)

            ts_next_pump_start = ts_now + aux
        except Exception as ex:
            _logger.exc(ex,"calc_ts_next_pump_start CM_C - Failed to calculate ts_next_pump_start: {e}".format(e=str(ex)))

    elif cm_f:
        # Force irrigation now
        irr_cause_m = True
        ts_next_pump_start = ts_now
        
        _logger.info("CM_F - start forced irrigation. Downlink message forcedirrigation = {f}. last {l}, period {p}, now {now}, next {n}".format(
                        l=ts_last_pump_start, f=forcedirrigation_str, p=status.periodic_mode_pump_period_s, now=ts_now, n=ts_next_pump_start))
        
        pass


    if ts_next_pump_start < 0:
        # We cannot start in the past
        ts_next_pump_start = ts_now

    pending_seconds = ts_next_pump_start - ts_now
    
    need_to_start_pump_cycle = (pending_seconds <= 0)

    if _ts_next_pump_start != ts_next_pump_start:

        _ts_next_pump_start = ts_next_pump_start

        if ts_next_pump_start < sys.maxsize:
            ts_next_pump_start_str = str(ts_next_pump_start)
            pending_seconds_str = str(pending_seconds)
        else:
            ts_next_pump_start_str = "NEVER"
            pending_seconds_str = "N/A"

        _logger.debug("calc_ts_next_pump_start: elapsed since last pump {e} [s], ts_now {now} => second {s}, ts_next_start {n} => pending {cv}{ps}{cn} [s], need to start pump = {need_to_start}, cause (p {irr_cause_p}, c {irr_cause_c}, sm {irr_cause_sm}, m {irr_cause_m}), cm_sm {cm_sm}, has_data {sm_has_data}, mode {cmt}, batt_v={batt_v}, water level low = {ll}".format(
            e = elapsed_since_last_pump,
            now = ts_now, s = current_second, n = ts_next_pump_start_str, ps = pending_seconds_str, need_to_start = need_to_start_pump_cycle,
            irr_cause_p=irr_cause_p, irr_cause_sm=irr_cause_sm, irr_cause_c=irr_cause_c, irr_cause_m=irr_cause_m,
            cm_sm=cm_sm, sm_has_data=status.soil_moisture_data_available, cmt=str(cmt), cv=colors.BOLD_GREEN, cn=colors.NORMAL,
            batt_v = batt_v, ll=bWaterLevelLow
        ))

    irr_cause = (irr_cause_p, irr_cause_sm, irr_cause_c, irr_cause_m)

    return (elapsed_since_last_pump, ts_next_pump_start, pending_seconds, need_to_start_pump_cycle, irr_cause)


async def start_irrigation_cycle(cls, reasons):
    global _raw_rain_pulses


    cls.status.display_page = PlanterStatus.PAGE_PUMP
    # Update display
    try:
        PL_DISPLAY.update_display_with_status(cls)
    except Exception as ex:
        _logger.exc(ex,"failed to update display: {e}".format(e=str(ex)))

    

    if NetworkMgr.isconnected():
        await COMM.post_status_and_events(cls, True)

    # Increase threshold to avoid having multiple interrupts due to the pump vibration
    await cls.set_sensor_motion_threshold(factor=100.0)

    # Calculate elapsed time since last pump start
    current_ts = utime.time()
    elapsed_s = current_ts - cls.status.ts_last_pump_start
    
    # And update with the new timestamp
    cls.status.ts_last_pump_start = current_ts
    
    # Start
    cls.status.start_irrigation_cycle()
    irrigationid = cls.status.current_irrigationid()

    #
    # Get rain pulses count to restore them after the irrigation has finished
    # This is just in case the noise caused by the pump affects the measure of rain pulses
    #
    try:
        if cls.status.has_rain_sensor:
            _raw_rain_pulses = ulp_pulse.getRawPulseCount()
    except:
        pass
    #
    #
    #

    full_explanation = "{c}Start irrigation cycle{n} - irrigationid={irrigationid} - Elapsed since last pump start = {s} [s] - Reasons: {r}".format(
        c=colors.BOLD_PURPLE, n=colors.NORMAL,s=elapsed_s, r=reasons,irrigationid=irrigationid)
    _logger.info(full_explanation)

    # Enable outputs
    await cls.enable_pump(True, full_explanation)
    
    cls.status.display_mode = 1
    PL_DISPLAY.update_display_with_status(cls)
    # cls.flag_post_status_and_events = True  # Do not post until irrigation is finished

    await flow.init_irrigation_cycle(cls.mcp, cls.status.flow_en_hysteresis)


async def end_irrigation_cycle(cls, reasons):
    global _pwm_pin
    global _pwm
    global _pwm_duty
    global _raw_rain_pulses


    #start_ms = cls.status.current_irrigation_cycle_start_ms()
    

    # Take a power measurement
    m = await power_monitor.cycle(False)

    # Get voltage and current before stopping the irrigation so we have a real measure of the pump voltage and current
    vbatt=cls.status.batt_v
    vpump=cls.status.pump_v
    ipump=cls.status.pump_i

    if vbatt is None or vbatt is False or not isinstance(vbatt,(float, int)):
        vbatt = 0.0
    if vpump is None or vpump is False or not isinstance(vpump,(float, int)):
        vpump = 0.0
    if ipump is None or ipump is False or not isinstance(ipump,(float, int)):
        ipump = 0.0


    (pulses, pulses_by_hysteresis, missed_pulses, removed_pulses, vol_l, ce_mwh) = await flow.end_irrigation_cycle()

    
    rh = cls.status.soil_moisture_vwc
    irrigationid = cls.status.current_irrigationid()

    cls.status.end_irrigation_cycle(pulses_by_hysteresis, vol_l, ce_mwh, vbatt, vpump, ipump)
    
    # Calculate elapsed time since last pump start
    current_ts = utime.time()
    elapsed_s = current_ts - cls.status.ts_last_pump_start
    
    # Update stop timestamp
    cls.status.ts_last_pump_stop = current_ts

    full_explanation = "{c}End irrigation cycle{n} - irrigationid={irrigationid} - after {e} [s], pulses (int {p}, hist {ph}, miss {miss}, rem {rem}), vol_l {v}, ce_mwh {ce}, rh {rh} - Reasons: {r}".format(
        c=colors.BOLD_PURPLE, n=colors.NORMAL, e=elapsed_s, p=pulses, ph=pulses_by_hysteresis, miss=missed_pulses, rem=removed_pulses, v=vol_l, ce=ce_mwh, rh=rh, r=reasons, irrigationid=irrigationid)
    _logger.info(full_explanation)

    # Disable outputs
    await cls.enable_pump(False, full_explanation)

    await cls.set_sensor_motion_threshold(factor=1.0)        # Restore threshold

    #
    # Restore the rain pulse count
    #
    try:
        if cls.status.has_rain_sensor:
            aux_rain_pulses = ulp_pulse.getRawPulseCount()
            diff_rain_pulses = aux_rain_pulses - _raw_rain_pulses
            _logger.info("Rain pulses: before irrigation: {i}, after irrigation: {f}, diff: {d}".format(
                i=_raw_rain_pulses, f=aux_rain_pulses, d=diff_rain_pulses))
            ulp_pulse.setRawPulseCount(_raw_rain_pulses)
    except:
        pass
    #
    #
    #

    #print("Schedule post_status_and_events")
    #micropython.schedule(cls.post_status_and_events, None)
    cls.flag_post_status_and_events = True

    cls.status.display_page = PlanterStatus.PAGE_PUMP
    # Update display
    try:
        PL_DISPLAY.update_display_with_status(cls)
    except Exception as ex:
        _logger.exc(ex,"failed to update display: {e}".format(e=str(ex)))

    await asyncio.sleep_ms(1000)
    cls.status.display_mode = 0


async def control_pump(cls, ts_now, control_mode_tuple):
    global flow_ppl
    if cls.cycle_counter < 5:
        # Do not allow control_pump until we have executed at least 5 cycles
        return


    (cm_p, cm_c, cm_sm, cm_f, cm_d) = control_mode_tuple
    pump_status = cls.get_pump_status()

    bWaterLevelSensorDetected = cls.status.water_level_sensor_detected
    bWaterLevelLow = cls.status.level_low
    batt_v = cls.status.batt_v
    
    vbatt_min_for_pump = cls.status.get_vbatt_min_for_pump()

    elapsed_since_last_pump_s = ts_now - cls.status.ts_last_pump_start
    (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s) = cls.status.get_sm_params()
    if elapsed_since_last_pump_s > 600000000:
        cls.status.ts_last_pump_start = ts_now-sm_pump_min_period_s+20
        elapsed_since_last_pump_s = 0

    soil_moisture_data_available = cls.status.soil_moisture_data_available

    current_irrigation_pulses = flow.pulse_count()

    if flow_ppl is None:
        # Initialization of pulses_per_l using the received parameters
        try:
            flow_ppl = cls.status.work_flow_ppl()
            flow.set_pulses_per_l(flow_ppl)
            _logger.debug("Nominal flow pulses per litre factor {f}".format(f=flow_ppl))
        except Exception as ex:
            _logger.exc(ex,"failed to set PULSES_PER_LITRE parameter: {e}".format(e=str(ex)))
            _logger.debug("Params: {p}".format(p=str(cls.status.params)))
            flow_ppl = PINOUT.FLOW_PPL
            flow.set_pulses_per_l(flow_ppl)

    current_irrigation_vol_ml = float(current_irrigation_pulses) / flow_ppl

    cls.status.set_pump_details([pump_status, elapsed_since_last_pump_s, current_irrigation_pulses, current_irrigation_vol_ml])

    sm_available = cls.status.soil_moisture_data_available

    bDoStartCycle = False
    bDoEndCycle = False

    cls.reasons.clear()

    rh = float(cls.status.soil_moisture_vwc)

    forcedirrigation = False
    forcedirrigation_str = "False"
    forcedirrigation_dlmsg = None
    li_downlink_messages = cls.status.downlink_messages
    if li_downlink_messages is not None:
        for dlmsg in li_downlink_messages:
            if 'forcedirrigation' in dlmsg['Topic']:
                forcedirrigation = True
                forcedirrigation_dlmsg = dlmsg
                forcedirrigation_str = "{c}True{n}".format(c=colors.BOLD_PURPLE, n=colors.NORMAL)
                break


    if forcedirrigation:
        cm_p = False
        cm_sm = False
        cm_c = False
        cm_d = False
        cm_f = True

        
    
    #if cm_p or (cm_sm and not sm_available):
    #if cm_p or (cm_sm and (sm_available is False)):
    if cm_p:
        # PERIODIC CONTROL MODE IS ACTIVE
        periodic_mode_pump_period_s = cls.status.periodic_mode_pump_period_s
        periodic_mode_pump_max_duration_s = cls.status.periodic_mode_pump_max_duration_s
        periodic_mode_pump_max_volume_ml = cls.status.periodic_mode_pump_max_volume_ml

        if pump_status is False:
            # Pump is OFF -> Check if we need to start it
            if periodic_mode_pump_period_s is not None:
                if elapsed_since_last_pump_s >= periodic_mode_pump_period_s:
                    bDoStartCycle = True
                    cls.reasons.append("Periodic control - Pump is OFF, elapsed {e} [s], period {p} [s], batt_v {v} [V]".format(
                        e=elapsed_since_last_pump_s, p=periodic_mode_pump_period_s, v=batt_v))
        else:
            # Pump is ON -> Check if we need to stop it
            if (periodic_mode_pump_max_duration_s is not None) and (periodic_mode_pump_max_volume_ml is not None):
                if (elapsed_since_last_pump_s >= periodic_mode_pump_max_duration_s) or (current_irrigation_vol_ml>periodic_mode_pump_max_volume_ml):
                    bDoEndCycle = True
                    cls.reasons.append("Periodic control - Pump is ON, elapsed {e} [s], duration {d} [s], vol {v} [ml], max_vol {mv} [ml], pulses {p}".format(
                        e=elapsed_since_last_pump_s, d=periodic_mode_pump_max_duration_s,
                        v = current_irrigation_vol_ml, mv = periodic_mode_pump_max_volume_ml,
                        p = current_irrigation_pulses))

    elif cm_sm:
        # SOIL MOISTURE CONTROL MODE IS ACTIVE
        sm_low_th = float(cls.status.params["moisture_low_th"])
        periodic_mode_pump_max_duration_s = cls.status.periodic_mode_pump_max_duration_s

        if pump_status is False:
            # Pump is OFF -> Check if we need to start it
            if sm_available:
                if rh < sm_low_th:
                    msg = "Soil Moisture control - Pump is OFF, elapsed {e} [s], min period {p} [s], rh {rh}, th {th}, sm data available {a}, batt_v {v} [V]".format(
                                e=elapsed_since_last_pump_s, p=sm_pump_min_period_s, rh=rh, th=sm_low_th, a=soil_moisture_data_available, v=batt_v)
                    if elapsed_since_last_pump_s > sm_pump_min_period_s:
                        bDoStartCycle = True
                        cls.reasons.append(msg)
                    else:
                        _logger.debug("{msg} -> cannot start pump".format(msg=msg))
        else:
            # Pump is ON -> Check if we need to stop it
            max_volume_ml = cls.status.periodic_mode_pump_max_volume_ml
            #if (elapsed_since_last_pump >= periodic_mode_pump_max_duration_s) or (current_irrigation_vol_ml>max_volume_ml):
            if (elapsed_since_last_pump_s >= periodic_mode_pump_max_duration_s):
                bDoEndCycle = True
                cls.reasons.append("Soil Moisture control - Pump is ON, elapsed {e} [s], min period {p} [s], max duration {d} [s], rh {rh}, th = {th}, sm data available {a}, vol {cv}, max vol {mv}".format(
                        e=elapsed_since_last_pump_s,
                        p=sm_pump_min_period_s, d = periodic_mode_pump_max_duration_s,
                        rh=rh, th=sm_low_th, a=soil_moisture_data_available,
                        cv = current_irrigation_vol_ml, mv=max_volume_ml))

    elif cm_c:
        # CALENDAR CONTROL MODE IS ACTIVE
        current_second = ts_now % (3600*24)
        cal = cls.status.calendar
        
        sm = None
        
        a = cls.status.soil_moisture_data_available
        if a:
            (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s) = cls.status.get_sm_params()
            sm = cls.status.soil_moisture_vwc
        
        if pump_status is False:
            # Pump is OFF -> Check if we need to start it
            for start_s, cal_data in cal.items():
                elapsed_since_start_s = current_second - start_s
                cal_moisture_low_th = cal_data[CFG._CAL_DATA_MOISTURE_LOW_TH_POSITION]
                if cal_moisture_low_th is None or ((sm is not None) and (sm < cal_moisture_low_th)):
                    cal_start_str = cal_data[CFG._CAL_DATA_START_STR_POSITION]
                    aux_max_duration_s = int(cal_data[CFG._CAL_DATA_MAX_DURATION_POSITION] or 0)
                    d2 = max(aux_max_duration_s, PINOUT.POWERUP_TIME_S)*2
                    if elapsed_since_start_s > 0 and elapsed_since_start_s < d2 and elapsed_since_last_pump_s > d2:
                        # (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
                        dt = cls.rtc.datetime()
                        msg = "Calendar control - Pump is OFF, Start at {start}, now {hh:02}:{mm:02}:{ss:02}, elapsed since last pump {e} [s], batt_v {v} [V]".format(
                                    start = cal_start_str, hh=dt[4], mm=dt[5], ss=dt[6],
                                    e=elapsed_since_last_pump_s, v=batt_v)

                        bDoStartCycle = True
                        cls.reasons.append(msg)
                        cls.calendar_data = cal_data
                if cal_moisture_low_th is not None and sm is None:
                    #_logger.debug("Calendar control - skip {d} because it depends on soil moisure measure and it is not available".format(d=str(cal_data)))
                    pass


        else:
            # Pump is ON -> Check if we need to stop it
            if cls.calendar_data is not None:
                max_duration_s = cls.calendar_data[CFG._CAL_DATA_MAX_DURATION_POSITION]
                max_volume_ml = cls.calendar_data[CFG._CAL_DATA_MAX_VOLUME_POSITION]
                cal_moisture_low_th = cal_data[CFG._CAL_DATA_MOISTURE_LOW_TH_POSITION]
                if (elapsed_since_last_pump_s >= max_duration_s) or (current_irrigation_vol_ml>max_volume_ml) or (cal_moisture_low_th is not None and sm > cal_moisture_low_th):
                    bDoEndCycle = True
                    msg = "Calendar control - Pump is ON, elapsed {e} [s], vol {cv}, max vol {mv}, sm th {th}, sm {sm}".format(
                            e=elapsed_since_last_pump_s, cv = current_irrigation_vol_ml, mv=max_volume_ml, th=cal_moisture_low_th, sm=sm)
                    cls.reasons.append(msg)
            else:
                bDoEndCycle = True
                msg = "Calendar control - Pump is ON, elapsed {e} [s], vol {cv} - calendar data is None".format(
                        e=elapsed_since_last_pump_s, cv = current_irrigation_vol_ml)
                cls.reasons.append(msg)

    elif cm_f:
        # FORCED CONTROL MODE IS ACTIVE
        periodic_mode_pump_period_s = PINOUT.PUMP_ON_PERIOD_S
        periodic_mode_pump_max_duration_s = PINOUT.PUMP_ON_DURATION_S

        if pump_status is False:
            # Pump is OFF -> Check if we need to start it
            if periodic_mode_pump_period_s is not None:
                if elapsed_since_last_pump_s >= periodic_mode_pump_period_s:
                    bDoStartCycle = True
                    cls.reasons.append("Forced control - Pump is OFF, elapsed {e} [s], period {p} [s], batt_v {v} [V], downlink message forcedirrigation = {f} ".format(
                        e=elapsed_since_last_pump_s, p=periodic_mode_pump_period_s, v=batt_v, f=forcedirrigation_str))
        else:
            # Pump is ON -> Check if we need to stop it
            if (periodic_mode_pump_max_duration_s is not None):
                if (elapsed_since_last_pump_s >= periodic_mode_pump_max_duration_s):
                    bDoEndCycle = True
                    cls.reasons.append("Forced control - Pump is ON, elapsed {e} [s], duration {d} [s], vol {v} [ml], pulses {p}, downlink message forcedirrigation = {f} ".format(
                        e=elapsed_since_last_pump_s, d=periodic_mode_pump_max_duration_s,
                        v = current_irrigation_vol_ml,
                        p = current_irrigation_pulses,
                        f=forcedirrigation_str))
                    

        pass
    elif cm_d:
        # Disabled
        if pump_status is True:
            bDoEndCycle = True
            cls.reasons.append("Disabled")



            


    # Protection: 
    # If pump is started and elapsed time is 5 or more seconds but
    #       there is no flow or 
    #       pump consumption is below the threshold (because it is pumping air or malfunction)
    # Then stop the pump

    iprot_time = cls.status.iprot_time
    iprot_minpulses = cls.status.iprot_minpulses

    if pump_status is True and (elapsed_since_last_pump_s>iprot_time):
        has_flow_meter = cls.status.has_flow_meter
        if has_flow_meter and (current_irrigation_pulses < iprot_minpulses) and PINOUT.ENABLE_PUMP_AND_BATTERY_CHECKS:
            bDoEndCycle = True
            if bWaterLevelLow:
                low_str = "LOW"
            else:
                low_str = "NORMAL"
            cls.reasons.append("Measured water level is {l}. After {e} [s], only {p} flow pulses have been received -> insufficient flow".format(
                e=elapsed_since_last_pump_s, p=current_irrigation_pulses, l=low_str))
        
        if cls.status.has_ina3221_12v and PINOUT.ENABLE_PUMP_AND_BATTERY_CHECKS:
            pump_i = cls.status.pump_i
            if pump_i < PINOUT.A_PUMP_MIN:
                bDoEndCycle = True
                cls.reasons.append("Pump current {i} [A] is below threshold {th} -> Either there is no water or the pump is not working properly".format(i=pump_i, th=PINOUT.A_PUMP_MIN))
            th = (vbatt_min_for_pump-1.0)
            if batt_v < th:
                bDoEndCycle = True
                if batt_v > 0:
                    cls.reasons.append("Battery voltage {v} [V] is below {th} (1V below the configured minimum) -> Either the battery is discharged or in bad condition".format(v=batt_v, th=th))
                else:
                    cls.reasons.append("Battery voltage {v} [V] -> Either the battery is disconnected or the power monitor that measures the battery is broken".format(v=batt_v))

    

    if bDoStartCycle:

        if PINOUT.PUMP_ENABLE_LEVEL_CHECK:
            if bWaterLevelSensorDetected and bWaterLevelLow:
                # Cannot start irrigation because water level is low
                #cls.reason = "Cannot start irrigation because water level sensor has been detected and level is low"
                #_logger.warning(cls.reason)
                #return
                msg=("Water level is low. The pump will start, but will stop if no flow is detected or too-low current consumption is detected")
                cls.reasons.append(msg)
                _logger.debug(msg)


        rain_th_mmph = cls.status.rain_th_mmph
        rain_mmph = cls.status.rain_mmph

        if (rain_th_mmph is not None) and (rain_mmph is not None):
            if rain_mmph > rain_th_mmph:
                # Cannot start irrigation because rain mmph is higher than the threshold
                msg = "Cannot start irrigation because rain {rain_mmph} [mmph] is higher than the threshold {rain_th_mmph} [mmph]".format(rain_mmph=rain_mmph, rain_th_mmph=rain_th_mmph)
                cls.reasons.append(msg)
                _logger.warning(msg)
                # Set the ts_last_pump_start so we can go to sleep
                cls.status.ts_last_pump_start = ts_now

                # EVENT -> Decided not to start irrigation because rain mmph is higher than threshold
                cls.status.add_event(PlanterEvents.Irrigation_Decission, PlanterEvents.ID_RAIN_INTENSITY,msg)

                return

        rain_prob_th = cls.status.rain_prob_th
        rain_prob = cls.status.rain_prob

        if (rain_prob_th is not None) and (rain_prob is not None):
            if rain_prob > rain_prob_th:
                # Cannot start irrigation because rain mmph is higher than the threshold
                msg = "Cannot start irrigation because rain probability {rain_prob} [%] is higher than the threshold {rain_prob_th} [%]".format(
                    rain_prob=rain_prob, rain_prob_th=rain_prob_th)
                cls.reasons.append(msg)
                _logger.warning(msg)
                # Set the ts_last_pump_start so we can go to sleep
                cls.status.ts_last_pump_start = ts_now

                # EVENT -> Decided not to start irrigation because rain probability is higher than threshold
                cls.status.add_event(PlanterEvents.Irrigation_Decission, PlanterEvents.ID_RAIN_PROB,msg)

                return


        if PINOUT.ENABLE_PUMP_AND_BATTERY_CHECKS:
            if batt_v < vbatt_min_for_pump:
                # Cannot start irrigation because battery voltage is low
                msg = "Cannot start irrigation because battery voltage {v} [V] is below threshold {th} [V]".format(v=batt_v, th=vbatt_min_for_pump)
                cls.reasons.append(msg)
                _logger.warning(msg)
                # Set the ts_last_pump_start so we can go to sleep
                cls.status.ts_last_pump_start = ts_now
                
                # EVENT -> Decided not to start irrigation because battery voltage is below limit
                cls.status.add_event(PlanterEvents.Irrigation_Decission, PlanterEvents.ID_BATTERY_VOLT,msg)
                
                return
            else:
                msg = ("Can start pump because battery voltage {v} [V] is over the threshold {th} [V]. Current soil moisture is {rh} %, rain {rain_mmph} [mmph]".format(
                    v=batt_v, th=vbatt_min_for_pump, rh=rh, rain_mmph=rain_mmph))
                cls.reasons.append(msg)
                _logger.debug(msg)
        else:
                msg = ("Can start pump because battery check is disabled. Battery voltage is {v} [V], threshold is {th} [V]. Current soil moisture is {rh} %, rain {rain_mmph} [mmph]".format(
                    v=batt_v, th=vbatt_min_for_pump, rh=rh, rain_mmph=rain_mmph))
                cls.reasons.append(msg)
                _logger.debug(msg)

        cls.reason = ",".join(cls.reasons)
        
        # EVENT -> Decided to start irrigation
        cls.status.add_event(PlanterEvents.Irrigation_Decission, PlanterEvents.ID_START_IRRIGATION,cls.reason)
                
        await start_irrigation_cycle(cls, cls.reason)
        
    elif bDoEndCycle:
        cls.reason = ",".join(cls.reasons)
        await end_irrigation_cycle(cls, cls.reason)

        if forcedirrigation:
            # Remove the item because the forced irrigation has been executed
            _logger.debug("Remove downlink message '{m}' because it has already been executed".format(m=str(json.dumps(forcedirrigation_dlmsg))))
            cls.status.downlink_messages.remove(forcedirrigation_dlmsg)
            
            li_downlink_messages = cls.status.downlink_messages
            if li_downlink_messages is not None:
                for dlmsg in li_downlink_messages:
                    if 'forcedirrigation' in dlmsg['Topic']:
                        cls.status.downlink_messages.remove(dlmsg)
            
            _logger.debug("Resulting downlink messages list: {l}".format(l=json.dumps(cls.status.downlink_messages)))



async def control_sleep(cls, ts_now):
    control_sleep_debug = logging.DEBUG
    if control_sleep_debug<=logging.DEBUG:
        _logger.debug("control_sleep(now={t})".format(t=ts_now))

    if cls.get_pump_status():
        # Pump is ON
        if control_sleep_debug<=logging.DEBUG:
            _logger.warning("Cannot sleep because the PUMP is ON")
        return

    has_pm_measures = power_monitor.has_measures()
    if has_pm_measures is False:
        await cls.do_power_measure()

    sm_available = False
    bWaterLevelLow = False
    batt_v = None
    vbatt_min_for_pump = None

    try:
        sm_available = cls.status.soil_moisture_data_available
        bWaterLevelLow = cls.status.level_low
        batt_v = cls.status.batt_v
        
        vbatt_min_for_pump = cls.status.get_vbatt_min_for_pump()
    except Exception as ex:
            _logger.exc(ex,"Failed to control sleep: Error getting status: {e}".format(e=str(ex)))

    if (batt_v is not None) and (vbatt_min_for_pump is not None):
        bBattVIsLow = (batt_v < vbatt_min_for_pump)
    else:
        bBattVIsLow = False

    if batt_v is None:
        batt_v = 0

    if (cls.cycle_counter < 5) or ((cls.cycle_counter < 10) and (sm_available is False)):
        # Do not allow control_pump until we have executed at least 5 cycles
        return

    await _control_sleep_lock.acquire()

    try:
        (elapsed_since_last_pump, ts_next_pump_start, pending_seconds, need_to_start_pump_cycle, irr_cause) = calc_ts_next_pump_start(cls.status)

        if pending_seconds < -200:
            # Incorrect number, just rewrite
            pending_seconds = 600
    except Exception as ex:
            _logger.exc(ex,"Failed to control sleep: Error in calc_ts_next_pump_start: {e}".format(e=str(ex)))
            pending_seconds = 600
            need_to_start_pump_cycle = False


    # Note: We are starting irrigation cycles even when the water level is low, so
    # a low water level should not be a flag to abort starting and going to sleep
    #
    # Note: If battery checks are disabled, then 
    # low battery should not be a flat to abort starting and going to sleep
    #
    if need_to_start_pump_cycle and ( 
            (
                #(bWaterLevelLow is False) and
                (bBattVIsLow is False)
            ) or (PINOUT.ENABLE_PUMP_AND_BATTERY_CHECKS==False)
        ):
        
        if control_sleep_debug<=logging.DEBUG:
            _logger.debug("Cannot sleep because we need to start a PUMP cycle")
        _control_sleep_lock.release()
        return


    pending_s_to_get_params = cls.status.pending_s_to_get_params()

    # Note: We are starting irrigation cycles even when the water level is low, so
    # a low water level should not affect the sleep time
    if (need_to_start_pump_cycle is True) and (
            #(bWaterLevelLow is True) or 
            (bBattVIsLow is True)
         ):
        # We have to start pumping and water level is low or battery voltage is low, so we cannot pump
        # In this case we set seconds_to_sleep the time pending to get params
        seconds_to_sleep = pending_s_to_get_params
    else:
        seconds_to_sleep = pending_seconds


    pending_s_to_get_params = cls.status.pending_s_to_get_params()
    if (pending_s_to_get_params > 0) and (pending_s_to_get_params < pending_seconds):
        # We will wake up to get params
        seconds_to_sleep = pending_s_to_get_params

    # Control de wakening period parameter
    try:
        if K_WAKENING_PERIOD in cls.status.params:
            wakening_period = int(cls.status.params[K_WAKENING_PERIOD])
        else:
            # default value 24h
            wakening_period = 24*3600
    except:
        # default value 24h
        wakening_period = 24*3600

    if seconds_to_sleep > wakening_period:
        seconds_to_sleep = wakening_period

    # If door is open, then sleep max 15min
    if cls.status.door_open:
        door_open_max_sleep_s = cls.status.get_door_open_max_sleep_s()
        if seconds_to_sleep > door_open_max_sleep_s:
            seconds_to_sleep = door_open_max_sleep_s


    # Substract the time that the controller needs to powerup
    seconds_to_sleep -= PINOUT.POWERUP_TIME_S
    hasToSleep = seconds_to_sleep > PINOUT.MIN_SLEEP_TIME_S

    if hasToSleep is False:
        if control_sleep_debug<=logging.DEBUG:
            _logger.debug("Cannot sleep because {t} seconds to sleep is below the minimum time of {th}".format(t=seconds_to_sleep, th=PINOUT.MIN_SLEEP_TIME_S))

    #
    # If SoilMoisture control mode is enabled
    # make sure that we have read soil moisture data
    # before going to sleep
    #

    cm_sm = cls.status.is_soil_moisture_control_mode_active()
    has_sm_data = cls.status.soil_moisture_data_available
    (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s) = cls.status.get_sm_params()
    if cm_sm is True:
        if hasToSleep and elapsed_since_last_pump>sm_pump_min_period_s:
            if has_sm_data is False:
                if cls.status.soil_moisture_read_trial < PINOUT.SOIL_MOISTURE_MAX_READ_TRIALS_BEFORE_SLEEP:
                    # We need more time to read the sensor
                    hasToSleep = False
                    if control_sleep_debug<=logging.DEBUG:
                        _logger.debug("Cannot sleep because soil moisture control mode is active and we still have not read sm data (read trials {i} of {n})".format(i=cls.status.soil_moisture_read_trial , n=PINOUT.SOIL_MOISTURE_MAX_READ_TRIALS_BEFORE_SLEEP))

        if seconds_to_sleep > sm_mode_max_sleep_s:
            # Limit the sleep time so we have a frequent soil moisture verification
            seconds_to_sleep = sm_mode_max_sleep_s


    

    if hasToSleep:
        ticks_ms_now = utime.ticks_ms()
        ts_last_button1_pressed_ticks_ms = cls.status.ts_last_button1_pressed_ticks_ms
        elapsed_since_last_press = (utime.ticks_diff(ticks_ms_now, ts_last_button1_pressed_ticks_ms))/1000
        if elapsed_since_last_press > 0 and elapsed_since_last_press < PINOUT.MIN_TIME_FROM_BUTTON_PRESS_TO_SLEEP_S:
            # We are using the display, so we should not go to sleep
            hasToSleep = False
            if control_sleep_debug<=logging.DEBUG:
                _logger.debug("Cannot sleep because pressed button {t} [s] ago".format(t=elapsed_since_last_press))


    # if hasToSleep and False:
    #     nbClients = webapp.GetNbAsyncSockets()
    #     if nbClients > 0:
    #         hasToSleep = False
    #         if control_sleep_debug<=logging.DEBUG:
    #             _logger.debug("Cannot sleep because there are {n} clients connected to the web".format(n=nbClients))

    if seconds_to_sleep > PINOUT.MAX_SECONDS_TO_SLEEP:
        # Limit
        seconds_to_sleep = PINOUT.MAX_SECONDS_TO_SLEEP


    if hasToSleep:

        now_s = utime.time()
        wakeup_time_s = now_s + seconds_to_sleep
        wakeup_dt = time.localtime(wakeup_time_s)
        wakeup_dt_str = "{hh:02}:{mm:02}:{ss:02}".format(hh=wakeup_dt[3], mm=wakeup_dt[4], ss=wakeup_dt[5])

        PL_DISPLAY.update_display((['Post','status','Sleep','{s} [s]'.format(s=seconds_to_sleep)], True))
        sleep_str = "Deepsleep for {s} [s] until {wakeup_dt_str} - pump {pump} [s], params {params} [s], cm_sm = ({cm_sm}, {has_data}, rh {rh}, th {th}, max_sleep {ms} [s], trial {tr}, limit {trl})".format(
            s=seconds_to_sleep, wakeup_dt_str=wakeup_dt_str,
            pump=pending_seconds, params=pending_s_to_get_params,
            cm_sm=cm_sm, has_data = has_sm_data, rh=cls.status.soil_moisture_vwc, th=cls.status.soil_moisture_th,
            ms = sm_mode_max_sleep_s, tr = cls.status.soil_moisture_read_trial, trl=PINOUT.SOIL_MOISTURE_MAX_READ_TRIALS_BEFORE_SLEEP)

        cls.status.add_event(PlanterEvents.Wake, PlanterEvents.STATUS_OFF, sleep_str)

        _logger.debug("{g}------------- PREPARE FOR DEEP SLEEP ---------------{n}".format(g=colors.BOLD_GREEN, n=colors.NORMAL))


        sleep_str = "{c}Deepsleep for {s} [s] until {wakeup_dt_str} {n} - pump {pump} [s], params {params} [s], cm_sm = ({cm_sm}, {has_data}, rh {rh}, th {th}, max_sleep {ms} [s], trial {tr}, limit {trl})".format(
            c=colors.BOLD_PURPLE, n=colors.NORMAL,
            s=seconds_to_sleep,  wakeup_dt_str=wakeup_dt_str, 
            pump=pending_seconds, params=pending_s_to_get_params,
            cm_sm=cm_sm, has_data = has_sm_data, rh=cls.status.soil_moisture_vwc, th=cls.status.soil_moisture_th,
            ms = sm_mode_max_sleep_s, tr = cls.status.soil_moisture_read_trial, trl=PINOUT.SOIL_MOISTURE_MAX_READ_TRIALS_BEFORE_SLEEP)

        _logger.info(sleep_str)


        # Need to post in order to clear lists and reduce size
        try:
            await COMM.post_status_and_events(cls, True)
        except Exception as ex:
            _logger.exc(ex,"Failed to post status and events", nopost=True)
            pass

        # Disable any further communication
        try:
            cls.comm_enabled = False
            COMM.disable()
        except Exception as ex:
            _logger.exc(ex,"Failed to disable comms", nopost=True)
            pass

        # Prepare to sleep
        try:
            cls.status.store_status()
        except Exception as ex:
            _logger.exc(ex,"Failed to store status", nopost=True)
            pass


        # Stop network
        PL_DISPLAY.update_display((['Stop','network','Sleep','{s} [s]'.format(s=seconds_to_sleep)], True))
        try:
            try:
                stop_event = NetworkMgr.stop_event()
                NetworkMgr.stop()

                try:
                    await asyncio.wait_for_ms(stop_event.wait(), 12000)
                except Exception as ex:
                    # Power off manually
                    _logger.exc(ex, "Failed to stop NetworkMgr. Disconnect WiFi and poweroff modem ...", nopost=True)
                    await NetworkMgr.hard_stop()
            except Exception as ex:
                # Power off manually
                _logger.exc(ex, "Failed to stop NetworkMgr. Disconnect WiFi and poweroff modem ...", nopost=True)
                await NetworkMgr.hard_stop()
        except:
            # Just go on with power down
            pass


        # Power off devices
        try:
            PL_DISPLAY.poweroff()
        except Exception as ex:
            _logger.exc(ex,"Failed to power off display", nopost=True)
            pass

        try:
            await cls.enable_power(False)
        except Exception as ex:
            _logger.exc(ex,"Failed to disable load's power lines", nopost=True)
            pass

        # Shut down MODBUS and release UART
        try:
            sm_task.release_sm_sensor()
        except Exception as ex:
            _logger.exc(ex,"Failed to release the soil moisture sensor", nopost=True)
            pass

        

        if PINOUT.WDT_ENABLED:
            wdt_time_s = seconds_to_sleep+60
            try:
                cls.wdt = machine.WDT(timeout=wdt_time_s*1000)
            except Exception as ex:
                _logger.exc(ex,"Failed to set WDT to {s} before going to sleep".format(s=wdt_time_s), nopost=True)

        

        # Allow time to print the debug output and disconnect wlan
        time.sleep(1)

        # Clear accelerometer interrupts
        # Accelerometer interrupt
        try:
            if cls.accelerometer is not None:
                
                cls.set_sensor_motion_threshold(factor=1)
                
                if cls.accelerometer.name == "ADXL34x":
                    r = cls.accelerometer.data_format
                    _logger.debug("ADXL345 data format: {r}".format(r=r))

                    r = str(cls.accelerometer.enabled_interrupts)
                    _logger.debug("ADXL345 enabled interrupts: {r}".format(r=r))
                    
                    r = str(cls.accelerometer.interrupt_map)
                    _logger.debug("ADXL345 interrupt map: {r}".format(r=r))
                    
                    r = str(cls.accelerometer.thresholds)
                    _logger.debug("ADXL345 thresholds: {r}".format(r=r))
                
                aux_n = 0
                retCode = True
                while retCode and (aux_n < 100):
                    (retCode, impact_str) = cls.accelerometer.interruptChecker()
                    aux_n = aux_n +1
                if retCode:
                    _logger.error("Failed to clear accelerometer interrupts")
                    
        except Exception as ex:
            _logger.exc(ex,"Failed to clear accelerometer interrupts", nopost=True)
            pass

        h = cls.status.has_mcp

        if hwversion.HW_VERSION == hwversion.VERSION_TCALL_14:
            l = esp32.WAKEUP_ALL_LOW
            l_str = "WAKEUP_ALL_LOW"
        elif hwversion.HW_VERSION == hwversion.VERSION_TCALL_MPU:
                l = esp32.WAKEUP_ALL_LOW
                l_str = "WAKEUP_ALL_LOW"
        elif hwversion.HW_VERSION == hwversion.VERSION_10:
            l = esp32.WAKEUP_ANY_HIGH
            l_str = "WAKEUP_ANY_HIGH"

        #ma = PINOUT.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP
        ma = cls.status.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP
        mb = PINOUT.MCP_B_INTERRUPT_ENABLE_FOR_WAKEUP
        _logger.debug("Set interrupt mask to A={a}, B={b}".format(a=ma, b=mb))
        
        a = 0
        b = 0
        try:
            if h:
                # Restrict interrupt configuration
                cls.mcp.porta.interrupt_enable = ma
                cls.mcp.portb.interrupt_enable = mb

                # Clear any DIA interrupt
                # Clear previous interrupt if any
                v = cls.mcp.porta.interrupt_captured
                v = cls.mcp.portb.interrupt_captured
                v = cls.mcp.porta.interrupt_flag
                v = cls.mcp.portb.interrupt_flag

                # Read current value
                a=cls.mcp.porta.gpio
                b=cls.mcp.portb.gpio
            else:
                a = 0
                b = 0
                ma = 0
                mb = 0
        except:
            _logger.exc(ex,"Failed to clear and configure MCP interrupts", nopost=True)
            pass

        _logger.debug('DIA interrupt: pin {p} -> HasMCP {h}, A = {a:08b} mask {ma:08b} B = {b:08b} mask {mb:08b}, wakeup level = {l_str}'.format(
            p=cls.dia_interrupt_pin, h=h, a=a, b=b, ma=ma, mb=mb, l_str=l_str))
            #utime.sleep_ms(250)

        esp32.wake_on_ext0( cls.dia_interrupt, level = l)

        try:
            # Set pin 13 with no pullup or as output with low lever so the LED is not power-up while sleeping
            p13 = Pin(PINOUT.RS485_RXD, Pin.OUT, value=0)
            p13.init(mode=Pin.OUT, pull=Pin.PULL_DOWN, value=0)
        except:
            _logger.exc(ex,"Failed to set pin {p} as output with value 0 and pull-down".format(p=PINOUT.RS485_RXD), nopost=True)
            pass

        #p13.off()

        #
        # Final adjustment of time to sleep
        #
        final_now_s = utime.time()

        aux_elapsed_s = final_now_s - now_s
        if aux_elapsed_s > 0:
            # adjust time to sleep
            seconds_to_sleep = seconds_to_sleep - aux_elapsed_s

        wakeup_time_s = final_now_s + seconds_to_sleep
        wakeup_dt = time.localtime(wakeup_time_s)
        wakeup_dt_str = "{hh:02}:{mm:02}:{ss:02}".format(hh=wakeup_dt[3], mm=wakeup_dt[4], ss=wakeup_dt[5])

        _logger.debug("=============================================")
        _logger.debug("SLEEP FOR {s} [s] until {wakeup_dt_str}".format(s=seconds_to_sleep, wakeup_dt_str=wakeup_dt_str))
        _logger.debug("=============================================")

        # Allow time to complete changes
        time.sleep(2)

        # Sleep
        machine.deepsleep(seconds_to_sleep*1000)

        #machine.lightsleep(seconds_to_sleep*1000)

    _control_sleep_lock.release()



async def pump_control_task(cls):
    _logger.debug("Pump control TASK started")
    # Let the rest of the system to start
    await asyncio.sleep(10)
    while True:
        try:
            # Control pump
            ts_now = utime.time()
            ps = False
            try:
                control_mode_tuple= cls.status.get_control_mode_tuple()
                await control_pump(cls, ts_now, control_mode_tuple)
                ps = cls.get_pump_status()
            except Exception as ex:
                msg = "pump_control_task control_pump failed: {e}".format(e=str(ex))
                _logger.exc(ex,msg)
                # Ensure that the pump is OFF
                s = io.StringIO()
                sys.print_exception(ex, s)
                irrigationid = cls.status.current_irrigationid()
                full_explanation = "irrigationid={irrigationid} - {msg} - {t}".format(msg=msg, t=s.getvalue(),irrigationid=irrigationid)
                await cls.enable_pump(False, full_explanation)
                ps = False

            try:
                if ps is None or not ps:
                    await control_sleep(cls, ts_now)
            except Exception as ex:
                _logger.exc(ex,"failed to control sleep: {e}".format(e=str(ex)))

            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
        except Exception as ex:
            _logger.exc(ex,"Failed to control pump and sleep: {e}".format(e=ex))
            ps = False

        t = 200 if ps else 10000
        await asyncio.sleep_ms(t)

