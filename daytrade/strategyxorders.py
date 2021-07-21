# -*- coding: utf-8 -*-
"""
Created on Fri Oct 30 02:42:01 2020

@author: justi
"""

import strategy

class OpenCloseStrategy(strategy.SingleContractStrategy):
    
    def __init__(self, *args, quantity=0, wait_time=0, flip=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.quantity = int(quantity)
        self.wait_time = float(wait_time)
        self.flip = bool(int(flip))
        self._open = False
    
    def getInputs(self, inputs={}):
        inputs.update({'quantity':self.quantity})
        inputs.update({'wait_time':self.wait_time})
        inputs.update({'flip':int(self.flip)})
        return super().getInputs(inputs)

    @strategy.logEvent
    def _logStateChange(self, is_open):
        return {'Event' : 'State Change', 'is_open' : is_open}
    
    def processOpenState(self, set_open, open_state=0):
        if open_state:
            if open_state % 2:
                # logic error
                self._logLogicError(f'double setting open_state: "{set_open}"')
            else:
                # logic warning
                self._logWarning(f'open_state: "{set_open}" does not align with ib truth')
                self._open = set_open
                self._logStateChange(self._open)
        else:
            self._open = set_open
            self._logStateChange(self._open)
    
    @property
    def open(self):
        return self._open

    
    @property
    def ib_open(self):
        return bool(self.position or self.openOrders())
    
    @property
    def open_syncd(self):
        ib_tru = self.ib_open
        synced = ib_tru == self.open
        return synced, self.open, ib_tru
    
    @open.setter
    def open(self, set_open):
        synced, now_open, tru_open = self.open_syncd
        if set_open == now_open:
            open_state = 1
        else:
            if synced:
                open_state = 2
            else:
                open_state = 0
        self.processOpenState(set_open, open_state)


class BracketStrategy(OpenCloseStrategy):
    
    
    def __init__(self, *args, bracket_order_type='basic', **kwargs):
        super().__init__(*args, **kwargs)
        self.newOrderEvent += self.setOpen
        self.filledEvent += self.setClose
        self.bracketOrderFunction = {
            'basic':self.ib.bracketOrder,
            'market':self.ib.marketBracketOrder,
            'marketEntry':self.ib.marketEntryBracketOrder
        }[bracket_order_type]
        
    
    def calibrateStatus(self):
        synced, now_open, ib_open = self.open_syncd
        if not synced:
            if ib_open:
                if all(order in self.orders
                       for order in self.openOrders()):
                    self.open = True
                else:
                    self.resetExposure()
            else:
                self.open = False
      
    def submit_entry_order(self, long: bool, **order_details):
        order_details.update({
            'action'   : 'BUY' if long else 'SELL', 
            'quantity' : self.quantity
        })
        self.orders = self.bracketOrderFunction(**order_details)
        self.entryOrder, self.targetOrder, self.lossOrder = self.orders
        for order in self.orders:
            self.placeOrder(self.contract, order)
    
    def setOpen(self, trade):
        order_id = trade.order.orderId
        if order_id == self.entryOrder.orderId:
            self.open = True
        elif order_id not in (self.targetOrder.orderId, self.lossOrder.orderId):
            self._logLogicError(f'New Order: "{order_id}" is not a currently tracked Entry order')
    
    def setClose(self, trade):
        order_id = trade.order.orderId
        if order_id in (self.targetOrder.orderId, self.lossOrder.orderId):
            self.open = False
        elif order_id != self.entryOrder.orderId:
            self._logLogicError(f'Filled Order: "{order_id}" is not a currently tracked Exit order')

class TickScaledBracketStrategy(BracketStrategy):
    
    def __init__(self, *args, 
                 tick_scale       = 1,
                 profit_buffer    = 2,
                 loss_buffer      = 2,
                 **kwargs):
        
        super().__init__(*args, **kwargs)
        self.loss_buffer = int(loss_buffer)
        self.profit_buffer = int(profit_buffer)
        self._tick_scale = int(tick_scale)
        self.tick_unit = self._tick_scale*self.increment
    
    def getInputs(self, inputs={}):
        inputs.update({'tick_scale':self._tick_scale})
        inputs.update({'profit_buffer':self.profit_buffer})
        inputs.update({'loss_buffer':int(self.loss_buffer)})
        return super().getInputs(inputs)


BasicBracketStrategy = TickScaledBracketStrategy


class MarketBracketStrategy(TickScaledBracketStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, bracket_order_type='market', **kwargs)


class MarketEntryBracketStrategy(TickScaledBracketStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, bracket_order_type='marketEntry', **kwargs)
        


    
class TriggeredTargetTrailStopStrategy(OpenCloseStrategy):
    
    ocaNumber = 0
    
    def __init__(self, *args, trailticks=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailScale = int(trailticks)
        self.newOrderEvent += self.setOpen
        self.filledEvent += self.setClose
        self.cancelEvent += self.setClose
        self.cancelledEvent += self.setClose
    
    def getInputs(self, inputs={}):
        inputs.update({'trailticks':self.trailScale})
        return super().getInputs(inputs)

    
    def setOpen(self, trade):
        order_id = trade.order.orderId
        if not self.open:
            if order_id == self.entryMarket.orderId:
                self.open = True
                self.placeOrder(self.contract, self.stopOrder)

    
    def setClose(self, trade):
        order_id = trade.order.orderId
        if self.open:
            if order_id in (self.exitMarket.orderId, self.stopOrder.orderId):
                self.open = False
    
    
    def submit_entry_order(self, long: bool):
        self.ocaNumber += 1
        action = 'BUY' if long else 'SELL'
        reverseAction = 'BUY' if action == 'SELL' else 'SELL'
        self.entryMarket = self.ib.marketOrder(action, self.quantity)
        self.stopOrder = self.ib.trailingStop(
            reverseAction, self.quantity, self.increment*self.trailScale
        )
        self.exitMarket = self.ib.marketOrder(reverseAction, self.quantity)
        self.ib.oneCancelsAll([self.stopOrder, self.exitMarket], f'exit-orders-{self.name}-{self.ocaNumber}', 1)
        self.placeOrder(self.contract, self.entryMarket)
    
    
    def submit_exit_order(self):
        self.placeOrder(self.contract, self.exitMarket)
    
    def calibrateStatus(self):
        orders = self.openOrders()
        position = self.position
        ib_open = bool(orders or position)
        synced = ib_open == self.open
        if not synced:
            if ib_open:
                if ((orders and position) 
                    and (len(orders) == 1) 
                    and ((orders[0].action == 'BUY') == (position < 0))):
                    # in a valid open state
                    self.open = True
                else:
                    # invalid open state, closing
                    self.resetExposure()
            else:
                self.open = False

    
TTTSStrategy = TriggeredTargetTrailStopStrategy