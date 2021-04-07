#!/usr/bin/env python3

import time
import subprocess
import os
import sys
import re
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from pathlib import Path


class Config():
    def __init__(self):
        '''
        configure script here:
        '''
        self.config = dict()


        ######### BEGIN CONFIG ###############################################


        # title and icon
        self.config['title'] = 'ADB Shell'
        self.config['icon'] = ''
                
        # mount point for fuse file system
        self.config['mount_path'] = '~/android-fuse'

        # mount command (see https://github.com/bailuk/android-fuse)
        self.config['mount_cmd'] = '~/git/android-fuse/android-fuse.py'
        
        # directory where adb is installed (will be added to path)
        self.config['adb_path'] = '~/Android/Sdk/platform-tools/'
        
        # adb command
        self.config['adb'] = 'adb'

        ######### END CONFIG #################################################



        
        self.fixPath('mount_cmd')        
        self.fixPath('mount_path')
        self.fixPath('adb_path')

        if os.path.exists(self.config['adb_path']):
            os.environ['PATH'] = os.environ['PATH'] + ":" + str(self.config['adb_path'])

        self.config['mount_cmd'] = str(self.get('mount_cmd'))        
       
         
       
    def fixPath(self, key):
        self.config[key] = Path(os.path.expanduser(self.config[key]))
        
    

    def get(self, key):
        try:
            return self.config[key]
    
        except:
            return '';

            
            


def cmd_list(args):
    if type(args) is str: args = args.split(' ')
    return args


def cmd_bg(args):
    return subprocess.Popen(cmd_list(args))


def cmd_read(args):
    try:
        p = subprocess.Popen(cmd_list(args), stdout=subprocess.PIPE)
        return p.stdout.read().decode('utf-8')
    except:
        return ''
     

def cmd_lines(args):
    return cmd_read(args).splitlines()



def cmd_fg(args):
    try:
        subprocess.check_call(cmd_list(args))
        return True
    except:
        return False





def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        
    return os.path.exists(path)


def is_mounted(mpoint):
    return os.path.exists(mpoint) and cmd_fg('mountpoint -q ' + mpoint)

        

def umount(mpoint):
    if is_mounted(mpoint):
        cmd_fg('umount ' + mpoint)


def cmd_fuse(mpoint, dev):
    if ensure_dir(mpoint):
        cmd_bg(CFG.get('mount_cmd') + ' ' + mpoint + ' -s ' + dev)
       

def mount_wait(mpoint, dev):
    if not is_mounted(mpoint):
        cmd_fuse(mpoint, dev)
        time.sleep(1)



def mount(mpoint, dev):
    if not is_mounted(mpoint):
        cmd_fuse(mpoint, dev)

  

CFG = Config()

class Properties():
    def __init__(self):
        self.props = dict()
        
        
    def get(self, dev, prop):
        try:
            return self.props[dev][prop]
    
        except:
            self.add(dev, prop)
            return self.props[dev][prop]
            
        
    def add(self, dev, prop):
        print(prop)
        p = cmd_read(str(CFG.get('adb')) + ' -s ' + dev + ' shell getprop ' + prop).strip()
        if dev not in self.props:
            self.props[dev] = dict()
            
        self.props[dev][prop] = p
        


class Devices():

    def __init__(self):
        self.props = Properties()
        self.device_list = self.read_list()


    def get(self):
        return self.device_list

    def get_mpoint(self, dev):
        return (CFG.get('mount_path') / dev).absolute().as_posix()


    def read_list(self):
        result = list()

        for line in cmd_lines(str(CFG.get('adb')) + ' devices'):
            t = line.split('\t')
            if len(t) == 2:
                dev_id, dev_type = t
                mpoint = self.get_mpoint(dev_id)

                result.append({'id'     : dev_id,
                               'type'   : dev_type,
                               'name'   : self.props.get(dev_id, 'ro.product.name'),
                               'model'  : self.props.get(dev_id, 'ro.product.model'),                               
                               'mpoint' : mpoint,
                               'mounted': is_mounted(mpoint)})
        return result


    def cmp_entry(a, b):
        return a['id'] == b['id'] and a['mounted'] == b['mounted']

    def cmp_list(a, b):
        if len(a) != len(b): return False

        for i in range(len(a)):
            if not Devices.cmp_entry(a[i], b[i]):
                return False

        return True

    

    def update(self):
        old = self.device_list[:]
        self.device_list = self.read_list()

        return not Devices.cmp_list(self.device_list, old)


    def find_mpoint(self, mpoint):
        for device in device_list:
            if device['mpoint'] == mpoint:
                return True
        return False


    def umount_disconnected(self):
        for mpoint in os.listdir(mpoint_base):
            mpoint = os.path.abspath(mpoint)
            if not os.path.isfile(mpoint):
                if not self.find_mpoint(mpoint):
                    umount(mpoint)





