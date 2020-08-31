#!/local/python3/bin/python3
'''
RMB 20200221
Tune to a range of frequencies.
At each frequency, set PA to a range of values.
Record average mixer current at each PA, for each mixer.

Motivation:  Mixer current was much lower than expected
at LO 249 GHz with the new mixer block.  I'm wondering
if there are strange dropouts at various frequencies.

Recording this data is a little troublesome.
I'll use topcat ascii format, with each column
a separate mixer/pa combo.  Plotting data is also
troublesome.  I might want a separate program for that.
'''

import jac_sw
import sys
import os
import time
import argparse
import namakanui.cart
import namakanui.agilent
import namakanui.femc
import namakanui.load
import namakanui.ifswitch
import namakanui.util
import logging

logging.root.setLevel(logging.INFO)
logging.root.addHandler(logging.StreamHandler())

binpath, datapath = namakanui.util.get_paths()
    
parser = argparse.ArgumentParser()
parser.add_argument('band', type=int, choices=[6,7])
parser.add_argument('--lo')  # range
parser.add_argument('--pa')  # range
parser.add_argument('--load', nargs='?', default='hot')
parser.add_argument('lock_polarity', nargs='?', choices=['below','above'], default='above')
parser.add_argument('--note', nargs='?', default='', help='note for file header')
args = parser.parse_args()

band = args.band
los = namakanui.util.parse_range(args.lo, maxlen=100e3)
pas = namakanui.util.parse_range(args.pa, maxlen=300)

# create file header.
# trying to plot this manually in topcat would be a nightmare anyway,
# so just use the order that makes it easy to write the file.
sys.stdout.write(time.strftime('# %Y%m%d %H:%M:%S HST\n', time.localtime()))
sys.stdout.write('# %s\n'%(sys.argv))
sys.stdout.write('# load: %s\n'%(args.load))
sys.stdout.write('#\n')
sys.stdout.write('#lo_ghz pa_3v pa_5v ')
for pa in pas:
    for mixer in ['01', '02', '11', '12']:
        sys.stdout.write('ua%s_%03d '%(mixer, pa*100))
    for po in ['0', '1']:
        sys.stdout.write('vd%s_%03d '%(po, pa*100))
    for po in ['0', '1']:
        sys.stdout.write('id%s_%03d '%(po, pa*100))
    for po in ['0', '1']:
        sys.stdout.write('vg%s_%03d '%(po, pa*100))
sys.stdout.write('\n')

# init load controller and set desired load (default hot)
load = namakanui.load.Load(datapath+'load.ini', time.sleep, namakanui.nop, simulate=0)
if args.load == 'hot' or args.load == 'sky':
    args.load = 'b%d_'%(band) + args.load
load.move(args.load)

# set agilent output to a safe level before setting ifswitch
agilent = namakanui.agilent.Agilent(datapath+'agilent.ini', time.sleep, namakanui.nop, simulate=0)
agilent.set_dbm(agilent.safe_dbm)
agilent.set_output(1)
ifswitch = namakanui.ifswitch.IFSwitch(datapath+'ifswitch.ini', time.sleep, namakanui.nop, simulate=0)
ifswitch.set_band(band)

# power up the cartridge
cart = namakanui.cart.Cart(band, datapath+'band%d.ini'%(band), time.sleep, namakanui.nop, simulate=0)
cart.power(1)
cart.femc.set_cartridge_lo_pll_sb_lock_polarity_select(cart.ca, {'below':0, 'above':1}[args.lock_polarity])
floog = agilent.floog * {'below':1.0, 'above':-1.0}[args.lock_polarity]


x = []
y = [[], [], [], []]
# we need a y for each mixer and pa; y[mixer][pa_index] is an array of len(x)
for i in range(4):
    for pa in pas:
        y[i].append([])

# main loop
for lo in los:
    if not namakanui.util.tune(cart, agilent, None, lo, skip_servo_pa=True):
        continue
    x.append(lo)
    sys.stdout.write('%.3f '%(lo))
    for j,pa in enumerate(pas):
        cart._set_pa([pa,pa])
        time.sleep(0.05)
        # check voltages
        pa_3v = self.femc.get_cartridge_lo_pa_supply_voltage_3v(self.ca)
        pa_5v = self.femc.get_cartridge_lo_pa_supply_voltage_5v(self.ca)
        sys.stdout.write('%.3f %.3f '%(pa_3v, pa_5v))
        # average mixer currents
        n = 10
        uas = [0.0]*4
        for i in range(n):
            for po in range(2):
                for sb in range(2):
                    uas[po*2 + sb] += cart.femc.get_sis_current(cart.ca,po,sb)*1e3
        for i in range(4):
            uas[i] /= n
            sys.stdout.write('%.3f '%(uas[i]))
            y[i][j].append(uas[i])
        # amp feedback
        pa_vd = [0.0]*2
        pa_id = [0.0]*2
        pa_vg = [0.0]*2
        for po in range(2):
            pa_vg[po] = self.femc.get_cartridge_lo_pa_gate_voltage(self.ca, po)
            pa_vd[po] = self.femc.get_cartridge_lo_pa_drain_voltage(self.ca, po)
            pa_id[po] = self.femc.get_cartridge_lo_pa_drain_current(self.ca, po)
        sys.stdout.write('%.3f %.3f '%(pa_vd[0], pa_vd[1]))
        sys.stdout.write('%.3f %.3f '%(pa_id[0], pa_id[1]))
        sys.stdout.write('%.3f %.3f '%(pa_vg[0], pa_vg[1]))
    sys.stdout.write('\n')
    sys.stdout.flush()

# make a set of plots, one subplot per mixer
logging.info('done.  creating plot...')
from pylab import *
for i in range(4):
    p = subplot(2,2,i+1)
    for j,pa in enumerate(pas):
        p.plot(x,y[i][j])
    p.grid()
show()


