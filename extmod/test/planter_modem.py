import json

import utime
import colors
import arequests

import  asyncio

print("Import umdc pinout")
import umdc_pinout as PINOUT
print("Import umdc config")
import umdc_config as CFG

print ("Import logging")
import logging as logging

print("Create logger")
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


GET_HEADERS = {"Connection": "close"}
POST_HEADERS = {
    'content-type': 'application/json',
    "Connection": "close"
    }

a = "35.157.78.86:8080"
j = "J0002"
_config_url = "http://{agent}/config/{id}".format(agent=a, id=j)

print("Classes")

class PlanterModem(object):

    def __init__(self):

        print("Import SIM800L")
        from SIM800L import Modem

        print('Create Modem object...')

        # Create new modem object on the right Pins
        self._modem = Modem(modem_pwkey_pin    = PINOUT.MODEM_PWKEY_PIN,
                    modem_rst_pin      = PINOUT.MODEM_RST_PIN,
                    modem_power_on_pin = PINOUT.MODEM_POWER_ON_PIN,
                    modem_tx_pin       = PINOUT.MODEM_TX_PIN,
                    modem_rx_pin       = PINOUT.MODEM_RX_PIN)

    def start(self):
        # Initialize the modem
        print('Modem initialize ...')
        self._modem.initialize()

        # Run some optional diagnostics
        #print('Modem info: "{}"'.format(modem.get_info()))
        #print('Network scan: "{}"'.format(modem.scan_networks()))
        #print('Current network: "{}"'.format(modem.get_current_network()))
        #print('Signal strength: "{}%"'.format(modem.get_signal_strength()*100))

        
        print('Sleep 500ms...')
        utime.sleep_ms(500)

        modem_info = self._modem.get_info()
        print("Modem info: {modem_info}".format(modem_info=modem_info))
        print('Sleep 500ms...')
        utime.sleep_ms(500)

        print('POWER IS STABLE UP TO NOW ...')

        # Connect the modem
        print('Modem connect ...')
        self._modem.connect(apn=PINOUT.APN)
        print('\nModem IP address: "{}"'.format(self._modem.get_ip_addr()))


        # Example GET
        print('\nNow running demo http GET...')
        url = 'http://checkip.dyn.com/'
        response = self._modem.http_request(url, 'GET')
        print('Response status code:', response.status_code)
        print('Response content:', response.content)

        # Example POST
        print('Now running demo https POST...')
        url  = 'https://postman-echo.com/post'
        data = json.dumps({'myparameter': 42})
        response = self._modem.http_request(url, 'POST', data, 'application/json')
        print('Response status code:', response.status_code)
        print('Response content:', response.content)

        # Disconnect Modem
        self._modem.disconnect()




