# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 10:54:47 2020

@author: justi
"""
import utils
from ib import IBGW
from ibxdata import DataExtensions
from ibxorders import OrderExtensions


class LiveTrader(IBGW, DataExtensions, OrderExtensions):
    
    streaming_ticks = []
    
    """
    ///////////////////////////////////////////////////////////////////////////
    Live Data Methods
    ///////////////////////////////////////////////////////////////////////////
    """
    
    @staticmethod
    def tickersEvent(contract=None, contracts=[]):
        def newTickersEvent(function):
            def tickersFunction(tickers, *args, **kwargs):
                def transform_tick(tick):
                    tick = tick.tickByTicks[0]
                    mid  = (tick.askPrice*tick.askSize + tick.bidPrice*tick.bidSize)/(tick.askSize + tick.bidSize)
                    return {
                        'ask':tick.askPrice,
                        'bid':tick.bidPrice,
                        'mid':mid
                    }
                return [
                    function(
                        transform_tick(tick), # tickPrices (ask, bid, mid)
                        utils.getDatetime(tick.time), # tickTime
                        *args, 
                        **kwargs
                    ) for tick in tickers 
                    if tick.contract == contract or tick.contract in contracts
                ]
            return tickersFunction
        return newTickersEvent
    
    
    
    def reqLiveTicks(self, contract):
        """ Requesting real time tick price updates """
        if contract not in self.streaming_ticks:
            self.streaming_ticks.append(contract)
            self.reqTickByTickData(contract, 'BidAsk')

    
    def cancelLiveTicks(self, contract): 
        """ Cancel all updates requiring tickByTick data for the given Contract"""
        if contract in self.streaming_ticks:
            self.streaming_ticks.remove(contract)
            self.cancelTickByTickData(contract, 'BidAsk')
