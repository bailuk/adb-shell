#!/usr/bin/env python3

'''
adb_shell: UI Frontend to ADB and android_fuse
See https://github.com/bailuk/android-fuse
and https://github.com/bailuk/adb-shell
'''

from pathlib import Path
import time
import subprocess
import os

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib


class Config():
    '''
    Global configuration for this Applications.
    Adjust configuration here.
    '''

    def __init__(self):
        self.config = {
            'title': 'ADB Shell',

            # mount point for fuse file system
            'mount_path': self.__expand('~/android-fuse'),

            # mount command (see https://github.com/bailuk/android-fuse)
            'mount_cmd': self.__expand('~/git/android-fuse/android-fuse.py'),

            # directory where adb is installed (will be added to path)
            'adb_path': self.__expand('~/Android/Sdk/platform-tools/'),

            # adb command
            'adb': 'adb',

            'terminal': 'xfce4-terminal'
        }

        self.__add_adb_to_path()

    def __add_adb_to_path(self):
        if os.path.exists(self.config['adb_path']):
            os.environ['PATH'] = os.environ['PATH'] + ":" + str(self.config['adb_path'])

    def __expand(self, path):
        return Path(os.path.expanduser(path))

    def get_string(self, key):
        '''return config attribute as string'''
        return str(self.get(key))

    def get(self, key):
        '''return config attribute'''
        return self.config[key]

CFG = Config()

class Process():
    '''representates a command execution '''

    def __init__(self, args):
        self.args = self.__cmd_list(args)

    def __cmd_list(self, args):
        if isinstance(args, str):
            return args.split(' ')
        return args

    def run_bg(self):
        '''Run process in background. Returns process handler'''
        return subprocess.Popen(self.args)


    def read(self):
        '''run process in foreground and return stdout as UTF-8 string'''
        try:
            with(subprocess.Popen(self.args, stdout=subprocess.PIPE)) as process:
                return process.stdout.read().decode('utf-8')

        except subprocess.CalledProcessError as error:
            print(f"ERROR: {error.cmd} returned exit code {error.returncode}.")
            return ''

    def read_lines(self):
        '''run process in foreground and return stdout as UTF-8 string list'''
        return self.read().splitlines()


    def run_fg(self):
        '''run process in foreground. Returns execution status as boolean'''
        try:
            subprocess.check_call(self.args)
            return True
        except subprocess.CalledProcessError:
            return False


class MountPoint():
    '''
    Mount point for a device that can be mounted an umounted
    '''

    def __init__(self, mpoint, device):
        self.mpoint = mpoint
        self.process_query = Process('mountpoint -q ' + mpoint)
        self.process_umount = Process('umount ' + mpoint)
        self.process_mount = Process([CFG.get_string('mount_cmd'), mpoint, '-s', device])


    def is_mounted(self):
        '''
        returns true if mpoint is a path and is mounted
        '''
        return os.path.exists(self.mpoint) and self.process_query.run_fg()

    def umount(self):
        '''
        unmounts mpoint
        '''
        if self.is_mounted():
            self.process_umount.run_fg()


    def mount_wait(self):
        '''
        Run fuse script to mount dev at mpoint and wait one second afterwards
        '''
        if not self.is_mounted():
            self.__cmd_fuse()
            time.sleep(1)


    def mount(self):
        '''
        Mount device at mpoint if not yet mounted
        '''
        if not self.is_mounted():
            self.__cmd_fuse()


    def __enshure_dir(self):
        if not os.path.exists(self.mpoint):
            os.makedirs(self.mpoint)
        return os.path.exists(self.mpoint)


    def __cmd_fuse(self):
        if self.__enshure_dir():
            self.process_mount.run_bg()


class Properties():
    '''
    Properties (information) about devices
    '''

    def __init__(self):
        self.props = {}


    def get(self, dev, prop):
        '''
        Reads property if not yet in cache
        and then stores property in cache
        '''

        try:
            return self.props[dev][prop]

        except KeyError:
            print(f"ERROR: getting property {prop} for device {dev}")
            self.add(dev, prop)
            return self.props[dev][prop]


    def add(self, dev, prop):
        '''add property'''
        args = CFG.get_string('adb') + ' -s ' + dev + ' shell getprop ' + prop
        value = Process(args).read().strip()
        if dev not in self.props:
            self.props[dev] = {}

        self.props[dev][prop] = value



class Devices():
    '''
    Android devices detected by adb
    '''

    def __init__(self):
        self.props = Properties()
        self.device_list = self.__read_list()


    def get(self):
        '''list of devices'''
        return self.device_list

    def get_mpoint(self, dev):
        '''generate mount point path suitable for specific device'''
        return (CFG.get('mount_path') / dev).absolute().as_posix()


    def __read_list(self):
        result = []

        for line in Process(CFG.get_string('adb') + ' devices').read_lines():
            cols = line.split('\t')
            if len(cols) == 2:
                dev_id, dev_type = cols
                mpoint = self.get_mpoint(dev_id)

                result.append({'id'     : dev_id,
                               'type'   : dev_type,
                               'name'   : self.props.get(dev_id, 'ro.product.name'),
                               'model'  : self.props.get(dev_id, 'ro.product.model'),
                               'mpoint' : mpoint,
                               'mounted': MountPoint(mpoint, dev_id).is_mounted()})
        return result


    def __cmp_entry(self, device_a, device_b):
        return device_a['id'] == device_b['id'] and device_a['mounted'] == device_b['mounted']

    def __cmp_list(self, devices_a, devices_b):
        if len(devices_a) != len(devices_b):
            return False

        for i, device_a in enumerate(devices_a):
            if not self.__cmp_entry(device_a, devices_b[i]):
                return False

        return True


    def update(self):
        '''
        update list from adb
        return true if updated or false if unchanged
        '''

        old_list = self.device_list[:]
        self.device_list = self.__read_list()

        return not self.__cmp_list(self.device_list, old_list)


    def find_mpoint(self, mpoint):
        '''
        Returns true if mount point is known and in list
        '''
        for device in self.device_list:
            if device['mpoint'] == mpoint:
                return True
        return False


