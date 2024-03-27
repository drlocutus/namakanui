#!/usr/bin/env python3
'''
Locutus 2024.03.03

Simulate a PCAN device and test the communication with what is implemented in namakanui_pcand.py
'''

import argparse, asyncio, logging, select, selectors, socket, sys, time, types, os
from multiprocessing import Process
from concurrent.futures import ProcessPoolExecutor

logging.basicConfig()   # must set up the root logger
log = logging.getLogger('pcand')

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-v', '--verbose', action='store_true', help='enable debug logging output')
args = parser.parse_args()

if args.verbose:
    log.setLevel(logging.DEBUG)

#%%
def PCAN():
    sel = selectors.DefaultSelector()

    def accept(sock, mask):
        conn, addr = sock.accept()  # new socket; should be ready
        print(f"{time.strftime('%X')} @PCAN - accepted", conn, 'from', addr)
        conn.setblocking(False)
        sel.register(conn, selectors.EVENT_READ, read)

    def read(conn, mask):
        data = conn.recv(1000)  # Should be ready
        if data:
            time.sleep(1.0)     # slow the response; NOT CONCURRENT
            #print(f"{time.strftime('%X')} echoing {data!r} to", conn)
            #conn.sendall(data)  # Hope it won't block
            sel.register(pcan2relay, selectors.EVENT_WRITE, (send, data))
        else:
            print(f"{time.strftime('%X')} No data received. Closing", conn)
            sel.unregister(conn)
            conn.close()        # close the new socket
    
    def send(conn, data):
        print(f"{time.strftime('%X')} PCAN replies to ", conn)
        conn.sendall(data[:14] + b'--_xx_--sent from PCAN')
        sel.unregister(conn)    # Without this, conn will keep sending data

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost', 2000))
    sock.listen()
    sock.setblocking(False)
    sel.register(sock, selectors.EVENT_READ, accept)

    pcan2relay = socket.socket()
    #pcan2lan.setblocking(False)
    while True:
        try:
            pcan2relay.connect(('localhost', 2001))
            pcan2relay.sendall(b'Hello!!!!! from PCAN')
            break
        except ConnectionRefusedError:
            time.sleep(1.0)
            log.debug('PCAN is waiting for the relay server to start')

    while True:
        events = sel.select()
        for key, mask in events:
            try:
                callback = key.data[0]
                callback(key.fileobj, key.data[1])
            except:
                callback = key.data
                callback(key.fileobj, mask)

# standalone PCAN process
log.debug('PCAN running in a process')
pcan = Process(target=PCAN, daemon=True, name='PCAN')
pcan.start()
time.sleep(0.1)
if pcan.is_alive():     log.debug(f'PCAN daemon PID= {pcan.pid}')

#%%
lan2can = socket.socket()
lan2can.settimeout(1)
lan2can.connect(('localhost', 2000))    ###### PCAN should start first

can2lan_listener = socket.socket()
can2lan_listener.settimeout(5)
can2lan_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
can2lan_listener.bind(('localhost', 2001))
can2lan_listener.listen()
can2lan, _addr = can2lan_listener.accept()      # blocks until PCAN connects
can2lan.settimeout(5)
log.debug('1st message from PCAN: {}'.format(can2lan.recv(128)))
can2lan_listener.shutdown(socket.SHUT_RDWR)
can2lan_listener.close()

listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(('localhost', 2002))
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

#%% parallel sockets + burst communication test
def ding(task):
    #time.sleep(2.0)     # wait until servers are ready; let socket timeout handle it
    pid = os.getpid();  print(f'Task {task}, PID = {pid}')
    with socket.socket() as s:
        #s.settimeout(None)    # default=no timeout, allows PCAN responses in sequence
        s.connect(('localhost', 2002))
        repeats = 2
        msg = ''
        for i in range(repeats):
            _m = f'p={pid}, s={i}'
            msg += f'{_m:*<36}'
        s.sendall(msg.encode())
        r = b''
        while len(r) < 36*repeats:
            r += s.recv(1024)
        print(f'pid={pid}, hold on for 5 seconds before closing the socket.')
        time.sleep(5.0)
        print(s.getsockname(), f'Input: {msg} \t Return: {r}')

def dong():
    ''' a wrapper because the ContextManager will attempt to finish all processes
        before proceeding.
    '''
    with ProcessPoolExecutor() as P:
        log.debug('simulating parallel connections')
        P.map(ding, range(3))

darq = Process(target=dong);    darq.start()

#%%
log.debug('starting the relay server')
try:
    relay()
except Exception as e:
    log.exception(e)
finally:    # only get here if lost PCAN connection, so clean up and exit with error
    log.debug('done, closing processes & sockets.')
    pcan.terminate()    
    darq.terminate()    # child processes will be orphaned
    listener.close()
    lan2can.close()
    can2lan.close()
    sys.exit(1)