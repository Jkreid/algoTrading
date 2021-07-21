# -*- coding: utf-8 -*-
"""
Created on Wed Aug  5 22:24:27 2020
"""
import os
os.sys.path.insert(1, os.path.realpath('./daytrade'))
from configparser import ConfigParser
from trader import LiveTrader
from strategyxframeworks import get_framework

def main(framework, runtime, revtime, gateway, ibc, 
         algos=[], save_data=True, file_exts=[]):
    algo_files = [f'algos/{algo}.ini' for algo in algos]
    ib = LiveTrader(mod=True, gateway=gateway)
    if ibc:
        ib.begin()
    framework = get_framework(framework, ib, *algo_files, client_id=1)
    if framework:
        framework.run(runtime, revtime)
        if save_data:
            save_dir = ib.save_run_data(*file_exts)
            framework.save_inputs(save_dir)
    ib.disconnect()
    if ibc:
        ib.end()
        ib.close()

if __name__ == '__main__':
    config = ConfigParser()
    config.read('main.ini')
    framework = config.get('Parameters', 'framework')
    algos = config.get('Parameters', 'algos').split(',')
    time_mult = config.getfloat('Parameters', 'time_mult')
    runtime = config.getfloat('Parameters', 'runtime')*time_mult
    revtime = config.getfloat('Parameters', 'revtime')*time_mult
    ibc = config.getboolean('Parameters', 'ibc')
    gateway = config.getboolean('Parameters', 'gateway') or ibc
    ibc = config.getboolean('Parameters', 'ibc')
    save_data = config.getboolean('Parameters', 'save_data')
    exts = config.get('Parameters', 'file_exts').split(',')
    
    main(framework, runtime, revtime, gateway, ibc, 
         algos=algos, save_data=save_data, file_exts=exts
    )