#!/usr/bin/env python3

import jac_sw
import namakanui.femc
import namakanui.util
import logging
namakanui.util.setup_logging(logging.DEBUG)
f = namakanui.femc.FEMC(level=logging.DEBUG)
print('get_setup_info:', f.get_setup_info())
print('get_version_info:', f.get_version_info())
print('get_ambsi1_version_info:', f.get_ambsi1_version_info())
print('get_fpga_version_info:', f.get_fpga_version_info())
print('get_fe_mode:', f.get_fe_mode())
print('get_ppcomm_time:', f.get_ppcomm_time())
print('get_pd_powered_modules:', f.get_pd_powered_modules())
