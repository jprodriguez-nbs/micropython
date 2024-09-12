import machine, os, gc
from .httpclient import HttpClient

import logging

import utime

import hwversion

WDT_ENABLED = hwversion.WDT_ENABLED
if WDT_ENABLED:
    import machine
    _wdt = machine.WDT(timeout=240000)


DOWNLOAD_FROZEN_LIB = False

_logger = logging.getLogger("OTAUpdater")

class OTAUpdater:
    """
    A class to update your MicroController with the latest version from a GitHub tagged release,
    optimized for low power usage.
    """

    def __init__(self, github_repo, github_src_dir='', module='', main_dir='main', new_version_dir='next', secrets_file=None, headers={}, extra_dirs=[]):
        self.headers = headers
        self.http_client = HttpClient(headers=headers)
        self.github_repo = github_repo.rstrip('/').replace('https://github.com/', '')
        self.github_src_dir = '' if len(github_src_dir) < 1 else github_src_dir.rstrip('/') + '/'
        self.module = module.rstrip('/')
        self.main_dir = main_dir
        self.extra_dirs = extra_dirs
        self.new_version_dir = new_version_dir
        self.secrets_file = secrets_file

    def __del__(self):
        self.http_client = None

    def check_for_update_to_install_during_next_reboot(self) -> bool:
        """Function which will check the GitHub repo if there is a newer version available.
        
        This method expects an active internet connection and will compare the current 
        version with the latest version available on GitHub.
        If a newer version is available, the file 'next/version.dat' will be created 
        and you need to call machine.reset(). A reset is needed as the installation process 
        takes up a lot of memory (mostly due to the http stack)

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        cv_parts = current_version.split(".")
        cv = cv_parts[0]*65535+cv_parts[1]*256+cv_parts[3]
        lv_parts = latest_version.split(".")
        lv = lv_parts[0]*65535+lv_parts[1]*256+lv_parts[3]
        if lv > cv:
            print('New version available, will download and install on next reboot')
            self._create_new_version_file(latest_version)
            return True

        return False

    def install_update_if_available_after_boot(self, ssid, password) -> bool:
        """This method will install the latest version if out-of-date after boot.
        
        This method, which should be called first thing after booting, will check if the 
        next/version.dat' file exists. 

        - If yes, it initializes the WIFI connection, downloads the latest version and installs it
        - If no, the WIFI connection is not initialized as no new known version is available
        """

        if self.new_version_dir in os.listdir(self.module):
            if 'version.dat' in os.listdir(self.modulepath(self.new_version_dir)):
                latest_version = self.get_version(self.modulepath(self.new_version_dir), 'version.dat')
                print('New update found: ', latest_version)
                OTAUpdater._using_network(ssid, password)
                self.install_update_if_available()
                return True
            
        print('No new updates found...')
        return False

    def install_update_if_available(self) -> bool:
        """This method will immediately install the latest version if out-of-date.
        
        This method expects an active internet connection and allows you to decide yourself
        if you want to install the latest version. It is necessary to run it directly after boot 
        (for memory reasons) and you need to restart the microcontroller if a new version is found.

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        if latest_version > current_version:
            print('Updating to version {}...'.format(latest_version))
            self._create_new_version_file(latest_version)
            self._download_new_version(latest_version, origin_dir=self.main_dir, target_dir=self.new_version_dir)
            for ed in self.extra_dirs:
                new_version_extra_dir = "{b}.{ed}".format(b=self.new_version_dir, ed=ed)
                self.mkdir(self.modulepath(new_version_extra_dir))
                self._download_new_version(latest_version, origin_dir=ed, target_dir=new_version_extra_dir)
            self._copy_secrets_file()
            self._delete_old_version(dirname=self.main_dir)
            for ed in self.extra_dirs:
                self._delete_old_version(dirname=ed)
            self._install_new_version(nvd=self.new_version_dir, target=self.main_dir)
            for ed in self.extra_dirs:
                new_version_extra_dir = "{b}.{ed}".format(b=self.new_version_dir, ed=ed)
                self._install_new_version(nvd=new_version_extra_dir, target=ed)
            return True
        
        return False


    @staticmethod
    def _using_network(ssid, password):
        import network
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print('connecting to network...')
            sta_if.active(True)
            sta_if.connect(ssid, password)
            while not sta_if.isconnected():
                pass
        print('network config:', sta_if.ifconfig())

    def _check_for_new_version(self):
        current_version = self.get_version(self.modulepath(self.main_dir))
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        return (current_version, latest_version)

    def get_current_version(self):
        current_version = self.get_version(self.modulepath(self.main_dir))
        return current_version

    def _create_new_version_file(self, latest_version):
        self.mkdir(self.modulepath(self.new_version_dir))
        with open(self.modulepath(self.new_version_dir + '/version.dat'), 'w') as versionfile:
            versionfile.write(latest_version)
            versionfile.close()

    def update_current_version_file(self, current_version):
        self.mkdir(self.modulepath(self.main_dir))
        with open(self.modulepath(self.main_dir + '/version.dat'), 'w') as versionfile:
            versionfile.write(current_version)
            versionfile.close()

    def get_version(self, directory, version_file_name='version.dat'):
        if version_file_name in os.listdir(directory):
            with open(directory + '/' + version_file_name) as f:
                version = f.read()
                return version
        return '0.0.0'

    def get_latest_version(self):
        query_url = 'https://api.github.com/repos/{}/releases/latest'.format(self.github_repo)
        latest_release = self.http_client.get(query_url)
        version = None
        try:
            obj = latest_release.json()
            if 'tag_name' in obj:
                version = latest_release.json()['tag_name']
            else:
                msg = "get_latest_version(url={u}, headers={h}) Error: tag_name does not exist in {o}".format(u=query_url, h=self.headers, o = str(obj))
                _logger.error(msg)
        except Exception as ex:
            msg = "get_latest_version(url={u}, headers={h}) Exception {e}".format(u=query_url, h=self.headers, e = str(ex))
            _logger.exc(ex, msg)
        latest_release.close()
        return version

    def _download_new_version(self, version, origin_dir=None, target_dir=None):
        if origin_dir is None:
            origin_dir = self.main_dir
        if target_dir is None:
            target_dir = self.new_version_dir
        print('Downloading version {v} {o} to {t}'.format(v=version, o=origin_dir, t=target_dir))
        self._download_all_files(version, origin_dir=origin_dir, target_dir=target_dir)
        print('Version {} downloaded to {}'.format(version, self.modulepath(self.new_version_dir)))

    def _download_all_files(self, version, origin_dir=None, target_dir=None, sub_dir=''):
        if origin_dir is None:
            origin_dir = self.main_dir
        if target_dir is None:
            target_dir = self.new_version_dir
        url = 'https://api.github.com/repos/{}/contents{}{}{}?ref=refs/tags/{}'.format(self.github_repo, self.github_src_dir, origin_dir, sub_dir, version)
        gc.collect() 
        file_list = self.http_client.get(url)
        for file in file_list.json():
            isFrozen = '/app/frozen/' in file['path']
            if not isFrozen or DOWNLOAD_FROZEN_LIB:
                path = self.modulepath(target_dir + '/' + file['path'].replace(origin_dir + '/', '').replace(self.github_src_dir, ''))
                if file['type'] == 'file':
                    gitPath = file['path']
                    print('\tDownloading: ', gitPath, 'to', path)
                    self._download_file(version, gitPath, path)
                elif file['type'] == 'dir':
                    print('Creating dir', path)
                    self.mkdir(path)
                    self._download_all_files(version, origin_dir, target_dir, sub_dir + '/' + file['name'])
                utime.sleep_ms(100)
                gc.collect()

        file_list.close()

    def _download_file(self, version, gitPath, path):
        trial_count = 0
        downloaded = False
        while (downloaded is False) and (trial_count < 5):
            try:
                self.http_client.get('https://raw.githubusercontent.com/{}/{}/{}'.format(self.github_repo, version, gitPath), saveToFile=path)
                downloaded = True
                if WDT_ENABLED:
                    _wdt.feed()
                utime.sleep_ms(100)
            except Exception as ex:
                trial_count = trial_count + 1
                if trial_count >=5:
                    raise ex

    def _copy_secrets_file(self):
        if self.secrets_file:
            fromPath = self.modulepath(self.main_dir + '/' + self.secrets_file)
            toPath = self.modulepath(self.new_version_dir + '/' + self.secrets_file)
            print('Copying secrets file from {} to {}'.format(fromPath, toPath))
            self._copy_file(fromPath, toPath)
            print('Copied secrets file from {} to {}'.format(fromPath, toPath))

    def _delete_old_version(self, dirname=None):
        if dirname is None:
            dirname = self.main_dir
        try:
            print('Deleting old version at {} ...'.format(self.modulepath(dirname)))
            self._rmtree(self.modulepath(dirname))
            print('Deleted old version at {} ...'.format(self.modulepath(dirname)))
        except Exception as ex:
            _logger.exc(ex, "Failed to delete old version at {} ...".format(self.modulepath(dirname)))

    def _install_new_version(self, nvd=None, target=None):
        if nvd is None:
            nvd = self.new_version_dir
        if target is None:
            target = self.main_dir
        print('Installing new version at {} ...'.format(self.modulepath(target)))
        if self._os_supports_rename():
            os.rename(self.modulepath(nvd), self.modulepath(target))
        else:
            self._copy_directory(self.modulepath(nvd), self.modulepath(target))
            self._rmtree(self.modulepath(nvd))
        print('Update installed, please reboot now')

    def _rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._rmtree(directory + '/' + entry[0])
            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def _os_supports_rename(self) -> bool:
        self._mk_dirs('otaUpdater/osRenameTest')
        os.rename('otaUpdater', 'otaUpdated')
        result = len(os.listdir('otaUpdated')) > 0
        self._rmtree('otaUpdated')
        return result

    def _copy_directory(self, fromPath, toPath):
        if not self._exists_dir(toPath):
            self._mk_dirs(toPath)

        for entry in os.ilistdir(fromPath):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._copy_directory(fromPath + '/' + entry[0], toPath + '/' + entry[0])
            else:
                self._copy_file(fromPath + '/' + entry[0], toPath + '/' + entry[0])

    def _copy_file(self, fromPath, toPath):
        with open(fromPath) as fromFile:
            with open(toPath, 'w') as toFile:
                CHUNK_SIZE = 512 # bytes
                data = fromFile.read(CHUNK_SIZE)
                while data:
                    toFile.write(data)
                    data = fromFile.read(CHUNK_SIZE)
            toFile.close()
        fromFile.close()

    def _exists_dir(self, path) -> bool:
        try:
            os.listdir(path)
            return True
        except:
            return False

    def _mk_dirs(self, path:str):
        paths = path.split('/')

        pathToCreate = ''
        for x in paths:
            self.mkdir(pathToCreate + x)
            pathToCreate = pathToCreate + x + '/'

    # different micropython versions act differently when directory already exists
    def mkdir(self, path:str):
        try:
            os.mkdir(path)
        except OSError as exc:
            if exc.args[0] == 17: 
                pass


    def modulepath(self, path):
        return self.module + '/' + path if self.module else path

    
