#!/local/python3/bin/python3
'''
namakanui_gui.py
RMB 20190828

Tkinter GUI for Namakanui DRAMA tasks.

need retry monitors on the following:

NAMAKANUI.LOAD
NAMAKANUI.IFSWITCH
NAMAKANUI.AGILENT
<BANDx3>.DYN_STATE

state update handler can basically be identical for each band, with just
a few minor differences.  so maybe make a BandTab class to hold all the
widgets and state variables.  pass it DYN_STATE updates.

each band still needs a separate action entry point so the RESCHED timeout
thing works as it should.  if a RetryMonitor shares an action with another,
it might never see a RESCHED at all.  it ought to be okay to share with
other monitors for the same task, however.
'''

import jac_sw
import drama
import drama.retry

from tkinter import ttk  # for Notebook (tabbed interface)
import tkinter as tk

import sys
import os
taskname = 'NG_%d'%(os.getpid())

import drama.log
import logging
drama.log.setup()
log = logging.getLogger(taskname)
log.setLevel(logging.INFO)

namakanui_taskname = 'NAMAKANUI'



def grid_value(parent, row, column, sticky=''):
    '''
    Create a label at row/col and return the textvariable.
    Note you must still grid_columnconfigure and grid_rowconfigure yourself.
    '''
    textvar = tk.StringVar()
    textvar.set('')
    tk.Label(parent, textvariable=textvar).grid(row=row, column=column, sticky=sticky)
    return textvar


def grid_label(parent, text, row, last=False):
    '''
    Set up a [text value] row and return the textvariable.
    Note you must still grid_columnconfigure and grid_rowconfigure yourself.
    TODO: probably want to save these labels so we can turn them red.
    '''
    n = ''
    if last:
        n = 'n'
    tk.Label(parent, text=text).grid(row=row, column=0, sticky='nw')#n+'w')
    return grid_value(parent, row=row, column=1, sticky='ne')#n+'e')
    


class LoadFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.setup()
    
    def setup(self):
        # number simulate sim_text pos_counts pos_name busy homed
        self.pack(fill='x', expand=1)
        status_frame = tk.Frame(self)
        status_frame.pack(fill='x')
        self.v_number = grid_label(status_frame, 'number', 0)
        self.v_simulate = grid_label(status_frame, 'simulate', 1)  # TODO sim_text as tooltip
        self.v_pos_counts = grid_label(status_frame, 'pos_counts', 2)
        self.v_pos_name = grid_label(status_frame, 'pos_name', 3)
        self.v_busy = grid_label(status_frame, 'busy', 4)
        self.v_homed = grid_label(status_frame, 'homed', 5, last=True)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_rowconfigure(5, weight=1)
        cmd_frame = tk.Frame(self)
        cmd_frame.pack(side='right')#fill='x')
        move_frame = tk.Frame(cmd_frame)
        move_frame.pack(fill='x')
        self.combo = ttk.Combobox(move_frame, width=8)
        self.combo.pack(side='left')
        self.move_button = tk.Button(move_frame, text='MOVE')
        self.move_button.pack(side='right')
        def move_callback():
            drama.blind_obey(taskname, "LOAD_MOVE", POSITION=self.combo.get())
        self.move_button['command'] = move_callback
        home_frame = tk.Frame(cmd_frame)
        home_frame.pack(fill='x')
        self.home_button = tk.Button(home_frame, text='HOME')
        self.home_button.pack(side='left')
        def home_callback():
            drama.blind_obey(taskname, "LOAD_HOME")
        self.home_button['command'] = home_callback
        kick_button = tk.Button(home_frame, text='KICK')
        kick_button.pack(side='right')
        def kick_callback():
            drama.blind_kick(namakanui_taskname, "LOAD_HOME")
            drama.blind_kick(namakanui_taskname, "LOAD_MOVE")
        kick_button['command'] = kick_callback
        # LoadFrame.setup
        
    def mon_changed(self, state):
        self.v_number.set('%d'%(state['number']))
        self.v_simulate.set('0x%x'%(state['simulate']))  # TODO tooltip, warning
        self.v_pos_counts.set('%d'%(state['pos_counts']))
        self.v_pos_name.set(state['pos_name'])
        self.v_busy.set('%d'%(state['busy']))
        self.v_homed.set('%d'%(state['homed']))  # TODO warning
    
    def table_changed(self, state):
        # update the position select combo box
        self.combo['values'] = state.keys()
        
    # LoadFrame


class AgilentFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.setup()
    
    def setup(self):
        # number simulate sim_text hz dbm output
        self.pack()
        status_frame = tk.Frame(self)
        status_frame.pack(fill='x')
        self.v_number = grid_label(status_frame, 'number', 0)
        self.v_simulate = grid_label(status_frame, 'simulate', 1)  # TODO sim_text as tooltip
        self.v_dbm = grid_label(status_frame, 'dbm', 2)
        self.v_hz = grid_label(status_frame, 'hz', 3)
        self.v_output = grid_label(status_frame, 'output', 4, last=True)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_rowconfigure(4, weight=1)
        # set DBM, HZ, OUTPUT
        cmd_frame = tk.Frame(self)
        cmd_frame.pack(side='right')
        dh_frame = tk.Frame(self)
        dh_frame.pack(fill='x')
        #tk.Label(dh_frame, text='dBm: ').grid(row=0, column=0, sticky='w')
        dbm_entry = tk.Entry(dh_frame, width=13, bg='white')
        dbm_entry.grid(row=0, column=1)
        self.dbm_button = tk.Button(dh_frame, text='DBM')
        self.dbm_button.grid(row=0, column=2)
        def dbm_callback():
            drama.blind_obey(taskname, "SET_SG_DBM", float(dbm_entry.get()))
        self.dbm_button['command'] = dbm_callback
        #tk.Label(dh_frame, text='Hz: ').grid(row=1, column=0, sticky='w')
        hz_entry = tk.Entry(dh_frame, width=13, bg='white')
        hz_entry.grid(row=1, column=1)
        self.hz_button = tk.Button(dh_frame, text='HZ')
        self.hz_button.grid(row=1, column=2, sticky='nsew')
        def hz_callback():
            drama.blind_obey(taskname, "SET_SG_HZ", float(hz_entry.get()))
        self.hz_button['command'] = hz_callback
        dh_frame.grid_columnconfigure(0, weight=1)
        dh_frame.grid_columnconfigure(1, weight=1)
        dh_frame.grid_columnconfigure(2, weight=1)
        dh_frame.grid_rowconfigure(2, weight=1)
        out_frame = tk.Frame(self)
        out_frame.pack(fill='x')
        #tk.Label(out_frame, text='Output:   ').pack(side='left')
        self.on_button = tk.Button(out_frame, text='ON')
        self.on_button.pack(side='left', fill='x', expand=1)
        tk.Label(out_frame, text='   ').pack(side='left')  # spacer
        self.off_button = tk.Button(out_frame, text='OFF')
        self.off_button.pack(side='right', fill='x', expand=1)
        def on_callback():
            drama.blind_obey(taskname, "SET_SG_OUT", 1)
        def off_callback():
            drama.blind_obey(taskname, "SET_SG_OUT", 0)
        self.on_button['command'] = on_callback
        self.off_button['command'] = off_callback
        # AgilentFrame.setup
        
    def mon_changed(self, state):
        self.v_number.set('%d'%(state['number']))
        self.v_simulate.set('0x%x'%(state['simulate']))  # TODO tooltip, warning
        self.v_hz.set('%.3f'%(state['hz']))
        self.v_dbm.set('%.2f'%(state['dbm']))
        self.v_output.set('%d'%(state['output']))  # TODO warning
    
    # AgilentFrame


class IFSwitchFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.setup()
    
    def setup(self):
        # number simulate sim_text DO AI
        # TODO: supply higher-level status so we don't have to guess
        self.pack(fill='x')
        status_frame = tk.Frame(self)
        status_frame.pack(fill='x')
        self.v_number = grid_label(status_frame, 'number', 0)
        self.v_simulate = grid_label(status_frame, 'simulate', 1)  # TODO sim_text as tooltip
        self.v_do = grid_label(status_frame, 'DO', 2)
        self.v_ai = grid_label(status_frame, 'AI', 3, last=True)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_rowconfigure(3, weight=1)
        cmd_frame = tk.Frame(self)
        cmd_frame.pack(side='right')
        tk.Label(cmd_frame, text='Band: ').pack(side='left')
        def b3_callback():
            drama.blind_obey(taskname, "SET_BAND", 3)
        def b6_callback():
            drama.blind_obey(taskname, "SET_BAND", 6)
        def b7_callback():
            drama.blind_obey(taskname, "SET_BAND", 7)
        self.b3_button = tk.Button(cmd_frame, text='3', command=b3_callback)
        self.b6_button = tk.Button(cmd_frame, text='6', command=b6_callback)
        self.b7_button = tk.Button(cmd_frame, text='7', command=b7_callback)
        self.b3_button.pack(side='left')
        self.b6_button.pack(side='left')
        self.b7_button.pack(side='left')
    
    def mon_changed(self, state):
        self.v_number.set('%d'%(state['number']))
        self.v_simulate.set('0x%x'%(state['simulate']))  # TODO tooltip, warning
        self.v_do.set('%s'%(state['DO']))
        self.v_ai.set('%s'%(state['AI']))  # bad idea
    
    # IFSwitchFrame
        