class Action():
    def __init__(self, controler, device):
        self.controler = controler
        self.device = device

    def get_name(self):
        return 'Undefinied'

    def call(self, caller):
        print(self.get_name())


class ActionShell(Action):
    def get_name(self):
        return 'ADB Shell'

    def call(self, caller):
        cmd_bg([ 'xfce4-terminal', '-e', CFG.get('adb') + ' -s ' + self.device['id'] + ' shell'])


class ActionLocalShell(Action):
    def get_name(self):
        return 'Shell'

    def call(self, caller):
        mpoint = self.device['mpoint']
        dev = self.device['id']
        mount_wait(mpoint, dev)
        cmd_bg('xfce4-terminal --working-directory=' + mpoint)


class ActionMount(Action):
    def get_name(self):
        return 'Mount'

    def call(self, caller):
        dev = self.device['id']
        mpoint = self.device['mpoint']
        mount(mpoint, dev)


class ActionUmount(Action):
    def get_name(self):
        return 'Umount'

    def call(self, caller):
        mpoint = self.device['mpoint']
        umount(mpoint)


class ActionThunar(Action):
    def get_name(self):
        return 'Thunar'

    def call(self, caller):
        mpoint = self.device['mpoint']
        dev = self.device['id']
        mount_wait(mpoint, dev)
        cmd_fg('thunar ' +  mpoint)
            


class Controler():

    def __init__(self, win):
        self.win = win
        self.devices = Devices()
        GLib.timeout_add_seconds(3, self.timeout)

    def timeout(self):
        self.update()
        return True

    def update(self, caller=None):
        if self.devices.update():
            self.win.update()

    def actions(self, device):
        return [    ActionShell(self, device),
                    ActionMount(self, device),
                    ActionUmount(self, device),
                    ActionLocalShell(self, device),
                    ActionThunar(self, device)
                ]

    def adb_version(self):
        print(CFG.get('adb') + ' version')
        return cmd_read(CFG.get('adb') + ' version').strip()


class UiDeviceEntry(Gtk.Box):

    def __init__(self, controler, device):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL, spacing = 5)

        self.device = device
        self.controler = controler

        self.add(Gtk.Separator(orientation = Gtk.Orientation.VERTICAL))
        self.add(Gtk.Label(label=self.device_str()))
        self.add(self.create_actions())


    def create_actions(self):
        result = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL, spacing = 5)

        for action in self.controler.actions(self.device):
            button = Gtk.Button(label=action.get_name())
            button.connect('clicked', action.call)
            result.add(button)
        return result

    def device_str(self):
        result = self.device['id'] + ' ' + self.device['model']
        if (self.device['mounted']):
            result += ' is mounted'
        return result




class UiHeader(Gtk.Box):

    def __init__(self, controler):
        Gtk.Box.__init__(self, spacing = 20)

        self.controler = controler

        icon = Gtk.Image.new_from_file (CFG.get('icon'))
        self.add(icon)
        
        self.label = Gtk.Label(label=controler.adb_version())
        self.add(self.label)


    def update(self):
        self.label.set_text(self.controler.adb_version())


class UiContent(Gtk.Box):

    def __init__(self):
        Gtk.Box.__init__(self, orientation = Gtk.Orientation.VERTICAL, spacing = 20)

        self.controler = Controler(self)

        self.header = UiHeader(self.controler)
        self.add(self.header)

        self.create_entries()


    def create_entries(self):
        self.entries = list()

        for device in self.controler.devices.get():
            self.entries.append(UiDeviceEntry(self.controler, device))
            self.add(self.entries[-1])


    def remove_entries(self):
        for e in self.entries:
            self.remove(e)

        self.entries = list()


    def update(self):
        self.header.update()
        self.remove_entries()
        self.create_entries()
        self.show_all()


class UiAppWindow(Gtk.ApplicationWindow):


    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_border_width(20)
        self.set_title(CFG.get('title'))
        
        if os.access(CFG.get('icon'), os.R_OK):
            self.set_icon_from_file(CFG.get('icon'))
            
        self.add(UiContent())
        self.show_all()



win = UiAppWindow()
win.connect("destroy", Gtk.main_quit)
Gtk.main()