class PlanterModemAsync(object):

    def __init__(self):
        print("Import async_SIM800L")
        from async_SIM800L import AsyncModem
        
        #print("Import async_SIM7070G")
        #from async_SIM7070G import AsyncModem

        print('Create AsyncModem object...')

        # Create new modem object on the right Pins
        self._modem = AsyncModem(uart_port = PINOUT.MODEM_UART_PORT,
                                modem_pwkey_pin    = PINOUT.MODEM_PWKEY_PIN,
                                modem_rst_pin      = PINOUT.MODEM_RST_PIN,
                                modem_power_on_pin = PINOUT.MODEM_POWER_ON_PIN,
                                modem_tx_pin       = PINOUT.MODEM_TX_PIN,
                                modem_rx_pin       = PINOUT.MODEM_RX_PIN,
                                pwrkey_inverted = PINOUT.PWKEY_INVERTED,
                                baudrate = PINOUT.MODEM_BAUDRATE)

        print('Modem created')

    async def start(self):

        print('AsyncModem initialize ...')
        # Initialize the modem
        await self._modem.initialize()

        # Run some optional diagnostics
        #print('Modem info: "{}"'.format(modem.get_info()))
        #print('Network scan: "{}"'.format(modem.scan_networks()))
        #print('Current network: "{}"'.format(modem.get_current_network()))
        #print('Signal strength: "{}%"'.format(modem.get_signal_strength()*100))

        if False:
            # Connect the modem
            print('\n{c}AsyncModem connect ...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))

            _apn = CFG.config()[CFG.K_GPRS][CFG.K_APN]
            _ppp_user = CFG.config()[CFG.K_GPRS][CFG.K_USER]
            _ppp_password = CFG.config()[CFG.K_GPRS][CFG.K_PSW]

            await self._modem.connect(apn=_apn, user=_ppp_user, pwd=_ppp_password)
            a = await self._modem.get_ip_addr()
            print('\n{c}Modem IP address:{n} "{a}"'.format(a=str(a),c=colors.BOLD_GREEN,n=colors.NORMAL))


            v = await self._modem.get_fwversion()
            print('\n{c}FW Version:{n} "{v}"'.format(v=str(v),c=colors.BOLD_GREEN,n=colors.NORMAL))

        if False:
            # Example GET
            try:
                print('\n{c}Now running demo http GET...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
                url = 'http://checkip.dyn.com/'
                response = await self._modem.http_request(url, 'GET')
                print('Response status code:', response.status_code)
                print('Response content:', response.content)
            except Exception as ex:
                _logger.exc(ex,"http GET: {e}".format(e=str(ex)))


            # Example POST
            try:
                print('\n{c}Now running demo https POST...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
                url  = 'https://postman-echo.com/post'
                data = json.dumps({'myparameter': 42})
                response = await self._modem.http_request(url, 'POST', data, 'application/json')
                print('Response status code:', response.status_code)
                print('Response content:', response.content)
            except Exception as ex:
                _logger.exc(ex,"https POST: {e}".format(e=str(ex)))




        try:
            # PPP communication

            _apn = None
            _ppp_user = None
            _ppp_password = None
            try:
                _apn = CFG.config()[CFG.K_GPRS][CFG.K_APN]
                _ppp_user = CFG.config()[CFG.K_GPRS][CFG.K_USER]
                _ppp_password = CFG.config()[CFG.K_GPRS][CFG.K_PSW]
            except Exception as ex:
                _logger.exc(ex, "Failed to get PPP configuration")

            print('\n{c}Connect PPP ({apn}, {u}, {p}) ...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL,apn=_apn, u=_ppp_user, p=_ppp_password))

            (iccid, rssi, ppp) = await self._modem.ppp_connect(apn=_apn, user=_ppp_user, pwd=_ppp_password)
            print ("SIM ICCID = {iccid}".format(iccid=iccid))

            try:
                # Execute request
                url = 'http://checkip.dyn.com/'
                print("{c}Get - URL:{n} {url}".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
                response = await arequests.get(url, headers=GET_HEADERS)
                print("{c}Response{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            except Exception as ex:
                _logger.exc(ex,"PPP: {e}".format(e=str(ex)))

            try:
                # Execute request
                url = 'http://www.google.es/'
                print("{c}Get - URL:{n} {url}".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
                response = await arequests.get(url, headers=GET_HEADERS)
                print("{c}Response{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            except Exception as ex:
                _logger.exc(ex,"PPP: {e}".format(e=str(ex)))

            try:
                # Execute request
                url = 'https://campus.uoc.edu/'
                print("{c}Get - URL:{n} {url}".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
                response = await arequests.get(url, headers=GET_HEADERS)
                print("{c}Response{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            except Exception as ex:
                _logger.exc(ex,"PPP: {e}".format(e=str(ex)))

            if False:
                # Disconnect PPP
                print('\n{c}nDisconnect PPP...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
                await self._modem.ppp_disconnect()
        except Exception as ex:
            _logger.exc(ex,"PPP: {e}".format(e=str(ex)))


        if False:
            # Disconnect Modem
            print('\nDisconnect Modem...')
            await self._modem.disconnect()


def test_async():
    import  asyncio
    loop = asyncio.get_event_loop()

    m = PlanterModemAsync()
    loop.create_task(m.start())
    loop.run_forever()