class BandFrame(tk.Frame):
    def __init__(self, band, master=None):
        super().__init__(master)
        self.band = int(band)
        self.master = master
        self.tnames = ['4k', '110k', 'p0', 'spare', '15k', 'p1']
        if self.band == 3:
            self.tnames = ['spare', '110k', 'p01', 'spare', '15k', 'wca']
        self.setup()
    
    def setup(self):
        self.pack()
        
        # column frames for organizing the subframes
        c0 = tk.Frame(self)
        c1 = tk.Frame(self)
        c2 = tk.Frame(self)
        c0.pack(side='left', fill='y')
        c1.pack(side='left', fill='y')
        c2.pack(side='left', fill='y')
        
        # status subframe
        status_frame = tk.LabelFrame(c0, text='Status')
        self.v_number = grid_label(status_frame, 'number', 0)
        self.v_simulate = grid_label(status_frame, 'simulate', 1)  # TODO sim_text as tooltip
        self.v_fe_mode = grid_label(status_frame, 'fe_mode', 2)  # TODO warn?
        self.v_ppcomm_time = grid_label(status_frame, 'ppcomm_time', 3)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_rowconfigure(3, weight=1)
        
        # power subframe
        power_frame = tk.LabelFrame(c0, text='Power')
        power_status = tk.Frame(power_frame)
        power_status.pack(fill='x')
        self.v_pd_enable = grid_label(power_status, 'pd_enable', 0)
        self.v_amc_5v = grid_label(power_status, 'AMC 5v', 1)
        self.v_pa_3v = grid_label(power_status, 'PA 3v', 2)
        self.v_pa_5v = grid_label(power_status, 'PA 5v', 3)
        power_status.grid_columnconfigure(0, weight=1)
        power_status.grid_columnconfigure(1, weight=1)
        power_status.grid_rowconfigure(3, weight=1)
        power_buttons = tk.Frame(power_frame)
        power_buttons.pack()
        self.power_on_button = tk.Button(power_buttons, text='Enable')#, state='disabled')
        self.power_off_button = tk.Button(power_buttons, text='Disable')#, state='disabled')
        self.power_on_button.pack(side='left')
        self.power_off_button.pack(side='left')
        def power_on_callback():
            drama.blind_obey(taskname, "POWER", BAND=self.band, ENABLE=1)
        def power_off_callback():
            drama.blind_obey(taskname, "POWER", BAND=self.band, ENABLE=0)
        self.power_on_button['command'] = power_on_callback
        self.power_off_button['command'] = power_off_callback
        self.power_action = False  # true if POWER action is active
            
        
        # PA
        pa_frame = tk.LabelFrame(c0, text='PA')
        tk.Label(pa_frame, text='P0').grid(row=0, column=1, sticky='e')
        tk.Label(pa_frame, text='P1').grid(row=0, column=2, sticky='e')
        tk.Label(pa_frame, text='Vd').grid(row=1, column=0, sticky='e')
        tk.Label(pa_frame, text='Id').grid(row=2, column=0, sticky='e')
        tk.Label(pa_frame, text='Vg').grid(row=3, column=0, sticky='ne')
        self.v_pa_drain_v = []
        self.v_pa_drain_c = []
        self.v_pa_gate_v = []
        for i in range(2):
            self.v_pa_drain_v.append(grid_value(pa_frame, 1, i+1, 'e'))
            self.v_pa_drain_c.append(grid_value(pa_frame, 2, i+1, 'e'))
            self.v_pa_gate_v.append(grid_value(pa_frame, 3, i+1, 'ne'))
        pa_frame.grid_columnconfigure(0, weight=1)
        pa_frame.grid_columnconfigure(1, weight=1)
        pa_frame.grid_columnconfigure(2, weight=1)
        pa_frame.grid_rowconfigure(3, weight=1)
        
        # AMC, presented in a table with friendlier labels.
        # might save a little space by putting 5v in the LabelFrame.
        amc_frame = tk.LabelFrame(c0, text='AMC')
        tk.Label(amc_frame, text='Vd').grid(row=0, column=1, sticky='e')
        tk.Label(amc_frame, text='Id').grid(row=0, column=2, sticky='e')  # can they all be NE?
        tk.Label(amc_frame, text='Vg').grid(row=0, column=3, sticky='e')
        tk.Label(amc_frame, text='A').grid(row=1, column=0, sticky='e')
        self.v_amc_drain_a_v = grid_value(amc_frame, 1, 1, 'e')
        self.v_amc_drain_a_c = grid_value(amc_frame, 1, 2, 'e')
        self.v_amc_gate_a_v = grid_value(amc_frame, 1, 3, 'e')
        tk.Label(amc_frame, text='B').grid(row=2, column=0, sticky='e')
        self.v_amc_drain_b_v = grid_value(amc_frame, 2, 1, 'e')
        self.v_amc_drain_b_c = grid_value(amc_frame, 2, 2, 'e')
        self.v_amc_gate_b_v = grid_value(amc_frame, 2, 3, 'e')
        tk.Label(amc_frame, text='E').grid(row=3, column=0, sticky='e')
        self.v_amc_drain_e_v = grid_value(amc_frame, 3, 1, 'e')
        self.v_amc_drain_e_c = grid_value(amc_frame, 3, 2, 'e')
        self.v_amc_gate_e_v = grid_value(amc_frame, 3, 3, 'e')
        tk.Label(amc_frame, text='D').grid(row=4, column=0, sticky='ne')
        self.v_amc_drain_d_v = grid_value(amc_frame, 4, 1, 'ne')
        self.v_amc_drain_d_c = grid_value(amc_frame, 4, 2, 'ne')
        amc_frame.grid_columnconfigure(0, weight=1)
        amc_frame.grid_columnconfigure(1, weight=1)
        amc_frame.grid_columnconfigure(2, weight=1)
        amc_frame.grid_columnconfigure(3, weight=1)
        amc_frame.grid_rowconfigure(4, weight=1)
        
        # cart temperatures, broken out (including pll).  TODO skip spares.
        temp_frame = tk.LabelFrame(c1, text='Temperature')
        self.v_pll_temp = grid_label(temp_frame, 'pll', 0)
        self.v_cart_temp = []
        for i,n in enumerate(self.tnames):
            self.v_cart_temp.append(grid_label(temp_frame, n, i+1))
        temp_frame.grid_columnconfigure(0, weight=1)
        temp_frame.grid_columnconfigure(1, weight=1)
        temp_frame.grid_rowconfigure(i+1, weight=1)
        
        # PLL, including LO, YIG
        pll_frame = tk.LabelFrame(c1, text='PLL')
        self.v_lo_ghz = grid_label(pll_frame, 'LO GHz', 0)
        self.v_yig_ghz = grid_label(pll_frame, 'YTO GHz', 1)
        self.v_yto_coarse = grid_label(pll_frame, 'YTO counts', 2)
        self.v_yig_heater_c = grid_label(pll_frame, 'YTO heater mA', 3)
        self.v_pll_loop_bw = grid_label(pll_frame, 'loop BW', 4)
        self.v_pll_sb_lock = grid_label(pll_frame, 'lock SB', 5)
        self.v_pll_null_int = grid_label(pll_frame, 'null integrator', 6)
        self.v_pll_lock_v = grid_label(pll_frame, 'lock V', 7)
        self.v_pll_corr_v = grid_label(pll_frame, 'corr V', 8)
        self.v_pll_unlock = grid_label(pll_frame, 'unlock latch', 9)
        self.v_pll_ref_power = grid_label(pll_frame, 'ref power', 10)
        self.v_pll_if_power = grid_label(pll_frame, 'IF power', 11)
        pll_frame.grid_columnconfigure(0, weight=1)
        pll_frame.grid_columnconfigure(1, weight=1)
        pll_frame.grid_rowconfigure(11, weight=1)
        
        # LNA.  TODO band 3/6 only have a single stage.
        # config file order is Vd, Id, Vg.
        lna_frame = tk.LabelFrame(c2, text='LNA')
        tk.Label(lna_frame, text='P0/S1').grid(row=0, column=1, sticky='e')
        tk.Label(lna_frame, text='P0/S2').grid(row=0, column=2, sticky='e')
        tk.Label(lna_frame, text='P1/S1').grid(row=0, column=3, sticky='e')
        tk.Label(lna_frame, text='P1/S2').grid(row=0, column=4, sticky='e')
        tk.Label(lna_frame, text='Enable').grid(row=1, column=0, sticky='e')
        tk.Label(lna_frame, text='Vd0').grid(row=2, column=0, sticky='e')
        tk.Label(lna_frame, text='Vd1').grid(row=3, column=0, sticky='e')
        tk.Label(lna_frame, text='Vd2').grid(row=4, column=0, sticky='e')
        tk.Label(lna_frame, text='Id0').grid(row=5, column=0, sticky='e')
        tk.Label(lna_frame, text='Id1').grid(row=6, column=0, sticky='e')
        tk.Label(lna_frame, text='Id2').grid(row=7, column=0, sticky='e')
        tk.Label(lna_frame, text='Vg0').grid(row=8, column=0, sticky='e')
        tk.Label(lna_frame, text='Vg1').grid(row=9, column=0, sticky='e')
        tk.Label(lna_frame, text='Vg2').grid(row=10, column=0, sticky='ne')
        # there's got to be a better way
        self.v_lna_enable = []
        self.v_lna_vd0 = []
        self.v_lna_vd1 = []
        self.v_lna_vd2 = []
        self.v_lna_id0 = []
        self.v_lna_id1 = []
        self.v_lna_id2 = []
        self.v_lna_vg0 = []
        self.v_lna_vg1 = []
        self.v_lna_vg2 = []
        for i in range(4):
            self.v_lna_enable.append(grid_value(lna_frame, 1, i+1, 'e'))
            self.v_lna_vd0.append(grid_value(lna_frame, 2, i+1, 'e'))
            self.v_lna_vd1.append(grid_value(lna_frame, 3, i+1, 'e'))
            self.v_lna_vd2.append(grid_value(lna_frame, 4, i+1, 'e'))
            self.v_lna_id0.append(grid_value(lna_frame, 5, i+1, 'e'))
            self.v_lna_id1.append(grid_value(lna_frame, 6, i+1, 'e'))
            self.v_lna_id2.append(grid_value(lna_frame, 7, i+1, 'e'))
            self.v_lna_vg0.append(grid_value(lna_frame, 8, i+1, 'e'))
            self.v_lna_vg1.append(grid_value(lna_frame, 9, i+1, 'e'))
            self.v_lna_vg2.append(grid_value(lna_frame, 10, i+1, 'ne'))
        lna_frame.grid_columnconfigure(0, weight=1)
        lna_frame.grid_columnconfigure(1, weight=1)
        lna_frame.grid_columnconfigure(2, weight=1)
        lna_frame.grid_columnconfigure(3, weight=1)
        lna_frame.grid_columnconfigure(4, weight=1)
        lna_frame.grid_rowconfigure(10, weight=1)
        
        # SIS table.  TODO not for band 3
        sis_frame = tk.LabelFrame(c2, text='SIS')
        tk.Label(sis_frame, text='P0/S1').grid(row=0, column=1, sticky='e')
        tk.Label(sis_frame, text='P0/S2').grid(row=0, column=2, sticky='e')
        tk.Label(sis_frame, text='P1/S1').grid(row=0, column=3, sticky='e')
        tk.Label(sis_frame, text='P1/S2').grid(row=0, column=4, sticky='e')
        tk.Label(sis_frame, text='open loop').grid(row=1, column=0, sticky='e')
        tk.Label(sis_frame, text='mixer mV').grid(row=2, column=0, sticky='e')
        tk.Label(sis_frame, text='mixer uA').grid(row=3, column=0, sticky='e')
        tk.Label(sis_frame, text='magnet V').grid(row=4, column=0, sticky='e')
        tk.Label(sis_frame, text='magnet mA').grid(row=5, column=0, sticky='ne')
        self.v_sis_open_loop = []
        self.v_sis_v = []
        self.v_sis_c = []
        self.v_sis_mag_v = []
        self.v_sis_mag_c = []
        for i in range(4):
            self.v_sis_open_loop.append(grid_value(sis_frame, 1, i+1, 'e'))
            self.v_sis_v.append(grid_value(sis_frame, 2, i+1, 'e'))
            self.v_sis_c.append(grid_value(sis_frame, 3, i+1, 'e'))
            self.v_sis_mag_v.append(grid_value(sis_frame, 4, i+1, 'e'))
            self.v_sis_mag_c.append(grid_value(sis_frame, 5, i+1, 'ne'))
        sis_frame.grid_columnconfigure(0, weight=1)
        sis_frame.grid_columnconfigure(1, weight=1)
        sis_frame.grid_columnconfigure(2, weight=1)
        sis_frame.grid_columnconfigure(3, weight=1)
        sis_frame.grid_columnconfigure(4, weight=1)
        sis_frame.grid_rowconfigure(5, weight=1)
        
        # TUNE command entry and button.  fixed at VOLTAGE=0.
        tune_frame = tk.LabelFrame(c2, text='Tune')
        tk.Label(tune_frame, text='LO GHz: ').pack(side='left')
        tune_entry = tk.Entry(tune_frame, width=14, bg='white')
        tune_entry.pack(side='left', fill='x')
        self.tune_button = tk.Button(tune_frame, text='TUNE')
        self.tune_button.pack(side='right')
        def tune_callback():
            drama.blind_obey(taskname, "TUNE", BAND=self.band, LO_GHZ=float(tune_entry.get()), VOLTAGE=0.0)
        self.tune_button['command'] = tune_callback
        
        # TODO: better arrangement?
        
        status_frame.pack(fill='x')
        power_frame.pack(fill='x')
        pa_frame.pack(fill='x')
        amc_frame.pack(fill='both', expand=1)
        
        temp_frame.pack(fill='x')
        pll_frame.pack(fill='both', expand=1)
        
        lna_frame.pack(fill='x')
        sis_frame.pack(fill='x')
        tune_frame.pack(fill='both', expand=1)
        
        # BandFrame.setup
        
        
    
    def mon_changed(self, state):
        self.v_number.set('%d'%(state['number']))
        self.v_simulate.set('0x%x'%(state['simulate']))  # TODO tooltip, warning
        # more or less alphabetical order
        self.v_amc_5v.set(state['amc_5v'])
        self.v_amc_drain_a_c.set('%.3f'%(state['amc_drain_a_c']))
        self.v_amc_drain_a_v.set('%.3f'%(state['amc_drain_a_v']))
        self.v_amc_drain_b_c.set('%.3f'%(state['amc_drain_b_c']))
        self.v_amc_drain_b_v.set('%.3f'%(state['amc_drain_b_v']))
        self.v_amc_drain_e_c.set('%.3f'%(state['amc_drain_e_c']))
        self.v_amc_drain_e_v.set('%.3f'%(state['amc_drain_e_v']))
        self.v_amc_gate_a_v.set('%.3f'%(state['amc_gate_a_v']))
        self.v_amc_gate_b_v.set('%.3f'%(state['amc_gate_b_v']))
        self.v_amc_gate_e_v.set('%.3f'%(state['amc_gate_e_v']))
        self.v_amc_mult_d_c.set('%.3f'%(state['amc_mult_d_c']))
        self.v_amc_mult_d_v.set('%.3f'%(state['amc_mult_d_v']))
        
        self.v_pll_temp.set('%.3f'%(state['pll_temp']))
        for i,v in enumerate(state['cart_temp']):
            self.v_cart_temp[i].set('%.3f'%(v))
        
        self.v_fe_mode.set('%d'%(state['fe_mode']))
        
        for i in range(4):  # p0s1 ... p1s2
            self.v_lna_enable[i].set('%d'%(state['lna_enable'][i]))
            self.v_lna_vd0[i].set('%.3f'%(state['lna_drain_v'][i*3+0]))
            self.v_lna_vd1[i].set('%.3f'%(state['lna_drain_v'][i*3+1]))
            self.v_lna_vd2[i].set('%.3f'%(state['lna_drain_v'][i*3+2]))
            self.v_lna_id0[i].set('%.3f'%(state['lna_drain_c'][i*3+0]))
            self.v_lna_id1[i].set('%.3f'%(state['lna_drain_c'][i*3+1]))
            self.v_lna_id2[i].set('%.3f'%(state['lna_drain_c'][i*3+2]))
            self.v_lna_vg0[i].set('%.3f'%(state['lna_gate_v'][i*3+0]))
            self.v_lna_vg1[i].set('%.3f'%(state['lna_gate_v'][i*3+1]))
            self.v_lna_vg2[i].set('%.3f'%(state['lna_gate_v'][i*3+2]))
        
        self.v_lo_ghz.set('%.9f'%(state['lo_ghz']))
        self.v_pa_3v.set('%.3f'%(state['pa_3v']))
        self.v_pa_5v.set('%.3f'%(state['pa_5v']))
        
        for i in range(2):
            self.v_pa_drain_v[i].set('%.3f'%(state['pa_drain_v'][i]))
            self.v_pa_drain_c[i].set('%.3f'%(state['pa_drain_c'][i]))
            self.v_pa_gate_v[i].set('%.3f'%(state['pa_gate_v'][i]))
        
        self.v_pd_enable.set('%d'%(state['pd_enable']))
        if not self.power_action:
            if state['pd_enable']:
                self.power_on_button['state'] = 'disabled'
                self.power_off_button['state'] = 'normal'
            else:
                self.power_on_button['state'] = 'normal'
                self.power_off_button['state'] = 'disabled'
        
        self.v_pll_lock_v.set('%.3f'%(state['pll_lock_v']))
        self.v_pll_corr_v.set('%.3f'%(state['pll_corr_v']))
        self.v_pll_if_power.set('%.3f'%(state['pll_if_power']))
        self.v_pll_ref_power.set('%.3f'%(state['pll_ref_power']))
        
        self.v_pll_loop_bw.set('%d'%(state['pll_loop_bw']))
        self.v_pll_null_int.set('%d'%(state['pll_null_int']))
        self.v_pll_sb_lock.set('%d'%(state['pll_sb_lock']))
        self.v_pll_unlock.set('%d'%(state['pll_unlock']))
        
        self.v_ppcomm_time.set('%.6f'%(state['ppcomm_time']))
        
        for i in range(4):
            self.v_sis_open_loop[i].set('%d'%(state['sis_open_loop'][i]))
            self.v_sis_c[i].set('%.3f'%(state['sis_c'][i]))
            self.v_sis_v[i].set('%.3f'%(state['sis_v'][i]))
            self.v_sis_mag_c[i].set('%.3f'%(state['sis_mag_c'][i]))
            self.v_sis_mag_v[i].set('%.3f'%(state['sis_mag_v'][i]))
        
        self.v_yig_ghz.set('%.9f'%(state['yig_ghz']))
        self.v_yig_heater_c.set('%.3f'%(state['yig_heater_c']))
        self.v_yto_coarse.set('%d'%(state['yto_coarse']))
        
        # BandFrame.mon_changed
 
    # BandFrame


