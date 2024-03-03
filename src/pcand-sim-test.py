#!/usr/bin/env python3
'''
Locutus 2024.03.03

Simulate a PCAN device and test the communication with what is implemented in namakanui_pcand.py
'''

import argparse, asyncio, logging, select, selectors, socket, sys, time, os
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
    
    lan2can.sendall(msg)
    log.debug('sent to lan2can: %s', msg.hex())

    packet = can2lan.recv(36)
    log.debug('can2lan recv:    %s', packet.hex())
    if not packet:
        log.error('lost PCAN connection')
        raise Exception('lost PCAN connection')
    else:
        return packet

async def relay(reader, writer):
    '''relay communications between client programs and the PCAN'''
    to_femc = await reader.read(36)
    client = writer.get_extra_info('peername')
    log.debug('recv %d bytes:   %s from client %s', len(to_femc), to_femc.hex(), client)
    if to_femc == b'':   log.exception('recv exception for client %s', client)
    if len(to_femc) < 36:  # bad/lost/closed connection
        log.debug('dropping client %s', client)
    else:
        from_femc = messenger(to_femc)    #lan2can & can2lan, blocks until response
        writer.write(from_femc)
        log.debug('reply to client %s with %s', client, from_femc.hex())
        await writer.drain()

    writer.close()
    await writer.wait_closed()

async def main():
    server = await asyncio.start_server(relay, sock=listener)
    async with server:
        #await asyncio.create_task(asyncio.to_thread(PCAN))
        await server.serve_forever()

#%% parallel sockets test
def ding(task):
    #time.sleep(2.0)     # wait until everything else is ready
    pid = os.getpid();  print(f'Task {task}, PID = {pid}')
    with socket.socket() as s:
        s.settimeout(5)
        s.connect(('localhost', 2002))
        msg = f'{pid:*<36}'
        s.sendall(msg.encode())
        r = s.recv(36)
        print(f'Input: {msg} \t Return: {r}')

def dong():
    ''' a wrapper because the ContextManager will attempt to finish all processes
        before proceeding.
    '''
    with ProcessPoolExecutor() as P:
        log.debug('simulating parallel connections')
        P.map(ding, range(4))

darq = Process(target=dong);    darq.start()

#%%
log.debug('entering asyncio event loop')
try:
    asyncio.run(main())
finally:    # only get here if lost PCAN connection, so clean up and exit with error
    log.debug('done, closing sockets.')
    pcan.terminate()
    darq.terminate()
    listener.close()
    lan2can.close()
    can2lan.close()
    sys.exit(1)