class Action():
    '''
    Action that can be executed for specific device.
    Base class for all actions
    '''

    def __init__(self, controler, device):
        print(f"DEBUG: {device['mpoint']}")
        self.controler = controler
        self.device = device
        self.mount_point = MountPoint(device['mpoint'], device['id'])

    def get_name(self):
        '''action name'''
        return ''

    def call(self, caller):
        '''
        Execute action. This function is used as callback (GTK Signal).
        Therefore the second argument is needed.
        '''
        print(self.get_name())


class ActionShell(Action):
    '''
    Execute a shell on device
    '''

    def get_name(self):
        return 'ADB Shell'

    def call(self, caller):
        cmd = CFG.get('adb') + ' -s ' + self.device['id'] + ' shell'
        args = [CFG.get('terminal'), '-e', cmd]
        Process(args).run_bg()

class ActionLocalShell(Action):
    '''
    Open shell in mount point
    '''

    def get_name(self):
        return 'Shell'

    def call(self, caller):
        mpoint = self.device['mpoint']
        self.mount_point.mount_wait()
        Process([CFG.get('terminal'), '--working-directory=' + mpoint]).run_bg()


class ActionMount(Action):
    '''
    Mount device
    '''

    def get_name(self):
        return 'Mount'

    def call(self, caller):
        self.mount_point.mount()


class ActionUmount(Action):
    '''
    Unmount device
    '''

    def get_name(self):
        return 'Umount'

    def call(self, caller):
        self.mount_point.umount()


class ActionThunar(Action):
    '''
    Open Thunar file manager in mounted directory
    '''

    def get_name(self):
        return 'Thunar'

    def call(self, caller):
        mpoint = self.device['mpoint']
        self.mount_point.mount_wait()
        Process('thunar ' +  mpoint).run_fg()


class Controler():
    '''
    Controler for actions per device and ADB output
    '''

    def __init__(self, win):
        self.win = win
        self.devices = Devices()
        GLib.timeout_add_seconds(3, self.timeout)

    def timeout(self):
        '''
        Update on timeout
        This is a callback
        It returns true to receive more timeouts
        '''
        self.__update()
        return True

    def __update(self):
        if self.devices.update():
            self.win.update()

    def actions(self, device):
        '''
        Create actions for device and return them as list
        '''
        return [    ActionShell(self, device),
                    ActionMount(self, device),
                    ActionUmount(self, device),
                    ActionLocalShell(self, device),
                    ActionThunar(self, device)
                ]

    def adb_version(self):
        '''
        Get adb version and return it as string
        '''
        return Process(CFG.get('adb') + ' version').read().strip()


class UiDeviceEntry(Gtk.Box):
    '''
    UI Element that displays device info and action buttons
    '''

    def __init__(self, controler, device):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL, spacing = 5)

        self.device = device
        self.controler = controler

        self.add(Gtk.Separator(orientation = Gtk.Orientation.VERTICAL))
        self.add(Gtk.Label(label=self.__device_str()))
        self.add(self.__create_actions())


    def __create_actions(self):
        result = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL, spacing = 5)

        for action in self.controler.actions(self.device):
            button = Gtk.Button(label=action.get_name())
            button.connect('clicked', action.call)
            result.add(button)
        return result

    def __device_str(self):
        result = self.device['id'] + ' ' + self.device['model']
        if self.device['mounted']:
            result += ' is mounted'
        return result


class UiHeader(Gtk.Box):
    '''
    UI Element: A header that contains an icon and adb version
    '''

    def __init__(self, controler):
        Gtk.Box.__init__(self, spacing = 20)

        self.controler = controler

        self.label = Gtk.Label(label=controler.adb_version())
        self.add(self.label)

    def update(self):
        '''Update contents'''
        self.label.set_text(self.controler.adb_version())


class UiContent(Gtk.Box):
    '''
    UI Layout containing header and device list
    '''

    def __init__(self):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL, spacing = 20)

        self.controler = Controler(self)

        self.header = UiHeader(self.controler)
        self.add(self.header)

        self.entries = self.__create_entries()


    def __create_entries(self):
        result = []

        for device in self.controler.devices.get():
            result.append(UiDeviceEntry(self.controler, device))
            self.add(result[-1])

        return result


    def __remove_entries(self):
        for entry in self.entries:
            self.remove(entry)

        return []


    def update(self):
        ''' Update content of view '''

        self.header.update()
        self.entries = self.__remove_entries()
        self.entries = self.__create_entries()
        self.show_all()


class UiAppWindow(Gtk.ApplicationWindow):
    '''
    Main Window
    '''

    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_border_width(20)
        self.set_title(CFG.get('title'))

        self.add(UiContent())
        self.show_all()


UiAppWindow().connect("destroy", Gtk.main_quit)
Gtk.main()
