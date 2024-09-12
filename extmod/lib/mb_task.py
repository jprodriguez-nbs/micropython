import logging
import machine
import  asyncio
import gc
gc.collect()
from uModBus.async_serial import AsyncSerial
gc.collect()

try:
    from constants import *
except:
    from app.frozen.constants import *
    
from umdc.status import *
import umdc_pinout as PINOUT

from ubinascii import hexlify

gc.collect()

_modbus_obj = None
_mb_params = {}

_logger = logging.getLogger("MB_TASK")
_logger.setLevel(logging.DEBUG)

_li_requests = []
_li_requests_lock = asyncio.Lock()
_stop = False
_li_ei_previous_responses = {}
_di_slave_ok = {}

def is_modbus_defined():
    return _modbus_obj is not None

def set_modbus_debug(l):
    if _modbus_obj:
        _modbus_obj.debug = l

def init_mb_task(core):
    global _modbus_obj
    global _mb_params

    try:
        uart_id = PINOUT.RS485_UART
        
        _mb_params = core.status.mb_params
        
        if _modbus_obj is None:
            
            baudrate = _mb_params['baudrate']
            bits = _mb_params['bits']
            parity = _mb_params['parity']
            p_str = parity2str(parity)
            stop_bits = _mb_params['stop']
            
            msg = "Init modbus at (UART={id}, TX={tx}, RX={rx}) with (baud={baudrate}, bits={bits}, parity={parity}, stop={stop})".format(
                id=uart_id, tx=PINOUT.RS485_TXD, rx=PINOUT.RS485_RXD,
                baudrate = baudrate,
                bits = bits,
                parity = p_str,
                stop = stop_bits
                )
            _logger.info(msg)
            _modbus_obj = AsyncSerial(uart_id, tx_pin=PINOUT.RS485_TXD, rx_pin=PINOUT.RS485_RXD,
                                    baudrate=baudrate, data_bits=bits,
                                    stop_bits=stop_bits, parity=parity)

            _modbus_obj.debug = False
            _modbus_obj.read_async = True
    except Exception as ex:
        debug_msg = "init_mb_task Exception {e}".format(e=str(ex))
        _logger.exc(ex, debug_msg)

async def _mb_process_requests_list(requests):
    global _last_free_mem
    li_responses = []
    di_slave_result = {}
    gc.collect()
    if requests and len(requests)>0:
        _logger.debug("MB Task - process requests list {n}".format(n=len(requests)))
        for serial_pdu_hex in requests:
            try:
                serial_pdu = bytes.fromhex(serial_pdu_hex)
                slave_id = serial_pdu[0]
                if slave_id not in di_slave_result or di_slave_result[slave_id]==True:
                    response_pdu = await _modbus_obj.send_receive_raw(serial_pdu, count=True)
                    if response_pdu and len(response_pdu):
                        response_pdu_hex = hexlify(response_pdu).decode()
                        debug_msg = "MB '{request}' -> '{response}'".format(request=serial_pdu_hex, response=response_pdu_hex)
                        _logger.info(debug_msg)
                        li_responses.append(response_pdu_hex)
                        di_slave_result[slave_id]=True
                    else:
                        di_slave_result[slave_id]=False
                        li_responses.append(None)
            except Exception as ex:
                debug_msg = "MB '{request}' to slave {slave_id} failed -> Exception {e}".format(request=serial_pdu_hex, slave_id=slave_id, e=str(ex))
                _logger.exc(ex, debug_msg)
                li_responses.append(None)
                di_slave_result[slave_id]=False
                
        _logger.debug("MB Task - process requests list finished")
    
    # Memory control
    tools.free(False)
    
    return li_responses

def release_mb_sensor():
    global _modbus_obj
    if _modbus_obj is not None:
        del _modbus_obj
        _modbus_obj = None

