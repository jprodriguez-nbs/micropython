import logging as ulogging
import io
import sys
import gc
from networkmgr import NetworkMgr
import uasyncio as asyncio



_logger = ulogging.getLogger("UpdateUtils")

class UpdateUtils:

    @staticmethod
    async def updateIfNecessary():
        # Limit the update to 600s
        await asyncio.wait_for_ms(UpdateUtils.doUpdateIfNecessary(), 600000)

    @staticmethod
    async def doUpdateIfNecessary():
        import machine, os
        try:
            #with open('.updateRequested', "r") as updateRequested:
            #    pass

            updated = False
            try:
                try:
                    os.remove('.updateRequested')
                except:
                    pass
                _logger.info('Update requested...')
                await UpdateUtils._connectToWifi()
                await UpdateUtils._updateTimeUsingNTP()
                updated = UpdateUtils._otaUpdate()
                UpdateUtils._sendLogsToGithubGist()
                if updated:
                    _logger.info('Updates finished, will reboot')
                else:
                    _logger.info('No need to update')
            except BaseException as error:
                s = io.StringIO()
                sys.print_exception(error, s)
                full_explanation = "Error updating: {e} - {t}".format(e=str(error), t=s.getvalue())
                print(full_explanation)
                _logger.error(full_explanation)
            
            if updated:
                machine.reset()
            else:
                gc.collect()

        except BaseException as error:
            s = io.StringIO()
            sys.print_exception(error, s)
            full_explanation = "updateIfNecessary failed {e} - {t}".format(e=str(error), t=s.getvalue())
            print(full_explanation)
            ulogging.info('No update needed')
            pass

    @staticmethod
    async def _connectToWifi():
        only_wifi = False
        if only_wifi:
            import wifimgr as wifimgr
            sta_if = await wifimgr.get_connection()
            if sta_if is not None and sta_if.isconnected():
                ulogging.info('Connected to WIFI')
            else:
                ulogging.error('Failed to connect to WIFI')
        else:
            # Use NetworkMgr to connect either to WiFi or GPRS
            try:
                connection_event = NetworkMgr.connection_event()
                asyncio.create_task(NetworkMgr.nmtask()) 
                await asyncio.wait_for_ms(connection_event.wait(), 120000)
            except Exception as ex:
                print(str(ex))
                pass
            if NetworkMgr.isconnected():
                ulogging.info('Connected to Internet')
            else:
                ulogging.error('Failed to connect to Internet')
            


    async def _updateTimeUsingNTPTime():
        await NetworkMgr.setup_time()


    @staticmethod
    async def _updateTimeUsingNTP():
        ulogging.info('Updating time...')
        await UpdateUtils._updateTimeUsingNTPTime()


    @staticmethod
    def _otaUpdate():
        import secrets as secrets
        ulogging.info('Checking for Updates...')
        from .ota_updater import OTAUpdater
        #otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', secrets_file="secrets.py", extra_dirs=["www"])
        headers = {
            "Authorization": "token {t}".format(t=secrets.TOKEN)
            }
        otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', headers=headers, extra_dirs=["www"])
        updated = otaUpdater.install_update_if_available()
        del(otaUpdater)
        return updated
    
    @staticmethod
    def _sendLogsToGithubGist():
        import os
        if not 'logs.log' in os.listdir():
            return

        ulogging.info('Sending logs to GitHub Gist...')
        import secrets as secrets
        from .ota_logger import OTALogger
        o = OTALogger(secrets.GIST_ID, secrets.GIST_ACCESS_TOKEN)
        succeeded = o.log_to_gist('logs.log')
        if succeeded:
            ulogging.info('Sending logs to GitHub Gist succeeded...') 
            os.remove('logs.log')
        else:
            ulogging.warn('Sending logs to GitHub Gist failed...') 


    @staticmethod
    def set_version_manually(v):
        import secrets as secrets
        ulogging.info('Manually set version ...')
        from .ota_updater import OTAUpdater
        #otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', secrets_file="secrets.py", extra_dirs=["www"])
        headers = {
            "Authorization": "token {t}".format(t=secrets.TOKEN)
            }
        otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', headers=headers, extra_dirs=["www"])
        otaUpdater.update_current_version_file(v)
        new_v = otaUpdater.get_current_version()
        print ("Version changed to {new_v}".format(new_v=new_v))
        del(otaUpdater)

    @staticmethod
    def get_current_version():
        import secrets as secrets
        from .ota_updater import OTAUpdater
        #otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', secrets_file="secrets.py", extra_dirs=["www"])
        headers = {
            "Authorization": "token {t}".format(t=secrets.TOKEN)
            }
        otaUpdater = OTAUpdater('https://github.com/NearbySensors/ud-pyplanter', github_src_dir='src', main_dir='app', headers=headers, extra_dirs=["www"])
        new_v = otaUpdater.get_current_version()
        # print ("Current version is {new_v}".format(new_v=new_v))
        del(otaUpdater)
        return new_v


# UpdateUtils.updateIfNecessary()