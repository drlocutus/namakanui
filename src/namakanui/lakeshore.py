'''
namakanui/lakeshore.py  RMB 20211210

Class to monitor temperature channels from a LakeShore 218 or 336.


Copyright (C) 2020 East Asian Observatory

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

from namakanui.ini import *
from namakanui import sim
import socket
import select
import time
import logging
import os

class Lakeshore(object):
    '''
    Class to monitor temperature channels from a LakeShore 218 or 336.
    '''
    def __init__(self, inifile, sleep, publish, simulate=0, level=logging.INFO):
        '''Arguments:
            inifile: Path to config file or IncludeParser instance.
            sleep(seconds): Function to sleep for given seconds, e.g. time.sleep, drama.wait.
            publish(name, dict): Function to output dict with given name, e.g. drama.set_param.
            simulate: Mask, bitwise ORed with config settings.
            level: Logging level, default INFO.
        '''
        self.config = inifile
        if not hasattr(inifile, 'items'):
            self.config = IncludeParser(inifile)
        myconfig = self.config['lakeshore']
        self.sleep = sleep
        self.publish = publish
        self.simulate = sim.str_to_bits(myconfig['simulate']) | simulate
        self.name = myconfig['name']
        self.log = logging.getLogger(self.name)
        self.state = {'number':0}
        
        self.ip = myconfig['ip']
        self.port = int(myconfig['port'])
        self.timeout = float(myconfig['timeout'])  # seconds
        
        self.gpib = False
        if 'gpib_addr' in myconfig:
            # using Prologix GPIB-LAN converter
            self.gpib = True
            self.gpib_addr = int(myconfig['gpib_addr'])
            self.gpib_tmo_ms = int(myconfig['gpib_tmo_ms'])
        
        self.log.debug('__init__ %s, sim=%d, %s:%d',
                       self.config.inifilename, self.simulate, self.ip, self.port)
        
        self.initialise()
        
        self.log.setLevel(level)  # set log level last to allow DEBUG output during creation
        # Lakeshore.__init__
    
    def __del__(self):
        self.log.debug('__del__')

    def initialise(self):
        '''Open the connections to the Lakeshore and get/publish state.'''
        self.log.debug('initialise')
        
        # fix simulate set
        self.simulate &= sim.SIM_LAKESHORE
        
        self.state['simulate'] = self.simulate
        self.state['sim_text'] = sim.bits_to_str(self.simulate)
        
        if not self.simulate & sim.SIM_LAKESHORE:    
            self.cmd('*CLS')
            idn = self.cmd('*IDN?')
            self.log.debug('Lakeshore IDN: %s', idn)
        
        self.update()
        # Lakeshore.initialise
    
    def update(self):
        '''Update and publish state.'''
        self.log.debug('update')
        
        if self.simulate:
            self.state['temp'] = [4.0, 4.0, 15.0, 90.0, 273.0]
        else:
            krdg = self.cmd('KRDG? 0')
            self.state['temp'] = [float(x.strip()) for x in krdg.split(',')]
        
        self.state['number'] += 1
        self.publish(self.name, self.state)
        # Lakeshore.update
    
    def cmd(self, c):
        '''Send cmd c. If "?" in c, the last reply will be repeated because of GPIB buffer.'''
        self.log.debug('cmd(%s)', c)

        c = c.strip()
        if hasattr(c, 'encode'):
            c = c.encode()  # convert to bytes

        # reconnect every time since Lakeshore disconnects us too quickly
        self.log.debug('connecting Lakeshore, %s:%d', self.ip, self.port)
        s = socket.socket()
        s.settimeout(self.timeout)
        s.connect((self.ip, self.port))
        if self.gpib:
            # Set mode as CONTROLLER
            s.sendall(b'++mode 1\n')
            # Set Lakeshore GPIB address
            s.sendall(b'++addr %d\n'%(self.gpib_addr))
            # Turn on read-after-write
            s.sendall(b'++auto 1\n')
            # Set read timeout in milliseconds (no need if ++auto 1)
            #s.sendall(b'++read_tmo_ms %d\n'%(self.gpib_tmo_ms))
            # Do not append CR or LF to GPIB data
            s.sendall(b'++eos 3\n')
            # Assert EOI with last byte to indicate end of data
            s.sendall(b'++eoi 1\n')

        s.sendall(c + b'\r\n')

        # always read reply since we set ++auto 1,
        # but if this cmd was not a query it will be junk
        r = b''
        while b'\r\n' not in r:
            r += s.recv(4096)

        self.log.debug('close')
        s.close()
        self.log.debug('cmd: %s; reply: %s', c, r)
        if b'?' in c:
            return r.strip().decode()  # convert to str
        # Lakeshore.cmd

