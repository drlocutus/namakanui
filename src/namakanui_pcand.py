#!/usr/bin/env python3
'''
namakanui_pcand.py   RMB 20220125

A daemon to communicate with the PEAK PCAN-Ethernet Gateway DR.

The PCAN module is designed primarily to talk to other PCAN modules,
and as such it uses separate, preconfigured can2lan and lan2can routes.
You can't just connect a socket and get simple bidirectional communication.

If you want to talk to the CANbus with multiple simultaneous processes,
you'd normally need to configure a separate pair of routes for each one.
Instead, we configure a single pair of routes that only talk to this process,
and everybody else talks to us with bidirectional sockets.

This daemon is designed to exit immediately on any communication error,
so it should be configured to automatically restart, for instance
by running it as a systemd service.



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

import argparse, logging, select, selectors, socket, sys, time, types
import namakanui.util

namakanui.util.setup_logging()
log = logging.getLogger('pcand')

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description=namakanui.util.get_description(__doc__)
    )
parser.add_argument('-v', '--verbose', action='store_true', help='enable debug logging output')
args = parser.parse_args()

if args.verbose:
    logging.root.setLevel(logging.DEBUG)
    logging.root.handlers[0].setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    log.setLevel(logging.DEBUG)

cfg = namakanui.util.get_config('femc.ini')['femc']
pcan_type = cfg['pcan_type'].lower()  # tcp or udp
lan2can_ip = cfg['lan2can_ip']  # PCAN IP
lan2can_port = int(cfg['lan2can_port'])
can2lan_port = int(cfg['can2lan_port'])  # on localhost
pcand_port = int(cfg['pcand_port'])

# connect to PCAN
if pcan_type == 'tcp':
    log.debug('creating tcp lan2can socket')
    lan2can = socket.socket()
else:
    log.debug('creating udp lan2can socket')
    lan2can = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
lan2can.settimeout(1)
log.debug('lan2can.connect((%s, %d))', lan2can_ip, lan2can_port)
lan2can.connect((lan2can_ip, lan2can_port))

# bind a known port so PCAN can connect to us;
# set SO_REUSEADDR so pcand can restart even if old socket stuck in TIME_WAIT
if pcan_type == 'tcp':
    log.debug('listening for can2lan on tcp port %d', can2lan_port)
    can2lan_listener = socket.socket()
    can2lan_listener.settimeout(5)
    can2lan_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    can2lan_listener.bind(('0.0.0.0', can2lan_port))
    can2lan_listener.listen()
    can2lan, _addr = can2lan_listener.accept()      # blocks until PCAN connects
    can2lan.settimeout(1)
    can2lan_listener.shutdown(socket.SHUT_RDWR)
    can2lan_listener.close()        # because only one connection from PCAN?
else:
    log.debug('binding can2lan on udp port %d', can2lan_port)
    can2lan = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    can2lan.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    can2lan.settimeout(1)
    can2lan.bind(('0.0.0.0', can2lan_port))
    

# create server listening socket on pcand_port;
# set SO_REUSEADDR so pcand can restart even if old socket stuck in TIME_WAIT
log.debug('listening for clients on tcp port %d', pcand_port)
listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(('0.0.0.0', pcand_port))
listener.listen()

def messenger(msg):
    '''send msg to lan2can and get response from can2lan'''
    # clear out any leftover junk in the sockets -- might not be necessary
    r = select.select([lan2can, can2lan], [], [], 0.0)[0]
    while r:
        for ri in r:    ri.recv(64) 
        r = select.select([lan2can, can2lan], [], [], 0.0)[0]

    #_w = select.select([], [lan2can], [], 1.0)[1]   # timeout = 1.0
    # Probably not necessary; rely on socket's timeout instead
    lan2can.sendall(msg)
    log.debug('sent to lan2can: %s', msg.hex())

    #_r = select.select([can2lan], [], [], 1.0)[0]   # timeout = 1.0
    packet = can2lan.recv(36)
    log.debug('can2lan recv:    %s', packet.hex())
    if not packet:
        log.error('lost PCAN connection')
        raise Exception('lost PCAN connection')
    else:
        return packet

def relay():
    '''relay communications between client programs and the PCAN'''
    sel = selectors.DefaultSelector()
    sel.register(listener, selectors.EVENT_READ, data=None)

    def accept_wrapper(sock):
        conn, addr = sock.accept()  # Should be ready to read
        log.debug(f"{time.strftime('%X')} @RELAY - accepted from {addr}")
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
        events = selectors.EVENT_READ
        sel.register(conn, events, data=data)
    
    def service_connection(key, mask):
        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
            try:
                to_femc = sock.recv(36)
                log.debug('recv %d bytes:   %s from client %s', len(to_femc), 
                    to_femc.hex(), sock.getpeername())
            except:
                to_femc = b''
                log.exception('recv exception for client %s', sock.getpeername())
            if len(to_femc) < 36:  # bad/lost/closed connection
                log.debug('dropping client %s', sock.getpeername())
                sel.unregister(sock)
                sock.close()
            else:
                data.outb = messenger(to_femc)    #lan2can & can2lan, blocks until response
                sel.modify(sock, selectors.EVENT_WRITE, data=data)

        if mask & selectors.EVENT_WRITE:
            if data.outb:
                sock.sendall(data.outb)
                log.debug('reply to client %s with %s', sock.getpeername(), 
                    data.outb.hex())
                data.outb = b""
            sel.modify(sock, selectors.EVENT_READ, data=data)

    while True:
        events = sel.select()
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask)

log.debug('starting the pcand relay server')
try:
    relay()
finally:    # only get here if lost PCAN connection, so clean up and exit with error
    log.debug('done, closing sockets.')
    listener.close()
    lan2can.close()
    can2lan.close()
    sys.exit(1)
