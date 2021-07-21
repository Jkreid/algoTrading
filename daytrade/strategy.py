# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 10:54:45 2020

@author: justi
"""

from pandas import Series, DataFrame
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_DOWN
import time as t

import utils
import eventkit

#//////////////////////////////////////////////////////////////////////////////

def logEvent(function):
    def logFunction(strategy, *args, **kwargs):
        event = function(strategy, *args, **kwargs)
        if strategy._logging:
            event.update({'strategy':f'{strategy.name}'})
            event.update({'class':f'{type(strategy).__name__}'})
            event_log = Series(event, name=utils.getDatetime())
            strategy._log = strategy._log.append(event_log)
    return logFunction

def logTrigger(function):
    def logFunction(strategy, *args, **kwargs):
        trig = function(strategy, *args, **kwargs)
        if strategy._logging:
            trig.update({'strategy':f'{strategy.name}'})
            trig.update({'class':f'{type(strategy).__name__}'})
            event = Series(trig, name=utils.getDatetime())
            strategy._log = strategy._log.append(event)
        return trig['triggered']
    return logFunction

#//////////////////////////////////////////////////////////////////////////////

class Strategy:
        
    def __init__(self, name, ib, manager,
                 runtime=0, logging=True, **kwargs):
        self.ib = ib
        self.name = name
        self.manager = manager
        self.runtime = runtime
        self._logging = logging
        self.trades = {}
        self._bad_ids = []
        self.entry_blocked = False
        
        if logging:
            self._log = DataFrame()
            self.ib._data_streams[f'{name}_results'] = lambda: self._log
        
        self._active = False
        self.orderIds = []
        self.orderErrorEvent = eventkit.Event()
        self.newOrderEvent = eventkit.Event()
        self.fillEvent = eventkit.Event()
        self.filledEvent = eventkit.Event()
        self.modifyEvent = eventkit.Event()
        self.cancelEvent = eventkit.Event()
        self.cancelledEvent = eventkit.Event()
        self.commissionReportEvent = eventkit.Event()
        self.ib.errorEvent += self._orderErrorEvent
        self.ib.newOrderEvent += self._newOrderEvent
    
    def getInputs(self, inputs={}):
        inputs.update({'strategy':type(self).__name__})
        return inputs
    
    @property
    def active(self):
        return self._active
    
    @active.setter
    def active(self, activate: bool):
        if activate:
            if not self.active:                
                self._active = True
                self._logActivationChange(True)
        else:
            if self.active:
                self._active = False
                self._logActivationChange(False)
                
    
    def stop_entry(self):
        self.entry_blocked = True
        self.wait_start = t.time()
    
    
    def placeOrder(self, contract, order):
        if order.orderId not in self.orderIds:
            self.orderIds.append(order.orderId)
            self.manager.processsOrderReq(contract, order, self)
    
    
    def openOrders(self):
        return list(map(
            lambda trade: trade.order, 
            filter(
                lambda trade: trade.orderStatus.status in trade.orderStatus.ActiveStates,
                self.trades.values()
            )
        ))
    
    def cancelOrder(self, order):
        if order.orderId not in self._bad_ids:
            try:
                self.ib.cancelOrder(order)
            except Exception as e:
                self._logOrderFailure(f'id - {order.orderId}: {e}')
                self._bad_ids.append(order.orderId)
    
    def openOrderCancel(self):
        for order in self.openOrders():
            self.cancelOrder(order)
    
    
    def _orderErrorEvent(self, reqId, errorCode, errorStr, contract):
        if reqId in self.orderIds:
            self._logOrderErrorEvent(reqId, errorCode, errorStr, contract)
            self.orderErrorEvent.emit(reqId, errorCode, errorStr, contract)
       
    
    @logEvent
    def _logOrderErrorEvent(self, reqId, errorCode, errorStr, contract):
        event = {'contract':contract.symbol} if contract else {}
        event.update({
            'Event'     : 'ORDER ERROR',
            'error'     : errorStr,
            'errorCode' : errorCode,
            'orderId'   : reqId,
        })
        return event
    
    
    def _newOrderEvent(self, trade):
        if trade.order.orderId in self.orderIds:
            self.trades[trade.order.orderId] = trade
            trade.fillEvent   += self._logFillEvent
            trade.fillEvent   += self.fillEvent.emit
            trade.filledEvent += self._logFilledEvent
            trade.filledEvent += self.filledEvent.emit
            trade.modifyEvent += self._logModifyEvent
            trade.modifyEvent += self.modifyEvent.emit
            trade.cancelEvent += self._logCancelEvent
            trade.cancelEvent += self.cancelEvent.emit
            trade.cancelledEvent += self._logCancelledEvent
            trade.cancelledEvent += self.cancelledEvent.emit
            trade.commissionReportEvent += self._logCommissionReportEvent
            trade.commissionReportEvent += self.commissionReportEvent.emit
            self._logNewOrderEvent(trade)
            self.newOrderEvent.emit(trade)

    
    def _tradeEvent(self, trade):
        event = {
            'contract'  : trade.contract.symbol,
            'orderId'   : trade.order.orderId,
            'action'    : trade.order.action,
            'orderType' : trade.order.orderType
        }
        if event['orderType'] == 'LMT':
            event.update({'lmtPrice' : trade.order.lmtPrice})
        elif event['orderType'] == 'STP':
            event.update({'auxPrice' : trade.order.auxPrice})
        if trade.order.parentId:
            event.update({'parentId' : trade.order.parentId})
        return event
    
    @logEvent    
    def _logNewOrderEvent(self, trade):
        event = self._tradeEvent(trade)
        event.update({'Event' : 'New Order'})
        return event
    
    @logEvent
    def _logModifyEvent(self, trade):
        event = self._tradeEvent(trade)
        event.update({'Event' : 'Modify Order'})
        return event
    
    @logEvent
    def _logFillEvent(self, trade, fill):
        event = self._tradeEvent(trade)
        event.update({'Event'       : 'Order Fill'})
        event.update({'time'        : utils.getDatetime(fill.time)})
        exe = fill.execution
        event.update({'price'       : exe.price})
        event.update({'shares'      : exe.shares})
        com = fill.commissionReport
        event.update({'commission'  : com.commission})
        event.update({'realizedPNL' : com.realizedPNL})
        return event
    
    @logEvent
    def _logCommissionReportEvent(self, trade, fill, commissionReport):
        event = self._tradeEvent(trade)
        event.update({'Event'       : 'Commission Report'})
        event.update({'time'        : utils.getDatetime(fill.time)})
        exe = fill.execution
        event.update({'price'       : exe.price})
        event.update({'shares'      : exe.shares})
        event.update({'commission'  : commissionReport.commission})
        event.update({'realizedPNL' : commissionReport.realizedPNL})
        return event
    
    @logEvent
    def _logFilledEvent(self, trade):
        event = self._tradeEvent(trade)
        event.update({'Event' : 'Order Filled'})
        return event
    
    @logEvent
    def _logCancelEvent(self, trade):
        event = self._tradeEvent(trade)
        event.update({'Event' : 'Order Cancel'})
        return event
    
    @logEvent
    def _logCancelledEvent(self, trade):
        event = self._tradeEvent(trade)
        event.update({'Event' : 'Order Cancelled'})
        return event
    
    @logEvent
    def _logActivationChange(self, active: bool):
        return {'Event' : f"{'A' if active else 'Dea'}ctivating"}
    
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
            'Event' : 'Order Failure', 
            'error' : exception
        }
    
    @logEvent
    def _logLogicError(self, msg='', **kwargs):
        kwargs.update({
            'Event' : 'LOGIC_ERROR', 
            'message': msg
        })
        return kwargs
    
    @logEvent
    def _logWarning(self, msg='', **kwargs):
        kwargs.update({
            'Event' : 'WARNING', 
            'message': msg
        })
        return kwargs
    


class SingleContractStrategy(Strategy):
            
    def __init__(self, *args, contract=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contract = contract
        self.increment = contract.increment
        self.position = 0
        self.fillEvent += self.updatePosition
    
    def getInputs(self, inputs={}):
        symbol = self.contract.symbol
        if self.contract.secType == 'CASH':
            symbol += 'USD'
        inputs.update({'contract':symbol})
        return super().getInputs(inputs)
    
    def updatePosition(self, trade, fill):
        if trade.order.action == 'BUY':
            self.position += fill.execution.shares
        else:
            self.position -= fill.execution.shares

    def round(self, x: float, up: bool=True):
        rnd = ROUND_HALF_UP if up else ROUND_HALF_DOWN
        denom = int(1/self.increment)
        return float(Decimal(x*denom).to_integral_value(rounding=rnd)/denom)
    
    def exitPosition(self, position=0):
        position = position or self.position
        if position:
            action = 'SELL' if position > 0 else 'BUY'
            self.placeOrder(
                self.contract, 
                self.ib.marketOrder(action, abs(position))
            )
    
    def resetExposure(self, position=0):
        self.openOrderCancel()
        self.exitPosition(position)
    
    @property
    def ibPosition(self):
        position = list(filter(
            lambda p: p.contract.conId == self.contract.conId,
            self.ib.positions()
        ))
        return position[0].position if position else 0
    
    def close_if_time(self):
        if ((self.wait_time >= 0) 
            and (t.time() > self.wait_time + self.wait_start)):
            self.resetExposure()
    
    
