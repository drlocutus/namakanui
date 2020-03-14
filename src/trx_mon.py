#!/local/python3/bin/python3
'''
RMB 20200218

This version continuously monitors IFTASK:YFACTOR and prints updates
as they come in.

Calculate an array of Trx values from the IFTASK YFACTOR values.
Assumes Jhot is Namakanui ambient load temperature and that Jcold is 80K.
The receiver must already be tuned to the desired frequency,
IFTASK must be setup and leveled and running the YFACTOR action,
and the disk must be spinning for at least CALC_TIME already.

Trx = (Jhot - Y*Jcold) / (Y-1)

Proof:
slope = (Phot - Pcold) / (Jhot - Jcold)
Pcold = (Trx + Jcold) * slope
Phot  = (Trx + Jhot) * slope
Y = Phot/Pcold = ((Trx+Jhot)*slope) / ((Trx+Jcold)*slope) = (Trx+Jhot)/(Trx+Jcold)
Y*(Trx+Jcold) = Trx+Jhot
Y*Trx - Trx = Jhot - Y*Jcold
Trx*(Y-1) = Jhot - Y*Jcold
Trx = (Jhot - Y*Jcold) / (Y-1)

This method is slow and tedious and should not be used by anyone.
'''

import jac_sw
import drama
import epics
import sys
import os
import numpy

taskname = 'NMTRX_%d'%(os.getpid())

import drama.log
drama.log.setup()  # no save to file
import logging
log = logging.getLogger(taskname)
log.info('startup')

def MAIN(msg):
    
    if msg.reason == drama.REA_OBEY:
        drama.monitor('IFTASK@if-micro', 'YFACTOR')
        drama.reschedule()
        return
    elif msg.reason != drama.REA_TRIGGER:
        log.error('unexpected entry reason, msg: %s', msg)
        raise drama.Exit('bad msg')
    elif msg.status == drama.MON_STARTED:
        drama.reschedule()
        return
    
    log.info('YFACTOR update...')
    yfactor = msg.arg

    log.info('getting ambient temperature...')
    jamb = epics.caget('nmnCryo:ls:temp5')
    jcold = 80.0
    # AVG_PWR, LOW_PWR, HIGH_PWR, Y_FAC should already be numpy arrays
    log.info('J: %.3f, %.3f', jcold, jamb)
    log.info('AVG_SIZE:\n%s', yfactor['AVG_SIZE'])
    log.info('LOW_SIZE:\n%s', yfactor['LOW_SIZE'])
    log.info('HIGH_SIZE:\n%s', yfactor['HIGH_SIZE'])
    log.info('AVG_PWR:\n%s', yfactor['AVG_PWR'])
    log.info('HIGH_PWR:\n%s', yfactor['HIGH_PWR'])
    log.info('LOW_PWR:\n%s', yfactor['LOW_PWR'])
    log.info('Y_FAC:\n%s', yfactor['Y_FAC'])
    # why does this differ from Y_FAC? how is Y_FAC calculated?
    # PWR might be in dbm, in which case Y = 10**((HIGH-LOW)/10)
    #my_y = yfactor['HIGH_PWR'] / yfactor['LOW_PWR']
    #log.info('MY_Y:\n%s', my_y)
    # this one is correct, so no more reason to print it out
    #my_y2 = 10**(0.1*(yfactor['HIGH_PWR']-yfactor['LOW_PWR']))
    #log.info('MY_Y2:\n%s', my_y2)
    y = yfactor['Y_FAC']
    trx = (jamb - y*jcold) / (y-1)
    # zero out any spots with no samples
    trx *= yfactor['AVG_SIZE'].astype(bool).astype(float)
    log.info('trx:\n%s', trx)

    # print out stats/summary in blocks of 4
    i = 0
    n = 4
    while i < len(trx):
        b = trx[i:i+n]
        
        log.info('dcm %2d-%2d: %s avg: %.2f +- %.2f', i, i+n-1, b.round(2), b.mean(), b.std())
        i += n
    
    # reschedule to wait for new update
    drama.reschedule()
        

try:
    drama.init(taskname, actions=[MAIN])
    drama.blind_obey(taskname, 'MAIN')
    log.info('run')
    drama.run()
finally:
    log.info('stop')
    drama.stop()


