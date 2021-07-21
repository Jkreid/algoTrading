# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 00:30:03 2020

@author: justi
"""

from typing     import NamedTuple
from ib_insync  import Order, MarketOrder, StopOrder, LimitOrder, PriceCondition

class MarketBracketOrder(NamedTuple):
    parent:     Order
    takeProfit: Order
    stopLoss:   Order
    
class MarketEntryBracketOrder(NamedTuple):
    parent: Order
    takeProfit: Order
    stopLoss:   Order
    
class RecursiveBracketOrder(NamedTuple):
    # a bracket order of recursive "if touched" bracket orders
    # good for spiking strategies
    pass
    
class OrderExtensions:
    
    """
    ///////////////////////////////////////////////////////////////////////////
    Order Methods
    ///////////////////////////////////////////////////////////////////////////
    """
    
    def marketOrder(self, action: str, quantity: float, **kwargs):
        return MarketOrder(
            action, quantity,
            orderId=self.client.getReqId(),
            **kwargs
        )
    
    def trailingStop(self, action: str, quantity: float, trailingPrice: float, **kwargs):
        return Order(
            action=action,
            totalQuantity=quantity,
            orderType='TRAIL',
            orderId=self.client.getReqId(),
            auxPrice=trailingPrice,
            **kwargs
        )
    
    def marketBracketOrder(
            self, action: str, quantity: float, conId, isMore, exch,
            takeProfitPrice: float,
            stopLossPrice: float, **kwargs) -> MarketBracketOrder:
        """
        Create a market order that is bracketed by a take-profit order
        and a stop-loss order.
        
        Args:
            action: 'BUY' or 'SELL'.
            quantity: size of order.
            takeProfitPrice: limit price of profit order.
            stopLossPrice: stop price of loss order.
        """ 
        assert action in ('BUY', 'SELL')
        reverseAction = 'BUY' if action == 'SELL' else 'SELL'
        parent        = MarketOrder(
                        action, quantity,
                        orderId=self.client.getReqId(),
                        transmit=False,
                        **kwargs
                        )
        
        # this should maybe be changed to a market if touched order 
        # incase price condition is finicky
        # https://interactivebrokers.github.io/tws-api/basic_orders.html#market_if_touched
        takeProfit    = MarketOrder(
                        reverseAction, quantity,
                        orderId=self.client.getReqId(),
                        transmit=False,
                        parentId=parent.orderId,
                        conditions=[PriceCondition(price=takeProfitPrice, conId=conId, isMore=isMore, exch=exch, triggerMethod=8)],
                        **kwargs
                        )
        stopLoss      = StopOrder(
                        reverseAction, quantity, stopLossPrice,
                        orderId=self.client.getReqId(),
                        transmit=True,
                        parentId=parent.orderId,
                        **kwargs
                        )
        return MarketBracketOrder(parent, takeProfit, stopLoss)
    
    
    def marketEntryBracketOrder(
            self, action: str, quantity: float,
            takeProfitPrice: float,
            stopLossPrice: float, **kwargs) -> MarketBracketOrder:
        """
        Create a market order that is bracketed by a take-profit order
        and a stop-loss order.
        
        Args:
            action: 'BUY' or 'SELL'.
            quantity: size of order.
            takeProfitPrice: limit price of profit order.
            stopLossPrice: stop price of loss order.
        """ 
        assert action in ('BUY', 'SELL')
        reverseAction = 'BUY' if action == 'SELL' else 'SELL'
        parent        = MarketOrder(
                        action, quantity,
                        orderId=self.client.getReqId(),
                        transmit=False,
                        **kwargs
                        )
        takeProfit    = LimitOrder(
                        reverseAction, quantity, takeProfitPrice,
                        orderId=self.client.getReqId(),
                        transmit=False,
                        parentId=parent.orderId,
                        **kwargs
                        )
        stopLoss      = StopOrder(
                        reverseAction, quantity, stopLossPrice,
                        orderId=self.client.getReqId(),
                        transmit=True,
                        parentId=parent.orderId,
                        **kwargs
                        )
        return MarketEntryBracketOrder(parent, takeProfit, stopLoss)