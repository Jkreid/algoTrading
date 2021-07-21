# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 00:32:38 2020

@author: justi
"""


import numpy as np
import matplotlib.pyplot as plt
from pandas import DataFrame, Series
from typing import Union, List, Tuple, Dict

def trueRange(
        candlesticks : DataFrame,
        bars_ago     : int
    ) -> float:
    
    bars_ago = min(bars_ago, candlesticks.shape[0])
    high = candlesticks.iloc[-bars_ago]['high']
    low  = candlesticks.iloc[-bars_ago]['low']
    try:
        prev_close = candlesticks.iloc[-(bars_ago+1)]['close']
    except IndexError: 
        prev_close = candlesticks.iloc[-bars_ago]['open']
    return max(high-low, abs(high-prev_close), abs(prev_close-low))


def getATR(
        candlesticks : DataFrame,
        window       : int,
        bars_ago     : int=0
    ) -> float:

    candlesticks = candlesticks.head(-bars_ago) if bars_ago else candlesticks
    n = min(window, candlesticks.shape[0])
    return sum(
        map(lambda x: trueRange(candlesticks, x), range(1,n+1))
    )/n if n else 0.0


def heikinAshiEquation(
        candlestick : Union[Series, Dict[str, float]],
        heikin_ashi : DataFrame=DataFrame()
    ) -> List[float]:
    
    def minMax(*args : List[float]) -> Tuple[float, float]:
        x = sorted(args)
        return x[0], x[-1]

    ha_close = (candlestick['open'] + candlestick['high'] + 
                candlestick['low']  + candlestick['close']
                )/4
    open_stick = heikin_ashi.iloc[-1] if heikin_ashi.size else candlestick
    ha_open = (open_stick['open'] + open_stick['close'])/2
    ha_low, ha_high = minMax(
        candlestick['high'],
        candlestick['low'],
        ha_open,
        ha_close
    )
    return [ha_close, ha_high, ha_low, ha_open]

def getHeikinAshiBar(
        candlestick : Union[Series, Dict[str, float]],
        heikin_ashi : DataFrame=DataFrame()
    ) -> List[float]:
    
    return {x:y for x,y in zip(
        ['close', 'high', 'low', 'open'],
        heikinAshiEquation(candlestick, heikin_ashi)
    )}


def getHeikinAshi(
        candlesticks : Union[DataFrame, Series],
        heikin_ashi  : DataFrame=DataFrame()
    ) -> DataFrame:
    """ Create Heikin-Ashi candlestick data from a given set of candlestick data 
        *called recursively for each candlestick (ndim = 1) in the given candlestick set """
        
    if candlesticks.ndim == 1:
        if not heikin_ashi.size:
            heikin_ashi = DataFrame(0.0, columns=sorted(candlesticks.index), index=[0])
            candle_lables = ['close', 'high', 'low', 'open']
            for s,v in zip(candle_lables, heikinAshiEquation(candlesticks)):
                heikin_ashi.iloc[0][s] = v
            return heikin_ashi
        else:
            heikin_ashi_data = heikinAshiEquation(candlesticks, heikin_ashi)
            return heikin_ashi.append(Series(
                heikin_ashi_data, 
                index = sorted(candlesticks.index), 
                name  = candlesticks.name
            ))
    else:
        for i in range(candlesticks.shape[0]):
            heikin_ashi = getHeikinAshi(candlesticks.iloc[i], heikin_ashi)
        return heikin_ashi


def candleColor(
        candlestick: Union[Series, Dict[str, float]]
    ) -> str: 
    """ Candlestick color (green or red) """
    
    op, cl = candlestick['open'], candlestick['close']
    return 'green' if cl > op else 'red' if cl < op else 'black'


def getColor(
        candlesticks : DataFrame, 
        moves_ago    : int=0
    ) -> str:
    
    try: 
        candlestick = candlesticks.iloc[-(1 + moves_ago)]
        color = candleColor(candlestick)
    except Exception as e:
        print(e)
        color = 'black'
    return color


def priceChange(
        candlesticks : DataFrame,
        move_start   : int=-1,
        move_end     : int=-1
    ) -> float:
    """ return the tick change from the start and end index of a move in \
        (where a single candlstick is 1 move) """
    
    return candlesticks.iloc[move_end]['close'] - candlesticks.iloc[move_start]['open']


def moveStatus(
        candlesticks  : DataFrame,
        move_size     : int=1,
        current_color : str='',
        moves_ago     : int=0
    ) -> Dict[str, Union[str, int, float]]:
    """ return move status dictionary: color, size, and price_change of current move """
    
    if moves_ago:
        candlesticks = candlesticks.head(-moves_ago)
    try:
        current_color  = current_color or getColor(candlesticks)
        previous_color = getColor(candlesticks, moves_ago=move_size)
    except:
        previous_color = 'none'
    if current_color == previous_color:
        try:
            return moveStatus(candlesticks,
                              move_size+1,
                              current_color=previous_color)
        except: pass
    return {'color'        : current_color, 
            'size'         : move_size, 
            'price_change' : priceChange(candlesticks, -(move_size), -1)
            }


def isSignalBar(
        candlesticks      : DataFrame,
        current_move_size : int=0,
        thresh            : int=4,
    ) -> Tuple[bool, str]:
    
    if not candlesticks.size:
        return False, 'none'
    elif candlesticks.shape[0] == 1:
        return False, getColor(candlesticks)
    else:
        move_status = moveStatus(candlesticks)
        move_size = current_move_size or move_status['size']
        move_color = move_status['color']
        if move_size == 1 and (move_color != 'black'):
            if moveStatus(candlesticks, moves_ago=1)['size'] >= thresh:
                return True, move_color
        return False, move_color
        

def moveHistory(
        candlesticks : DataFrame
    ) -> List[Dict[str, Union[str, int, float]]]:
    
    history = []
    total_moves = 0
    while total_moves < candlesticks.shape[0]:
        move = moveStatus(candlesticks, moves_ago=total_moves)
        total_moves += move['size']
        history.append(move)
    return list(reversed(history))


class MoveHistogram:
    
    all_   = {}
    colors = {'red':{}, 'green':{}, 'black':{}}
    
    def __init__(self,
                 candlesticks : DataFrame=DataFrame(), 
                 ticksPerBar  : int=0, 
                 move_history : List[Dict[str, Union[str, int, float]]]=[]
                 ) -> None:
        
        self.addHistory(move_history + moveHistory(candlesticks))
        self.ticksPerBar = ticksPerBar
    
    
    def addMove(self,
                move : Dict[str, Union[str, int, float]]
                ) -> None:
        
        if move['size'] in self.all_:
            self.all_[move['size']] += 1
        else:
            self.all_[move['size']]  = 1
        if move['size'] in self.colors[move['color']]:
            self.colors[move['color']][move['size']] += 1
        else:
            self.colors[move['color']][move['size']]  = 1
    
    
    def addHistory(self,
                   move_history : List[Dict[str, Union[str, int, float]]]
                   ) -> None:
        
        for move in move_history:
            self.addMove(move)
    
    
    def addCandleHistory(self,
                         candlesticks : DataFrame
                         ) -> None:
        
        self.addHistory(moveHistory(candlesticks))
    
    
    def getHistogram(self,
                      move_color : str=''
                      ) -> Dict[int, int]:
        
        if move_color in self.colors:
            return self.colors[move_color]
        else:
            return self.all_
        
        
    def get_list(self, move_color=''):
        move_size_list = []
        for move_size, count in self.getHistogram(move_color).items():
            move_size_list += count*[move_size]
        return np.array(move_size_list)
    
    
    def get_average(self, move_color=''):
        return self.get_list(move_color).mean()
    
    
    def std(self, move_color=''):
        return self.get_list(move_color).std()
    
    
    def get_stats(self, move_color=''):
        x = self.get_list(move_color)
        mu = x.mean()
        sig = x.std()
        return {'mean': mu, 'std': sig, 'ratio': mu/sig}
    
    
    def plot(self, move_color : str='', display_stats : bool=True):
        x = self.get_list(move_color)
        if display_stats:
            print(self.get_stats(move_color))
        plt.close()
        plt.hist(x, bins=range(1,max(x)+1))
        plt.show()
        