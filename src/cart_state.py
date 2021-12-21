#!/usr/bin/env python3
import jac_sw
import sys
import logging
import time
import pprint
import namakanui.cart
import namakanui.util
import namakanui.ini

logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(logging.StreamHandler())

binpath, datapath = namakanui.util.get_paths()

band = 6
if len(sys.argv) > 1:
    band = int(sys.argv[1])

cart = namakanui.cart.Cart(band, datapath+'band%d.ini'%(band), sleep=time.sleep, publish=namakanui.nop)
cart.power(1)
cart.update_all()
pprint.pprint(cart.state)