class App(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.setup()
        self.actions = [self.MON_MAIN, self.MON_B3, self.MON_B6, self.MON_B7,
                        self.POWER, self.TUNE, self.LOAD_MOVE, self.LOAD_HOME,
                        self.SET_SG_DBM, self.SET_SG_HZ, self.SET_SG_OUT,
                        self.SET_BAND]
        
        self.retry_tasknames = drama.retry.RetryMonitor(namakanui_taskname, 'TASKNAMES')
        self.retry_load = drama.retry.RetryMonitor(namakanui_taskname, 'LOAD')
        self.retry_load_table = drama.retry.RetryMonitor(namakanui_taskname, 'LOAD_TABLE')
        self.retry_agilent = drama.retry.RetryMonitor(namakanui_taskname, 'AGILENT')
        self.retry_ifswitch = drama.retry.RetryMonitor(namakanui_taskname, 'IFSWITCH')
        
        # temporary tasknames; will be set on TASKNAMES update
        self.retry_b3 = drama.retry.RetryMonitor('B3_DUMMY', 'DYN_STATE')
        self.retry_b6 = drama.retry.RetryMonitor('B6_DUMMY', 'DYN_STATE')
        self.retry_b7 = drama.retry.RetryMonitor('B7_DUMMY', 'DYN_STATE')
        
        # App.__init__

    def setup(self):
        nam_frame = tk.Frame(self)
        nam_frame.pack(side='left', fill='y')
        
        load_parent = tk.LabelFrame(nam_frame, text='LOAD')
        load_parent.pack(fill='x')
        self.load_frame = LoadFrame(load_parent)
        
        agilent_parent = tk.LabelFrame(nam_frame, text='AGILENT')
        agilent_parent.pack(fill='x')
        self.agilent_frame = AgilentFrame(agilent_parent)
        
        ifswitch_parent = tk.LabelFrame(nam_frame, text='IFSWITCH')
        ifswitch_parent.pack(fill='x')
        self.ifswitch_frame = IFSwitchFrame(ifswitch_parent)
        
        # spacer
        space_label = tk.Label(self, text=' ')
        space_label.pack(side='left')
        
        notebook = ttk.Notebook(self)
        self.b3_frame = BandFrame(3, notebook)
        self.b6_frame = BandFrame(6, notebook)
        self.b7_frame = BandFrame(7, notebook)
        notebook.add(self.b3_frame, text='B3')
        notebook.add(self.b6_frame, text='B6')
        notebook.add(self.b7_frame, text='B7')
        notebook.pack(side='right')
        
        # App.setup
        
    
    def start_monitors(self):
        # MON_MAIN will start MON_B3 etc when it gets cartridge tasknames
        drama.blind_obey(taskname, 'MON_MAIN')
    
    def MON_MAIN(self, msg):
        '''Calls handle() on all NAMAKANUI RetryMonitors.'''
        
        if self.retry_tasknames.handle(msg):
            # tasknames changed; cancel old monitors if connected
            for b,r in [[3,self.retry_b3], [6,self.retry_b6], [7,self.retry_b7]]:
                new_taskname = msg.arg['B%d'%(b)]
                if r.task == new_taskname:
                    continue
                if r.connected:
                    r.cancel()
                r.task = new_taskname
                drama.blind_obey(taskname, 'MON_B%d'%(b))
        
        if self.retry_load.handle(msg):
            self.load_frame.mon_changed(msg.arg)
        
        if self.retry_load_table.handle(msg):
            self.load_frame.table_changed(msg.arg)
        
        if self.retry_agilent.handle(msg):
            self.agilent_frame.mon_changed(msg.arg)
        
        if self.retry_ifswitch.handle(msg):
            self.ifswitch_frame.mon_changed(msg.arg)
        
        # TODO handle disconnected state
        
        drama.reschedule(15.0)  # NAMAKANUI.UPDATE is pretty slow
        
        # App.MON_MAIN
    
    
    def MON_B3(self, msg):
        if self.retry_b3.handle(msg):
            self.b3_frame.mon_changed(msg.arg)
        # TODO handle disconnected state
        drama.reschedule(5.0)
    
    def MON_B6(self, msg):
        if self.retry_b6.handle(msg):
            self.b6_frame.mon_changed(msg.arg)
        # TODO handle disconnected state
        drama.reschedule(5.0)
    
    def MON_B7(self, msg):
        if self.retry_b7.handle(msg):
            self.b7_frame.mon_changed(msg.arg)
        # TODO handle disconnected state
        drama.reschedule(5.0)
    
    def power_args(self, BAND, ENABLE):
        return int(BAND), int(ENABLE)
    
    def POWER(self, msg):
        # the easy way
        args,kwargs = drama.parse_argument(msg.arg)
        band,enable = self.power_args(*args,**kwargs)
        frame = {3:self.b3_frame, 6:self.b6_frame, 7:self.b7_frame}[band]
        frame.power_action = True
        frame.power_on_button['state'] = 'disabled'
        frame.power_off_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "CART_POWER", BAND=band, ENABLE=enable).wait(120)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from CART_POWER: %s', msg)
            elif msg.status:
                log.error('bad status from CART_POWER: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in POWER')
            raise
        finally:
            frame.power_action = False
            # wait for update to reenable buttons
        
        # App.POWER
    
    def tune_args(self, BAND, LO_GHZ, VOLTAGE):
        return int(BAND), float(LO_GHZ), float(VOLTAGE)
    
    def TUNE(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        band,lo_ghz,voltage = self.tune_args(*args,**kwargs)
        frame = {3:self.b3_frame, 6:self.b6_frame, 7:self.b7_frame}[band]
        frame.tune_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "CART_TUNE", BAND=band, LO_GHZ=lo_ghz, VOLTAGE=voltage).wait(30)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from CART_TUNE: %s', msg)
            elif msg.status:
                log.error('bad status from CART_TUNE: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in TUNE')
            raise
        finally:
            frame.tune_button['state'] = 'normal'
        # App.TUNE
    
    def move_args(self, POSITION):
        return POSITION
    
    def LOAD_MOVE(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        pos = self.tune_args(*args,**kwargs)
        self.load_frame.move_button['state'] = 'disabled'
        self.load_frame.home_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "LOAD_MOVE", POSITION=pos).wait(30)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from LOAD_MOVE: %s', msg)
            elif msg.status:
                log.error('bad status from LOAD_MOVE: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in LOAD_MOVE')
            raise
        finally:
            self.load_frame.move_button['state'] = 'normal'
            self.load_frame.home_button['state'] = 'normal'
        # App.LOAD_MOVE
    
    def LOAD_HOME(self, msg):
        self.load_frame.move_button['state'] = 'disabled'
        self.load_frame.home_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "LOAD_HOME").wait(30)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from LOAD_HOME: %s', msg)
            elif msg.status:
                log.error('bad status from LOAD_HOME: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in LOAD_MOVE')
            raise
        finally:
            self.load_frame.move_button['state'] = 'normal'
            self.load_frame.home_button['state'] = 'normal'
        # App.LOAD_MOVE
    
    # TODO: some convenience functions to reduce this boilerplate might be handy
    
    def dbm_args(self, DBM):
        dbm = float(DBM)
        if dbm < -130.0 or dbm > 0.0:
            raise drama.BadStatus(drama.INVARG, 'dbm %g outside [-130, 0] range'%(dbm))
        return dbm
    
    def SET_SG_DBM(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        dbm = self.dbm_args(*args,**kwargs)
        self.agilent_frame.dbm_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "SET_SG_DBM", DBM=dbm).wait(5)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from SET_SG_DBM: %s', msg)
            elif msg.status:
                log.error('bad status from SET_SG_DBM: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in SET_SG_DBM')
            raise
        finally:
            self.agilent_frame.dbm_button['state'] = 'normal'
        # App.SET_SG_DBM
    
    def hz_args(self, HZ):
        hz = float(HZ)
        if hz < 9e3 or hz > 32e9:
            raise drama.BadStatus(drama.INVARG, 'hz %g outside [9 KHz, 32 GHz] range'%(hz))
        return hz
    
    def SET_SG_HZ(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        hz = self.hz_args(*args,**kwargs)
        self.agilent_frame.hz_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "SET_SG_HZ", HZ=hz).wait(5)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from SET_SG_HZ: %s', msg)
            elif msg.status:
                log.error('bad status from SET_SG_HZ: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in SET_SG_HZ')
            raise
        finally:
            self.agilent_frame.hz_button['state'] = 'normal'
        # App.SET_SG_HZ
    
    def out_args(self, OUT):
        return int(bool(OUT))
    
    def SET_SG_OUT(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        out = self.out_args(*args,**kwargs)
        self.agilent_frame.out_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "SET_SG_OUT", OUT=out).wait(5)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from SET_SG_OUT: %s', msg)
            elif msg.status:
                log.error('bad status from SET_SG_OUT: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in SET_SG_OUT')
            raise
        finally:
            self.agilent_frame.out_button['state'] = 'normal'
        # App.SET_SG_OUT
    
    def band_args(self, BAND):
        band = int(BAND)
        if band not in [3,6,7]:
            raise drama.BadStatus(drama.INVARG, 'BAND %d not one of [3,6,7]' % (band))
        return band
    
    def SET_BAND(self, msg):
        args,kwargs = drama.parse_argument(msg.arg)
        band = self.band_args(*args,**kwargs)
        self.ifswitch_frame.b3_button['state'] = 'disabled'
        self.ifswitch_frame.b6_button['state'] = 'disabled'
        self.ifswitch_frame.b7_button['state'] = 'disabled'
        try:
            msg = drama.obey(namakanui_taskname, "SET_BAND", BAND=band).wait(5)
            if msg.reason != drama.REA_COMPLETE:
                log.error('unexpected msg from SET_BAND: %s', msg)
            elif msg.status:
                log.error('bad status from SET_BAND: %d: %s', msg.status, drama.get_status_string(msg.status))
        except:
            log.exception('exception in SET_BAND')
            raise
        finally:
            self.ifswitch_frame.b3_button['state'] = 'normal'
            self.ifswitch_frame.b6_button['state'] = 'normal'
            self.ifswitch_frame.b7_button['state'] = 'normal'
    
    # App


try:
    log.info('tk init')
    root = tk.Tk()
    root.title('Namakanui GUI: ' + taskname)
    app = App(root)
    log.info('drama.init(%s)', taskname)
    drama.init(taskname, actions=app.actions)
    #app.start_monitors()
    log.info('drama.run()...')
    drama.run()
finally:
    log.info('drama.stop(%s)', taskname)
    drama.stop()
    log.info('done')
        

