# -*- coding: utf-8 -*-
"""
Created on Thu Nov 26 11:07:18 2020

@author: justi
"""

import sys
import pandas as pd
from functools import reduce
import eventkit

import utils
from strategies import get_strategy
from strategy import logEvent


def get_framework(framework, *args, **kwargs):
    return utils.getModuleClasses(
        sys.modules[__name__], 
        lambda x,y: y.framework
    )[framework](*args, **kwargs)


class StrategyManager:   
    
    framework = 'base'
    
    def __init__(self, ib, *strategy_files, logging=True, sleep_time=1, **kwargs):
        
        self.ib = ib
        self.strategy_files = strategy_files
        self.contracts = {}
        self.pnlEvent = eventkit.Event()
        self.pnlEvent += self._logPnLEvent
        self.ib.pnlEvent += self.pnlEvent.emit
        self.name = 'manager'
        self.ticksPerEvent = []
        self.sleep_time = sleep_time
        
        self._logging = logging
        if logging:
            self._log = pd.DataFrame()
            self.ib._data_streams['manager_results'] = lambda: self._log
            self.ib._data_streams['master_results'] = lambda: self.log
        
        if not ib.isConnected():
            ib.connect(**kwargs)
        
        self.account = self.ib.managedAccounts()[0]
        self.loadStrategies()
        
    
    def loadStrategies(self):
        self.strategies = [self.loadStrategy(file, i+1) 
                           for i, file in enumerate(self.strategy_files)]
    
    @property
    def log(self):
        return reduce(
            lambda log1, log2: pd.concat([log1, log2], axis=0), 
            self.logs
        ).sort_index()
    
    @property
    def logs(self):
        return [s._log for s in (self.strategies + [self])]
    
    def save_inputs(self, save_dir):
        for s in self.strategies:
            save_name = f'{save_dir}/{s.name}.ini'
            utils.writeConfig(save_name, s.getInputs())
    

    def getContract(self, symbol):
        if symbol not in self.contracts:
            self.contracts[symbol] = utils.getContract(symbol, ib=self.ib)
        return self.contracts[symbol]


    def loadStrategy(self, file, strategy_id=0):
        strategy_params = utils.readConfig(file)
        strategy_name = strategy_params.pop('strategy')
        symbol = strategy_params.pop('contract')
        strategy = get_strategy(
            strategy_name,
            name=file.split('algos/')[-1].split('.ini')[0],
            ib=self.ib,
            manager=self,
            logging=self._logging,
            contract=self.getContract(symbol),
            **strategy_params
        )
        strategy.add_data_reqs()
        return strategy
    
    
    def stopStremaing(self):
        self.ib.cancelPnL(self.account)
        for contract in self.contracts.values():
            self.ib.cancelLiveTicks(contract)
    
    def startStreaming(self):
        self.ib.reqPnL(self.account)
        for contract in self.contracts.values():
            self.ib.reqLiveTicks(contract)
    
    def start_strategies(self, *strategies):
        strategies = strategies or self.strategies
        for s in strategies:
            s.start()
    
    def begin_strategy_shutdown(self, *strategies):
        strategies = strategies or self.strategies
        for s in strategies:
            s.stop_entry()
    
    def deactivate_closed_strategies(self, *strategies):
        strategies = strategies or self.strategies
        for s in filter(lambda s: s.active and not s.ib_open, strategies):
            s.stop()
    
    def close_expired_strategies(self, *strategies):
        strategies = strategies or self.strategies
        for s in filter(lambda s: s.ib_open, strategies):
            s.close_if_time()
        
    def shutdown_strategies(self, *strategies):
        strategies = strategies or self.strategies
        self.begin_strategy_shutdown()
        while any(s.ib_open for s in strategies):
            self.close_expired_strategies(*strategies)
            self.ib.sleep(self.sleep_time)
            self.deactivate_closed_strategies(*strategies)
        self.deactivate_closed_strategies(*strategies)
    
    def runStrategies(self, runtime, *strategies):
        # Can overwrite in subclasses
        strategies = strategies or self.strategies
        self.start_strategies(*strategies)
        self.ib.sleep(runtime)
        self.shutdown_strategies(*strategies)
    
    
    def run(self, runtime, revtime=0):
        self.startStreaming()
        self.ib.sleep(revtime)
        self.runStrategies(runtime)
        self.stopStremaing()
    
    
    def getPosition(self, contract):
        position = list(filter(
            lambda p: p.contract == contract,
            self.ib.positions()
        ))
        return position[0].position if position else 0
    
    
    def placeOrder(self, contract, order, strategy=None):
        try:
            self.ib.placeOrder(contract, order)
            (strategy or self)._logOrderPlacement(order)
        except Exception as e:
            (strategy or self)._logOrderFailure(str(e))
            return False
    
    def processsOrderReq(self, contract, order, strategy=None):
        self.placeOrder(contract, order, strategy)
        # Can overwrite in subclasses
    
    
    @logEvent
    def _logOrderPlacement(self, order):
        return {
            'Event'     : 'Order Placement',
            'orderId'   : order.orderId,
            'action'    : order.action,
            'orderType' : order.orderType
        }
    
    
    @logEvent
    def _logOrderFailure(self, exception):
        return {
            'Event'    : 'Order Failure', 
            'error'    : exception, 
        }
    
    
    @logEvent
    def _logErrorEvent(self, reqId, errorCode, errorStr, contract):
        event = {'contract':contract.symbol} if contract else {}
        event.update({
            'Event'     : 'ERROR',
            'error'     : errorStr,
            'errorCode' : errorCode,
            'orderId'   : reqId,
        })
        return event
    
    
    @logEvent
    def _logPnLEvent(self, pnl):
        return {
            'Event'         : 'PnL',
            'dailyPnL'      : pnl.dailyPnL,
            'unrealizedPnL' : pnl.unrealizedPnL,
            'realizedPnL'   : pnl.realizedPnL
        }



class ConcurrentFramework(StrategyManager):
    
    framework = 'concurrent'



class SequentialFramework(StrategyManager):
    
    framework = 'sequential'
    
    def runStrategies(self, runtime):
        for s in self.strategies:
            super().runStrategies(runtime, s)
    
    