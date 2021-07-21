# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 00:31:14 2020

@author: justi
"""
import sys

import utils
from strategy import logTrigger
from strategyxdata import ADXStrategy, SignalBarStrategy, FormingATRStrategy, FlagStrategy
from strategyxorders import BasicBracketStrategy, TTTSStrategy, MarketBracketStrategy

def get_strategy(class_name: str, *args, **kwargs):
    return utils.getModuleClasses(
        sys.modules[__name__]
    )[class_name](*args, **kwargs)

sign = lambda b: b*2 - 1

class Scalping(SignalBarStrategy, BasicBracketStrategy, FlagStrategy):
        
    def __init__(self, *args, 
                 target_buffer = 1,
                 failure_buffer = 1,
                 **kwargs):
        
        super().__init__(*args, **kwargs)
        self.target_buffer = int(target_buffer)
        self.failure_buffer = int(failure_buffer)
        self.action = None
        short_ma_filename = f'movingAverage_tickBarClose_{self.contract.symbol}_{self.ticksPerBar}tpb_window{self.short_term_ma}'
        self.ib._data_streams[short_ma_filename] = lambda: self.ib.tickBarMovingAverage(
            self.contract, self.ticksPerBar,
            self.short_term_ma, complete=True
        )
        long_ma_filename = f'movingAverage_tickBarClose_{self.contract.symbol}_{self.ticksPerBar}tpb_window{self.long_term_ma}'
        self.ib._data_streams[long_ma_filename] = lambda: self.ib.tickBarMovingAverage(
            self.contract, self.ticksPerBar,
            self.long_term_ma, complete=True
        )
        adx_slope_filename = f'ADXslope_{self.contract.symbol}_{self.ticksPerBar}tpb_adxWindow{self.long_term_ma}_slopeWindow{2}'
        self.ib._data_streams[adx_slope_filename] = lambda: self.ib.averageSlope(
            self.ib.tickBars[self.contract.symbol][self.ticksPerBar]['ADX'][self.ATR_window], 2,
            complete=True,
            alpha=self.ADX_slope_alpha
        )
    
    def getInputs(self, inputs={}):
        inputs.update({'target_buffer':self.target_buffer})
        inputs.update({'failure_buffer':self.failure_buffer})
        return super().getInputs(inputs)
    
    def add_data_reqs(self):
        super().add_data_reqs()
        self.ib.addATR(
            contract=self.contract,
            ticksPerBar = self.ticksPerBar,
            window = self.ATR_window
        )
        self.ib.addADX(
            contract=self.contract,
            ticksPerBar = self.ticksPerBar,
            window = self.ATR_window
        )
    
    
    def exit(self):
        self.resetExposure()
        self.ib.pendingTickersEvent -= self.newTicksEvent
    
    @logTrigger
    def checkEntryFailure(self, tickPrice, long):
        isTriggered = (tickPrice == self.entryFailure or
                       tickPrice < self.entryFailure == long)
        return {
            'Event'     : 'Entry Failure Check',
            'triggered' : isTriggered,
            'price'     : tickPrice,
            'fail point': self.entryFailure,
            'long trade': long
            }
    
    def setOrderDetails(self, signal_bar, long: bool):
        scale = sign(long)*self.tick_unit
        entryTarget       = signal_bar['high' if long else 'low'] + self.target_buffer*scale
        self.entryFailure = signal_bar['close'] - self.failure_buffer*scale
        entryTarget = self.round(entryTarget, up=long)
        takeProfitPrice   = entryTarget + self.profit_buffer*scale
        stopLossPrice     = entryTarget - self.loss_buffer*scale
        return {
            'limitPrice'      : entryTarget, 
            'takeProfitPrice' : takeProfitPrice,
            'stopLossPrice'   : stopLossPrice
        }
    

    def newTickBarEvent(self, contract, ticksPerBar, tickTime):
        
        @self.ib.tickBarEvent(contract, ticksPerBar)
        def scalpingNewBarUpdate(contract, ticksPerBar):
            self.calibrateStatus()
            if not self.open:
                is_signalBar, color, signal_bar = self.getSignalBar()
                if is_signalBar:
                    long = (color == 'green') != self.flip
                    self.action = 'PENDING_BUY' if long else 'PENDING_SELL'
                    if not (self.flagsTriggered or self.entry_blocked):
                        self.action = self.action[8:]
                        self.submit_entry_order(
                            long,
                            **self.setOrderDetails(signal_bar, long)
                        )
                        self.ib.pendingTickersEvent += self.newTicksEvent
                    else:
                        self.action = None
            elif any(order.orderId == self.entryOrder.orderId 
                       for order in self.openOrders()):
                self.exit()
                self.open = False
        
        return scalpingNewBarUpdate(contract, ticksPerBar)

    
    def newTicksEvent(self, tickers):
        
        @self.ib.tickersEvent(self.contract)
        def scalpingNewTickRun(tickPrice, tickTime):
            if any(order.orderId == self.entryOrder.orderId 
                       for order in self.openOrders()):
                tickPrice  = tickPrice['mid']
                long: bool = self.action == 'BUY'
                failureHit = self.checkEntryFailure(tickPrice, long)
                if self.flagsTriggered or failureHit:
                    self.exit()
            else:
                 self.exit()
        
        return scalpingNewTickRun(tickers)
        

#//////////////////////////////////////////////////////////////////////////////

class Scalping_v2(Scalping):
        
    def setOrderDetails(self, signal_bar, long: bool):
        if long:
            extrema       = 'high'
            other_extrema = 'low'
        else:
            extrema       = 'low'
            other_extrema = 'high'
        scale = sign(long)*self.tick_unit
        entryTarget       = signal_bar[extrema] + self.target_buffer*scale
        self.entryFailure = signal_bar['close'] - self.failure_buffer*scale
        entryTarget = self.round(entryTarget, long)
        takeProfitPrice = entryTarget + self.profit_buffer*scale
        takeProfitPrice = self.round(takeProfitPrice, long)
        new_loss_buffer = 0.5*abs(entryTarget - signal_bar[other_extrema])
        stopLossPrice = entryTarget - new_loss_buffer*sign(long)
        stopLossPrice = self.round(stopLossPrice, long)
        return {
            'limitPrice'      : entryTarget,
            'takeProfitPrice' : takeProfitPrice,
            'stopLossPrice'   : stopLossPrice
        }

#//////////////////////////////////////////////////////////////////////////////



class TrendScalping(ADXStrategy, BasicBracketStrategy):
        
    def __init__(self, *args,
                 target_buffer = 2,
                 failure_buffer = 2,
                 **kwargs):
        
        super().__init__(*args, **kwargs)
        self.target_buffer = int(target_buffer)
        self.failure_buffer = int(failure_buffer)
    
    def getInputs(self, inputs={}):
        inputs.update({'target_buffer':self.target_buffer})
        inputs.update({'failure_buffer':self.failure_buffer})
        return super().getInputs(inputs)
    
    
    def setOrderDetails(self, signal_bar, long: bool):
        scale = sign(long)*self.tick_unit
        entryTarget       = signal_bar['high' if long else 'low'] + self.target_buffer*scale
        self.entryFailure = signal_bar['close'] - self.failure_buffer*scale
        entryTarget = self.round(entryTarget, up=long)
        takeProfitPrice   = entryTarget + self.profit_buffer*scale
        stopLossPrice     = entryTarget - self.loss_buffer*scale
        return {
            'limitPrice'      : entryTarget, 
            'takeProfitPrice' : takeProfitPrice,
            'stopLossPrice'   : stopLossPrice
        }

    def newTickBarEvent(self, contract, ticksPerBar, tickTime):
        
        @self.ib.tickBarEvent(contract, ticksPerBar)
        def trendingNewBarUpdate(contract, ticksPerBar):
            self.calibrateStatus()
            if not self.open:
                shouldEnter, long = self.shouldEnter
                if shouldEnter and not self.entry_blocked:
                    bar = self.ha_bars.iloc[-1]
                    self.submit_entry_order(
                        long,
                        **self.setOrderDetails(bar, long)
                    )
        
        return trendingNewBarUpdate(contract, ticksPerBar)

#//////////////////////////////////////////////////////////////////////////////


class Trending(TTTSStrategy, ADXStrategy):
    
    def newTickBarEvent(self, contract, ticksPerBar, tickTime):
        
        @self.ib.tickBarEvent(contract, ticksPerBar)
        def trendingNewBarUpdate(contract, ticksPerBar):
            self.calibrateStatus()
            if not self.open:
                shouldEnter, long = self.shouldEnter
                if shouldEnter and not self.entry_blocked:
                    self.submit_entry_order(long)
            else:
                if self.position and self.shouldExit:
                    self.submit_exit_order()
        
        return trendingNewBarUpdate(contract, ticksPerBar)

    
#//////////////////////////////////////////////////////////////////////////////


class Spiking(FormingATRStrategy, MarketBracketStrategy):
            
    def setOrderDetails(self, tickPrice, long: bool):
        scale = sign(long)*self.tick_unit
        return {
            'isMore': long,
            'exch' : self.contract.exchange,
            'conId' : self.contract.conId,
            'takeProfitPrice' : self.round(tickPrice + scale*self.profit_buffer, up=long),
            'stopLossPrice'   : self.round(tickPrice - scale*self.loss_buffer, up=long)
        }
    
    def newTicksEvent(self, tickers):
        
        @self.ib.tickersEvent(self.contract)
        def spikingNewTicksRun(tickPrice, tickTime):
            tickPrice = tickPrice['mid']
            self.calibrateStatus()
            if not self.open:
                shouldEnter, long = self.shouldEnter
                if shouldEnter and not self.entry_blocked:
                    self.submit_entry_order(
                        long,
                        **self.setOrderDetails(tickPrice, long)
                    )
        
        return spikingNewTicksRun(tickers)

#//////////////////////////////////////////////////////////////////////////////