async def do_read_mb(core):
    global _modbus_obj
    global _li_requests
    global _li_requests_lock
    

    try:  
        #_logger.debug("MB TASK - CYCLE")

        if _modbus_obj is None:
            # Resources have been released -> do not read
            return
        
        #
        # GET MODBUS OPERATION PARAMETERS
        #
        params = core.status.params
        messages = params[K_MESSAGES]
        acquisition_time = int(messages[K_ACQUISITION_TIME]) # Time in minutes between modbus slaves, starting at minute 0 and multiples
        report_time = int(messages[K_REPORT_TIME])           # Time in minutes between readings report, starting at minute 0 and multiples
        all_requests = messages[K_REQUESTS]
        external_inputs = tools.get_parts(params[K_EI])
        
        li_ei_slave_id = []
        has_ei = False
        for ei in external_inputs:
            ei = int(ei)
            if ei > 0:
                li_ei_slave_id.append("{ei:02x}".format(ei))
                has_ei = True
        
        ei_requests = []
        if has_ei:
            for request in all_requests:
                slave_id_str = request[0:2]
                if slave_id_str in li_ei_slave_id:
                    ei_requests.append(request)
        
        
        #
        # CONTROL TIME
        #
        ts_now = utime.time()
        dt = core._rtc.datetime()
        # (year, month, mday, week_of_year, hour, minute, second, milisecond)
        minute_within_hour = int(dt[5])
        
        if minute_within_hour == 0:
            # Start of the hour is always True
            is_acquisition_time_multiple = True
            is_report_time_multiple = True
        else:
            is_acquisition_time_multiple = (minute_within_hour % int(acquisition_time)) == 0
            is_report_time_multiple = (minute_within_hour % int(report_time)) == 0
        
        has_to_read_all = False
        has_to_report = False
        
        if is_acquisition_time_multiple:
            if core.status.mb_ts_last_acquisition_time is None:
                has_to_read_all = True
            else:
                elapsed_s_since_last_acquisition = ts_now - core.status.mb_ts_last_acquisition_time
                if elapsed_s_since_last_acquisition >= (acquisition_time*60):
                    has_to_read_all = True
            
        
        if is_report_time_multiple:
            if core.status.mb_ts_report_time is None:
                has_to_report = True
            else:
                elapsed_s_since_last_report = ts_now - core.status.mb_ts_report_time
                if elapsed_s_since_last_report >= (report_time*60):
                    has_to_report = True
                 
                 
        if has_to_read_all or has_to_report:
            requests = all_requests
            core.status.mb_ts_last_acquisition_time = ts_now
        else:
            requests = ei_requests
            
                 
                    
        #
        # SPECIFIC REQUESTS RECEIVED WITH MODBUS_REQUEST COMMAND
        #
        aux_li_requests = None
        async with _li_requests_lock:
            if len(_li_requests):
                aux_li_requests = _li_requests
                _li_requests.clear()
        if aux_li_requests is not None and len(aux_li_requests):
            li_responses = await _mb_process_requests_list(aux_li_requests)
            for response in li_responses:
                try:
                    await core.modbus_response(response)
                except Exception as ex:
                    debug_msg = "MB core.modbus_response Exception {e}".format(e=str(ex))


        #
        # SCHEDULED REQUESTS CONFIGURED WITH MESSAGES CONFIGURATION
        #
        if requests is not None and len(requests):
            li_responses = await _mb_process_requests_list(requests)
            try:
                # Evaluate responses
                di_slave_ok = {}
                di_responses_by_slave_id = {}
                nb_requests = len(requests)
                nb_answers = len(li_responses)
                if (nb_requests != nb_answers):
                    print("MB Error: Received {a} answers for {r} requests".format(a=nb_answers, r=nb_requests))
                n = min(nb_answers, nb_requests)
                for idx in range(n):
                    request = requests[idx]
                    response = li_responses[idx]
                    slave_id_str = request[0:2]
                    if slave_id_str not in di_slave_ok:
                        di_slave_ok[slave_id_str] = True
                        di_responses_by_slave_id[slave_id_str] = []
                    if response is None:
                        di_slave_ok[slave_id_str] = False
                        di_responses_by_slave_id[slave_id_str].append(response)
                
                # Update global dictionary
                ei_responses_changed = False
                for slave_id_str in di_slave_ok:
                    v = di_slave_ok[slave_id_str]
                    _di_slave_ok[slave_id_str] = v
                    # If this slave_id corresponds to external_input device
                    if slave_id_str in li_ei_slave_id:
                        # Compare with cache
                        if slave_id_str not in _li_ei_previous_responses:
                            ei_responses_changed = True
                        else:
                            if di_responses_by_slave_id[slave_id_str] != _li_ei_previous_responses[slave_id_str]:
                                ei_responses_changed = True
                        # Update cache
                        _li_ei_previous_responses[slave_id_str] = di_responses_by_slave_id[slave_id_str]

                if ei_responses_changed:
                    has_to_report = True

                # Count number for slaves not answering
                nb_ko_slaves = 0            
                for slave_id_str in _di_slave_ok:
                    v = _di_slave_ok[slave_id_str]
                    if v is False:
                        nb_ko_slaves = nb_ko_slaves + 1
                        
                # Calculate slave_fail field
                if nb_ko_slaves == 0:
                    new_mb_slave_fail = 0
                elif nb_ko_slaves < len(_di_slave_ok):
                    new_mb_slave_fail = 1
                else: 
                    new_mb_slave_fail = 2
                
                await core.update_mb_slave_fail(new_mb_slave_fail)
                
                # Report
                if has_to_report:
                    core.status.mb_ts_report_time = ts_now
                    await core.modbus_report(li_responses)
            except Exception as ex:
                debug_msg = "MB core.report Exception {e}".format(e=str(ex))
                _logger.exc(ex, debug_msg)

    except Exception as ex:
        _logger.exc(ex,"do_read_mb error: {e}".format(e=str(ex)))



