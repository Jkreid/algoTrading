# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 00:34:37 2020

@author: justi
"""

import numpy
import datetime
import configparser
import inspect
from ib_insync import Future, Forex, Contract


def getDatetime(time: datetime.datetime = None) -> numpy.datetime64:
    time = time or datetime.datetime.utcnow()
    return numpy.datetime64(time).astype('datetime64[ns]')

def getModuleClasses(module, identifier=lambda x,y: x):
    return {
        identifier(name, cls_obj) : cls_obj
        for name, cls_obj in inspect.getmembers(module, inspect.isclass) 
        if cls_obj.__module__ == module.__name__
    }

def readConfig(configfile, field='Parameters'):
    config = configparser.ConfigParser()
    config.read(configfile)
    return dict(config.items(field))

def writeConfig(configfile, data, field='Parameters'):
    config = configparser.ConfigParser()
    config[field] = data
    with open(configfile, 'w') as file:
        config.write(file)
    

def getContract(symbol, ib=None, **kwargs):
    symbol = symbol.upper()
    if symbol == 'ES':
        contract = Future('ES', **kwargs)
    elif symbol in ('EURUSD'):
        contract = Forex(symbol, **kwargs)
    else:
        contract = Contract(symbol, **kwargs)
    
    if ib and ib.isConnected():
        contract = ib.reqContractDetails(contract)[0].contract
        contract.increment = ib.reqMarketRule(
            ib.reqContractDetails(contract)[0].marketRuleIds.split(',')[0]
        )[0].increment
    
    return contract
