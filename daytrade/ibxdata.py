# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 01:09:59 2020

@author: justi
"""

import os
from datetime import datetime
from pandas import Series, DataFrame

import eventkit
import candles


def get_smoothed_value(values: Series, new_value: float, window=14):
    if values.size:
        window = min(window, values.size+1)
        return (values.iloc[-1]*(window-1) + new_value)/window
    else:
        return new_value


def movingAverage(values: Series,
                  window=0,
                  steps_back=0,
                  complete=False,
                  **kwargs):
    
    if values.empty:
        return 0
    
    if steps_back:
        values = values.head(-steps_back)

    window = min(values.size, window) if window > 0 else values.size
    if window > 1:
        if kwargs:
            seed = Series(
                [values.head(x+1).ewm(**kwargs).mean().iloc[-1]
                 for x in range(window)
                 ],
                index = values.index[:window]
            )
            moving_average = values.rolling(window).apply(
                lambda x: x.tail(window).ewm(**kwargs).mean().iloc[-1]
            ).fillna(value=seed)            
        else:
            seed = Series(
                [values.head(x+1).mean() for x in range(window)],
                index = values.index[:window]
            )
            moving_average = values.rolling(window).mean().fillna(value=seed)
        return moving_average if complete else moving_average.iloc[-1]
    else:
        return values if complete else values.iloc[-1]


def averageSlope(values: Series,
                 window,
                 steps_back=0,
                 complete=False,
                 **kwargs):
    
    return movingAverage(
        values.diff().dropna(),
        window=window,
        steps_back=steps_back,
        complete=complete,
        **kwargs
    )


class DataExtensions:
    
    prices          = {}
    tickBars        = {}
    currentBar      = {}
    newTickBarEvent = eventkit.Event()
    DMI_started     = False
    ADX_started     = False
    _data_streams   = {}
    
    
    def save_data(self, dirname, file_ext='csv'):
        failures = [
            self.write_data(data_func, dirname, filename, file_ext)
            for filename, data_func in self._data_streams.items()
        ]
        return any(failures)
    
    def save_run_data(self, *file_exts):
        date_dir = datetime.now().strftime('%Y/%m/%d/%H_%M_%p')
        savedir = './data'
        for dir_ in date_dir.split('/'):
            savedir += f'/{dir_}'
            if not os.path.exists(savedir):
                os.mkdir(savedir)
        for file_ext in file_exts:
            if self.save_data(savedir, file_ext):
                print(f'Error saving {file_ext} files')
        return savedir

    def write_data(self, data_func, dirname, filename, file_ext):
        savename = f'{dirname}/{filename}.{file_ext}'
        try:
            data = data_func()
            if file_ext == 'csv':
                data.to_csv(savename)
            elif file_ext == 'xlsx':
                data.to_excel(savename)
            else:
                raise NameError(f'File type extension: {file_ext}, is not valid!')
            return False
        except Exception as e:
            print(f'Data Saving Error for {filename}.{file_ext}: {e}')
            return True
    
    @staticmethod
    def tickBarEvent(contract, ticksPerBar):
        def newTickBarEvent(function):
            def tickBarFunction(contract, ticksPerBar, *args, **kwargs):
                if contract == contract and ticksPerBar == ticksPerBar:
                    return function(contract, ticksPerBar, *args, **kwargs)
            return tickBarFunction
        return newTickBarEvent
    
    
    """
    ///////////////////////////////////////////////////////////////////////////
    Data Transformations
    ///////////////////////////////////////////////////////////////////////////
    """
    
    @staticmethod
    def get_smoothed_value(values: Series, new_value: float, window=14):
        return get_smoothed_value(values, new_value, window=window)
    
    
    @staticmethod
    def movingAverage(values: Series,
                      window=0,
                      steps_back=0,
                      complete=False,
                      **kwargs):
        
        return movingAverage(values,
                      window=window,
                      steps_back=steps_back,
                      complete=complete,
                      **kwargs)
    
    
    @staticmethod
    def averageSlope(values: Series,
                     window,
                     steps_back=0,
                     complete=False,
                     **kwargs):
        
        return averageSlope(values,
                     window,
                     steps_back=steps_back,
                     complete=complete,
                     **kwargs)
        
    """
    ///////////////////////////////////////////////////////////////////////////
    TickByTick Price methods
    ///////////////////////////////////////////////////////////////////////////
    """

    def addTickPrices(self, contract):
        """ Add contract of that symbol to series of prices being stored"""
        self.prices[contract.symbol] = DataFrame()
        
        def updatePrices(tickers, contract):
            symbol = contract.symbol
            @self.tickersEvent(contract)
            def setPrice(tickPrice, tickTime):
                self.prices[symbol] = self.prices[symbol].append(
                    Series(tickPrice, name=tickTime)
                )
            
            return setPrice(tickers)
        
        self.pendingTickersEvent += updatePrices

        self._data_streams[f'tickPrices_{contract.symbol}'] = lambda: self.prices[contract.symbol]

    """
    ///////////////////////////////////////////////////////////////////////////
    TickByTick Bar methods
    ///////////////////////////////////////////////////////////////////////////
    """
    
    def addTickBars(self, contract, ticksPerBar=250, ATR_windows=[], priceType='mid'):
        """ Add tickBars for a specific symbol and ticksPerBar to pendingTickersEvent"""
        symbol = contract.symbol
        if symbol not in self.tickBars:
            self.tickBars[symbol]   = {}
            self.currentBar[symbol] = {}
        if ticksPerBar not in self.tickBars[symbol]:
            self.tickBars[symbol][ticksPerBar]   = {
                'raw'   :DataFrame(), 
                'smooth':DataFrame(), 
                'ATR'   :{},
                'STR'   :{},
                'DMI'   :{},
                'ADX'   :{}
            }
            self.currentBar[symbol][ticksPerBar] = {'raw': {}, 'smooth': {}}
        for window in ATR_windows:
            self.addATR(contract, ticksPerBar, window)
        
        def barUpdater(tickers):
            """ Function added to pendingTickersEvent that updates the tickBars and current Tickbar"""
            tickBars = self.tickBars[symbol][ticksPerBar]
            bar   = self.currentBar[symbol][ticksPerBar]['raw']
            
            @self.tickersEvent(contract)
            def updateBar(tickPrice, tickTime):
                tickPrice = tickPrice[priceType]
                newBar = False
                if (not bar) or (bar['ticks'] == ticksPerBar):
                    bar['open']  = tickPrice
                    bar['high']  = tickPrice
                    bar['low']   = tickPrice
                    bar['ticks'] = 1
                else:
                    bar['low']    = min(bar['low'] , tickPrice)
                    bar['high']   = max(bar['high'], tickPrice)
                    bar['ticks'] += 1
                bar['close'] = tickPrice
                hkbar = candles.getHeikinAshiBar(bar, tickBars['smooth'])
                hkbar['ticks'] = bar['ticks']
                if bar['ticks'] == ticksPerBar:
                    tickBars['raw'] = tickBars['raw'].append(Series(bar, name=tickTime))
                    tickBars['smooth'] = tickBars['smooth'].append(Series(hkbar, name=tickTime))
                    newBar = True
                self._updateFormingTickBarIndicators(symbol, ticksPerBar, bar, tickTime)
                return (newBar, tickTime)
            
            for isNewBar, barTime in updateBar(tickers):
                if isNewBar:
                    self.newTickBarEvent.emit(contract, ticksPerBar, barTime)
            
        self.pendingTickersEvent += barUpdater

        self._data_streams[f'rawBars_{symbol}_{ticksPerBar}tpb'] = lambda: self.tickBars[symbol][ticksPerBar]['raw']
        self._data_streams[f'HaBars_{symbol}_{ticksPerBar}tpb']  = lambda: self.tickBars[symbol][ticksPerBar]['smooth']

    
    """
    ///////////////////////////////////////////////////////////////////////////
    Indicator methods
    ///////////////////////////////////////////////////////////////////////////
    """
    
    def _updateFormingTickBarIndicators(self, symbol, ticksPerBar, bar, tickTime):
        self.updateATR(symbol, ticksPerBar, bar, tickTime)
    
    
    def tickBarMovingAverage(self, contract, ticksPerBar, window,
                             steps_back=0, complete=False, **kwargs):
        if self.tickBars[contract.symbol][ticksPerBar]['raw'].empty:
            values = Series(dtype=float)
        else:
            values = self.tickBars[contract.symbol][ticksPerBar]['raw']['close']
        return self.movingAverage(values, window,
                             steps_back=steps_back,
                             complete=complete, 
                             **kwargs
                             )
        
    
    def tickMovingAverage(self, contract, window,
                          steps_back=0, complete=False, priceType='mid', **kwargs):
        if self.prices[contract.symbol].empty:
            values = Series(dtype=float)
        else:
            values = self.prices[contract.symbol][priceType]
        return self.movingAverage(values, window,
                             steps_back=steps_back,
                             complete=complete,
                             **kwargs
                             )

   
    def addATR(self, contract, ticksPerBar, window):
        symbol = contract.symbol
        self.tickBars[symbol][ticksPerBar]['ATR'][window] = tickbars = {
            'formed' :{
                'values':Series(dtype=float),
                'slopes':Series(dtype=float)
            },
            'forming':{
                'values':Series(dtype=float),
                'slopes':Series(dtype=float)
            }
        }
        
        for bar_state, data in tickbars.items():
            for derivative, values in data.items():
                def getValues():
                    return self.tickBars[symbol][ticksPerBar]['ATR'][window][bar_state][derivative]
                data_name = f'ATR_{derivative}_{bar_state}_{symbol}_{ticksPerBar}tpb_window{window}'
                self._data_streams[data_name] = getValues
    
    
    def updateATR(self, symbol, ticksPerBar, bar, tickTime):
        
        def _formingATR(window, bars, formingTR, atrData, r, tickTime):
            formedATRs = atrData['formed']['values']
            avgTrueRange = formedATRs.iloc[-1] if formedATRs.size else 0
            if bars.shape[0] > window:
                removedRange = candles.trueRange(bars, window + int(r))
                newATR = avgTrueRange + r*(formingTR - removedRange)/window
            else:
                window = bars.shape[0]
                newATR = (avgTrueRange*window + r*formingTR)/(window + r)
            atrData['forming']['values'].at[tickTime] = newATR
            if r == 1.0:
                formedATRs.at[tickTime] = newATR
            _formingSlope(atrData, r, tickTime)
                
        def _formingSlope(atrData, r, tickTime):
            formedATRs = atrData['formed']['values']
            ATR_forming = atrData['forming']['values'].iloc[-1]
            ATR_new_formed = formedATRs.iloc[-1] if formedATRs.size else 0
            ATR_old_formed = formedATRs.iloc[-2] if formedATRs.size > 1 else 0
            if r == 1.0:
                ATR_slope = ATR_new_formed - ATR_old_formed
                atrData['forming']['slopes'].at[tickTime] = ATR_slope
                atrData['formed']['slopes'].at[tickTime] = ATR_slope
            else:
                ATR_slope = r*(ATR_forming - ATR_new_formed) + (1-r)*(ATR_new_formed - ATR_old_formed)
                atrData['forming']['slopes'].at[tickTime] = ATR_slope
        
        def _updateATRs(symbol, ticksPerBar, bar, tickTime):
            aTRs = self.tickBars[symbol][ticksPerBar]['ATR'].items()
            if aTRs:
                bars = self.tickBars[symbol][ticksPerBar]['raw']
                r    = bar['ticks']/ticksPerBar
                if r == 1.0:
                    forming_TR = candles.trueRange(bars, 1)
                else:
                    prev_close = bars.iloc[-1]['close'] if bars.size else bar['open']
                    forming_TR = max(bar['high']-bar['low'], 
                                     abs(prev_close-bar['high']), 
                                     abs(prev_close-bar['low'])
                                     )
                
                for window, ATR_data in aTRs:
                    _formingATR(window, bars, forming_TR, ATR_data, r, tickTime)
        
        _updateATRs(symbol, ticksPerBar, bar, tickTime)
    
    
    def getATR_values(self, contract, ticksPerBar, window,forming=True, slope=False, steps_back=0, complete=False):
        atrs = self.tickBars[contract.symbol][ticksPerBar]['ATR'][window][
            'forming' if forming else 'formed'
        ]['slopes' if slope else 'values']
        if steps_back:
            atrs = atrs.head(-steps_back)
        return atrs if complete else atrs.iloc[-1]
    
    def getFormingATR(self, contract, ticksPerBar, window, steps_back=0, complete=False):
        return self.getATR_values(
            contract, ticksPerBar, window,
            forming=True, slope=False,
            steps_back=steps_back, complete=complete
        )
    
    def getFormedATR(self, contract, ticksPerBar, window, steps_back=0, complete=False):
        return self.getATR_values(
            contract, ticksPerBar, window,
            forming=False, slope=False,
            steps_back=steps_back, complete=complete
        )
    
    def getFormingATR_slope(self, contract, ticksPerBar, window, steps_back=0, complete=False):
        return self.getATR_values(
            contract, ticksPerBar, window,
            forming=True, slope=True,
            steps_back=steps_back, complete=complete
        )
    
    def getFormedATR_slope(self, contract, ticksPerBar, window, steps_back=0, complete=False):
        return self.getATR_values(
            contract, ticksPerBar, window,
            forming=False, slope=True,
            steps_back=steps_back, complete=complete
        )
    
    
    def addDMI(self, contract, ticksPerBar, window):
        symbol = contract.symbol
        self.tickBars[symbol][ticksPerBar]['STR'][window] = Series(dtype=float)
        self.tickBars[symbol][ticksPerBar]['DMI'][window] = {
            'DM':{
                'plus' :Series(dtype=float),
                'minus':Series(dtype=float)
            },
            'DI':{
                'plus' :Series(dtype=float),
                'minus':Series(dtype=float)
            }
        }
        if not self.DMI_started:
            self.startDMI()
        
        str_    = f'STR_{symbol}_{ticksPerBar}tpb_window{window}'
        dmplus  = f'DMplus_{symbol}_{ticksPerBar}tpb_window{window}'
        dmminus = f'DMminus_{symbol}_{ticksPerBar}tpb_window{window}'
        diplus  = f'DIplus_{symbol}_{ticksPerBar}tpb_window{window}'
        diminus = f'DIminus_{symbol}_{ticksPerBar}tpb_window{window}'
        
        self._data_streams[str_]    = lambda: self.tickBars[symbol][ticksPerBar]['STR'][window]
        self._data_streams[dmplus]  = lambda: self.tickBars[symbol][ticksPerBar]['DMI'][window]['DM']['plus']
        self._data_streams[dmminus] = lambda: self.tickBars[symbol][ticksPerBar]['DMI'][window]['DM']['minus']
        self._data_streams[diplus]  = lambda: self.tickBars[symbol][ticksPerBar]['DMI'][window]['DI']['plus']
        self._data_streams[diminus] = lambda: self.tickBars[symbol][ticksPerBar]['DMI'][window]['DI']['minus']

    def startDMI(self):
        
        def updateSTR(contract, ticksPerBar, barTime, *args, **kwargs):
            symbol = contract.symbol
            if self.tickBars[symbol][ticksPerBar]['raw'].shape[0] > 1:
                sTRs  = self.tickBars[symbol][ticksPerBar]['STR']
                newTR = candles.trueRange(self.tickBars[symbol][ticksPerBar]['raw'], 1)
                for window, values in sTRs.items():
                    sTRs[window].at[barTime] = self.get_smoothed_value(
                        values,
                        newTR,
                        window
                    )

        def updateDMI(contract, ticksPerBar, barTime, *args, **kwargs):
            symbol = contract.symbol
            bars = self.tickBars[symbol][ticksPerBar]['raw']
            if bars.shape[0] > 1:
                [[prev_high, prev_low],[current_high, current_low]] = bars[['high','low']].iloc[-2:].values
                DM_plus = max(current_high - prev_high, 0)
                DM_minus = max(prev_low - current_low, 0)
                if DM_plus > DM_minus:
                    	DM_minus = 0
                elif DM_minus > DM_plus:
                    	DM_plus = 0
                else:
                    	DM_minus = DM_plus = 0
                for window, DMI in self.tickBars[symbol][ticksPerBar]['DMI'].items():
                    smoothDM_plus  = self.get_smoothed_value(DMI['DM']['plus'], DM_plus, window)
                    smoothDM_minus = self.get_smoothed_value(DMI['DM']['minus'], DM_minus, window)
                    smoothTR = self.tickBars[symbol][ticksPerBar]['STR'][window].iloc[-1]
                    DI_plus  = 100*smoothDM_plus/smoothTR
                    DI_minus = 100*smoothDM_minus/smoothTR
                    DMI['DM']['plus'].at[barTime]  = smoothDM_plus
                    DMI['DM']['minus'].at[barTime] = smoothDM_minus
                    DMI['DI']['plus'].at[barTime]  = DI_plus
                    DMI['DI']['minus'].at[barTime] = DI_minus
                    
        self.newTickBarEvent += updateSTR
        self.newTickBarEvent += updateDMI
        self.DMI_started = True
        

    def addADX(self, contract, ticksPerBar, window):
        symbol = contract.symbol
        if window not in self.tickBars[symbol][ticksPerBar]['STR']:
            self.addDMI(contract, ticksPerBar, window)
        self.tickBars[symbol][ticksPerBar]['ADX'][window] = Series(dtype=float)
        self.startADX()
        
        self._data_streams[f'ADX_{symbol}_{ticksPerBar}tpb_window{window}'] = lambda: self.tickBars[symbol][ticksPerBar]['ADX'][window]
        
    
    
    def startADX(self):
        
        def updateADX(contract, ticksPerBar, barTime, *args, **kwargs):
            symbol = contract.symbol
            if self.tickBars[symbol][ticksPerBar]['raw'].shape[0] > 1:
                ADXs = self.tickBars[symbol][ticksPerBar]['ADX']
                for window, values in ADXs.items():
                    dmi = self.tickBars[symbol][ticksPerBar]['DMI'][window]['DI']
                    if dmi['plus'].size >= window:
                        di_plus  = dmi['plus'].iloc[-1]
                        di_minus = dmi['minus'].iloc[-1]
                        dx = 100*abs(di_plus - di_minus)/abs(di_plus + di_minus)
                        ADXs[window].at[barTime] = self.get_smoothed_value(values, dx, window)
        
        if not self.DMI_started:
            self.startDMI()
        if not self.ADX_started:
            self.newTickBarEvent += updateADX
            self.ADX_started = True