async def mb_request(serial_pdu):
    global _li_requests
    global _li_requests_lock
    async with _li_requests_lock:
        _li_requests.append(serial_pdu)

def stop():
    global _stop
    _stop = True

async def mb_task(core):
    global _stop
    
    if PINOUT.MB_ENABLED is False:
        return
    
    requests = []
    _status = core.status
    _params = _status.params
    try:
        requests = _params[K_MESSAGES][K_REQUESTS]
    except Exception as ex:
        debug_msg = "\nmb_task failed to get requests from params. Exception {e}. Params '{p}'\n".format(e=str(ex), p=str(_params))
        _logger.exc(ex, debug_msg)
        
    _logger.debug("Modbus TASK started. {n} requests defined".format(n=len(requests)))
    
    try:
        init_mb_task(core)    
    except Exception as ex:
        debug_msg = "\nmb_task failed init modbus. Exception {e}. Params '{p}'\n".format(e=str(ex), p=str(_params))
        _logger.exc(ex, debug_msg)
        return
        
    await asyncio.sleep_ms(PINOUT.MB_READ_PERIOD_MS)
    
    # GC control
    gc_idx = 0
    gc_nb_periods = max(10000/PINOUT.MB_READ_PERIOD_MS,1)
    
    while _stop is False:
        try:
            await do_read_mb(core)
            if PINOUT.WDT_ENABLED:
                core.wdt.feed()
            
            # Periodic GC
            gc_idx = gc_idx + 1 
            if gc_idx >= gc_nb_periods:
                gc.collect()
                gc_idx = 0
                
        except Exception as ex:
            _logger.exc(ex,"Failed to read modbus: {e}".format(e=ex))
            
        await asyncio.sleep_ms(PINOUT.MB_READ_PERIOD_MS)
    
        
    _logger.debug("MB TASK FINISHED")



