# -*- coding: utf-8 -*-
"""
Created on Fri Oct 30 02:39:16 2020

@author: justi
"""

import candles
import strategy

class TickStrategy(strategy.SingleContractStrategy):
    
    def getInputs(self, inputs={}):
        return super().getInputs(inputs)
    
    def start(self):
        self.active = True
        self.ib.pendingTickersEvent += self.newTicksEvent
    
    def stop(self):
        self.ib.pendingTickersEvent -= self.newTicksEvent
        self.active = False


class BarStrategy(strategy.SingleContractStrategy):
    
    def __init__(self,
                 *args,
                 ticksperbar=250,
                 **kwargs):
        
        super().__init__(*args, **kwargs)
        self.ticksPerBar = int(ticksperbar)

    def getInputs(self, inputs={}):
        inputs.update({'ticksperbar':self.ticksPerBar})
        return super().getInputs(inputs)
    
    def add_data_reqs(self):
        self.ib.addTickBars(
            contract = self.contract,
            ticksPerBar = self.ticksPerBar
        )
    
    def start(self):
        self.active = True
        self.ib.newTickBarEvent += self._logNewTickBarEvent
        self.ib.newTickBarEvent += self.newTickBarEvent
    
    
    def stop(self):
        self.ib.newTickBarEvent -= self._logNewTickBarEvent
        self.ib.newTickBarEvent -= self.newTickBarEvent
        self.active = False
    
    @property
    def bars(self):
        return self.ib.tickBars[self.contract.symbol][self.ticksPerBar]['raw']
    
    @property
    def current_bar(self):
        return self.ib.currentBar[self.contract.symbol][self.ticksPerBar]['raw']
    
    @property
    def ha_bars(self):
        return self.ib.tickBars[self.contract.symbol][self.ticksPerBar]['smooth']
    
    @property
    def current_ha_bar(self):
        return self.ib.currentBar[self.contract.symbol][self.ticksPerBar]['smooth']
    
    
    def getBarData(self, *args):
        data = self.ib.tickBars[self.contract.symbol][self.ticksPerBar]
        for arg in args:
            data = data[arg]
        return data
    
    @strategy.logEvent
    def _logNewTickBarEvent(self, *args, **kwargs):
        return {
            'Event'    : 'New Bar',
            'color'    : candles.getColor(self.bars),
            'ha_color' : candles.getColor(self.ha_bars),
            'open'     : self.bars.iloc[-1]['open'],
            'close'    : self.bars.iloc[-1]['close'],
            'high'     : self.bars.iloc[-1]['high'],
            'low'      : self.bars.iloc[-1]['low'],
            'ha_open'  : self.ha_bars.iloc[-1]['open'],
            'ha_close' : self.ha_bars.iloc[-1]['close'],
            'ha_high'  : self.ha_bars.iloc[-1]['high'],
            'ha_low'   : self.ha_bars.iloc[-1]['low']
        }


class FormingATRStrategy(TickStrategy):
    
    def __init__(self, *args, 
                 window=14, 
                 atr_thresh=1, 
                 atr_slope_thresh=1, 
                 move_thresh=1,
                 ticksperbar=250,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.window = int(window)
        self.ATR_thresh = float(atr_thresh)
        self.ATR_slope_thresh = float(atr_slope_thresh)
        self.move_thresh = int(move_thresh)
        self.ticksPerBar = float(ticksperbar)
    
    def getInputs(self, inputs={}):
        inputs.update({'window':self.window})
        inputs.update({'atr_thresh':self.ATR_thresh})
        inputs.update({'atr_slope_thresh':self.ATR_slope_thresh})
        inputs.update({'move_thresh':self.move_thresh})
        inputs.update({'ticksperbar':self.ticksPerBar})
        return super().getInputs(inputs)
    
    def add_data_reqs(self):
        self.ib.addTickBars(
            contract = self.contract,
            ticksPerBar = self.ticksPerBar,
            ATR_windows = [self.window]
        )
        
    @property
    def shouldEnter(self):
        symbol = self.contract.symbol
        window = self.window
        ticksPerBar = self.ticksPerBar
        tickBars = self.ib.tickBars[symbol][ticksPerBar]
        ATR_forming = self.ib.getFormingATR(self.contract, ticksPerBar, window)
        ATR_slope = self.ib.getFormingATR_slope(self.contract, ticksPerBar, window)
        move_status = candles.moveStatus(tickBars['smooth'])
        should_enter = (
            (ATR_forming > self.ATR_thresh) 
            and (ATR_slope > self.ATR_slope_thresh) 
            and (move_status['size'] > self.move_thresh) 
            and (move_status['color'] == candles.candleColor(
                    self.ib.currentBar[symbol][ticksPerBar]['raw']
                ))
            and (move_status['color'] != 'black')
        )
        return should_enter, move_status['color'] == 'green' != self.flip
    
    
    
class ADXStrategy(BarStrategy):

    def __init__(self, *args, window=14, slope_window=1,
                 adx_threshold=20, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = int(window)
        self.slope_window = int(slope_window)
        self.adx_threshold = float(adx_threshold)
        adx_slope_filename = f'ADXslope_{self.contract.symbol}_{self.ticksPerBar}tpb_adxWindow{window}_slopeWindow{slope_window}'
        self.ib._data_streams[adx_slope_filename] = lambda: self.ib.averageSlope(
            self.getBarData('ADX', self.window), self.slope_window,
            complete=True
        )
        self.adx_data = {}
    
    def getInputs(self, inputs={}):
        inputs.update({'window':self.window})
        inputs.update({'slope_window':self.slope_window})
        inputs.update({'adx_threshold':self.adx_threshold})
        return super().getInputs(inputs)
    
    def start(self):
        self.active = True
        self.ib.newTickBarEvent += self._logNewTickBarEvent
        self.ib.newTickBarEvent += self.ADXEvent
        self.ib.newTickBarEvent += self.newTickBarEvent
        
    
    def stop(self):
        self.ib.newTickBarEvent -= self._logNewTickBarEvent
        self.ib.newTickBarEvent -= self.ADXEvent
        self.ib.newTickBarEvent -= self.newTickBarEvent
        self.active = False
    
    def add_data_reqs(self):
        BarStrategy.add_data_reqs(self)
        self.ib.addADX(
            contract=self.contract,
            ticksPerBar = self.ticksPerBar,
            window = self.window
        )
    
    def ADXEvent(self, *args, **kwargs):
        self.adx_data = self.getADXData()
        self._logADXEvent()
    
    def getADXData(self):
        # get indicator values
        adx = self.getBarData('ADX', self.window)
        adx_now = adx.iloc[-1] if adx.size else 0
        adx_slope = self.ib.averageSlope(
        adx, self.slope_window
        )#alpha=self.ADX_slope_alpha)
        dmi = self.getBarData('DMI', self.window, 'DI')
        dmi_plus = dmi['plus'].iloc[-1] if dmi['plus'].size else 0
        dmi_minus = dmi['minus'].iloc[-1] if dmi['minus'].size else 0
        return {
            'ADX' : adx_now, 
            'ADX Slope' : adx_slope, 
            'DI+' : dmi_plus, 
            'DI-' : dmi_minus
        }

    @property
    def shouldEnter(self):
        adx_now = self.adx_data['ADX']
        adx_slope = self.adx_data['ADX Slope']
        dmi_plus = self.adx_data['DI+']
        dmi_minus = self.adx_data['DI-']
        
        valid_adx = (adx_now > self.adx_threshold) and (adx_slope > 0)
        equal_dmi = dmi_plus == dmi_minus
        long = dmi_plus > dmi_minus != self.flip
        goodColor = (
            (candles.getColor(self.ha_bars) == 'green') 
            == (dmi_plus > dmi_minus)
        )
        is_valid_entry = valid_adx and (not equal_dmi) and goodColor
        return is_valid_entry, long

    @property
    def shouldExit(self):
        return self.ib.averageSlope(
            self.getBarData('ADX', self.window),
            self.slope_window
        ) <= 0
    
    @strategy.logEvent
    def _logADXEvent(self):
        event_data = {
            'Event': 'ADX Bar',
            'ticksPerBar':self.ticksPerBar,
            'contract':self.contract.symbol,
            'window':self.window,
            'ADX Threshold': self.adx_threshold
        }
        event_data.update(self.adx_data)
        return event_data



class SignalBarStrategy(BarStrategy):
    
    def __init__(self, *args, signal_thresh=3, **kwargs):
        super().__init__(*args, **kwargs)
        self.signal_thresh = int(signal_thresh)
    
    def getInputs(self, inputs={}):
        inputs.update({'signal_thresh':self.signal_thresh})
        return super().getInputs(inputs)
    
    def getSignalBar(self):
        bar = self.ha_bars.iloc[-1]
        is_signalBar, bar_color = candles.isSignalBar(
                self.ha_bars,
                current_move_size = None,
                thresh = self.signal_thresh
            )
        if is_signalBar:
            self._logSignalBarEvent(bar_color, bar)
        return is_signalBar, bar_color, bar
    
    @strategy.logEvent
    def _logSignalBarEvent(self, in_color, bar):
        return {
            'Event'   : 'Signal Bar',
            'ha_color': in_color,
            'ha_open' : bar['open'],
            'ha_close': bar['close'],
            'ha_high' : bar['high'],
            'ha_low'  : bar['low']
            }

#//////////////////////////////////////////////////////////////////////////////

@strategy.logTrigger
def ATR_flag(strat):
    ticksPerBar = strat.ticksPerBar
    window      = strat.ATR_window
    ATR_now     = strat.ib.getFormingATR(strat.contract, ticksPerBar, window)
    atr_min, atr_max = strat.ATR_range
    if strat.ignore_ATR:
        isTriggered = False
    else:
        isTriggered = not (atr_min <= ATR_now <= atr_max)
    return {
        'Event'      : 'ATR Range FlagCheck',
        'symbol'     : strat.contract.symbol,
        'ticksPerBar': ticksPerBar,
        'ATR window' : window,
        'triggered'  : isTriggered,
        'ATR'        : ATR_now,
        'ATR Min'    : atr_min,
        'ATR Max'    : atr_max,
        'ignored'    : strat.ignore_ATR
    }

@strategy.logTrigger
def ADX_flag(strat):
    symbol        = strat.contract.symbol
    ticksPerBar   = strat.ticksPerBar
    window        = strat.ATR_window
    ADX_threshold = strat.ADX_threshold
    if not strat.ib.tickBars[symbol][ticksPerBar]['ADX'][window].size:
        ADX = None
        isTriggered = True
    else:
        ADX = strat.ib.tickBars[symbol][ticksPerBar]['ADX'][window].iloc[-1]
        if strat.ignore_ADX:
            isTriggered = False
        else:
            isTriggered = (ADX < ADX_threshold)
    return {
        'Event'       : 'ADX FlagCheck',
        'symbol'      : symbol,
        'ticksPerBar' : ticksPerBar,
        'ADX window'  : window,
        'triggered'   : isTriggered,
        'ADX'         : ADX,
        'ADX Min'     : ADX_threshold,
        'ignored'     : strat.ignore_ADX
    }

@strategy.logTrigger
def ADX_slope_flag(strat):
        
    symbol       = strat.contract.symbol
    ticksPerBar  = strat.ticksPerBar
    window       = strat.ATR_window
    slope_window = strat.ADX_slope_window
    alpha        = strat.ADX_slope_alpha
    adx = strat.ib.tickBars[symbol][ticksPerBar]['ADX'][window]
    
    if adx.size < 2:
        ADX_slope   = None
        isTriggered = True
    else:
        ADX_slope = strat.ib.averageSlope(
            adx, slope_window,
            alpha=strat.ADX_slope_alpha
        )
        if strat.ignore_ADX_slope:
            isTriggered = False
        else:
            isTriggered = (ADX_slope < 0)
    
    return {
        'Event'           : 'ADX Slope FlagCheck',
        'symbol'          : symbol,
        'ticksPerBar'     : ticksPerBar,
        'ADX window'      : window,
        'ADX slope window': slope_window,
        'alpha'           : alpha,
        'triggered'       : isTriggered,
        'ADX_slope'       : ADX_slope,
        'ignored'         : strat.ignore_ADX_slope
    }

@strategy.logTrigger
def DMI_flag(strat):
    symbol        = strat.contract.symbol
    ticksPerBar   = strat.ticksPerBar
    window        = strat.ATR_window
    plus_DMI = strat.ib.tickBars[symbol][ticksPerBar]['DMI'][window]['DI']['plus'].iloc[-1]
    minus_DMI = strat.ib.tickBars[symbol][ticksPerBar]['DMI'][window]['DI']['minus'].iloc[-1]
    if strat.ignore_DMI:
        isTriggered = False
    else:
        isTriggered = ('BUY' in strat.action) != (plus_DMI > minus_DMI)
    return {
        'Event'       : 'DMI FlagCheck',
        'symbol'      : symbol,
        'ticksPerBar' : ticksPerBar,
        'DMI window'  : window,
        'triggered'   : isTriggered,
        'plus_DMI'    : plus_DMI,
        'minus_DMI'   : minus_DMI,
        'ignored'     : strat.ignore_DMI
    }


def movingAvg_flags(strat):
    short_ma = strat.ib.tickBarMovingAverage(
        strat.contract,
        strat.ticksPerBar,
        strat.short_term_ma,
        complete=True
    )
    old_short_ma, new_short_ma = short_ma.values[-2:]
    short_slope = strat.ib.averageSlope(short_ma, 1)
    
    @strategy.logTrigger
    def flatMA(strat):
        flat_min, flat_max = strat.maFlatRange
        if strat.ignore_flatMA:
            isTriggered = False
        else:
            isTriggered = flat_min <= short_slope <= flat_max
        return {
            'Event'          : 'Flat Moving Average FlagCheck',
            'symbol'         : strat.contract.symbol,
            'ticksPerBar'    : strat.ticksPerBar,
            'short MA window': strat.short_term_ma,
            'triggered'      : isTriggered,
            'slope'          : short_slope,
            'slope min'      : flat_min,
            'slope max'      : flat_max,
            'ignored'        : strat.ignore_flatMA
        }
    
    @strategy.logTrigger
    def momentumSlopeMA(strat):
        if strat.ignore_slopeMA:
            isTriggered = False
        else:
            isTriggered = ('BUY' in strat.action) != (short_slope > 0)
        return {
            'Event'          : 'Momentum Moving Average FlagCheck',
            'symbol'         : strat.contract.symbol,
            'ticksPerBar'    : strat.ticksPerBar,
            'short MA window': strat.short_term_ma,
            'triggered'      : isTriggered,
            'slope'          : short_slope,
            'side'           : strat.action,
            'ignored'        : strat.ignore_slopeMA
            }
        
    
    
    @strategy.logTrigger
    def crossingMA(strat):
        long_ma  = strat.ib.tickBarMovingAverage(
            strat.contract,
            strat.ticksPerBar,
            strat.long_term_ma
        )
        if strat.ignore_crossMA:
            isTriggered = False
        else:
            isTriggered = ('BUY' in strat.action) != (long_ma > new_short_ma)
        return {
            'Event'          : 'Moving Average Mean Reversion FlagCheck',
            'symbol'         : strat.contract.symbol,
            'ticksPerBar'    : strat.ticksPerBar,
            'short MA window': strat.short_term_ma,
            'long MA window' : strat.long_term_ma,
            'triggered'      : isTriggered,
            'long MA'        : long_ma,
            'short MA'       : new_short_ma,
            'side'           : strat.action,
            'ignored'        : strat.ignore_crossMA
            }
    
    return any(flag(strat) for flag in (flatMA, momentumSlopeMA, crossingMA))


class FlagStrategy(strategy.SingleContractStrategy):
    
    def __init__(self, *args, 
            atr_range        = '0,0', 
            atr_window       = 14,
            window_1         = 7,
            window_2         = 14,
            mashortflatrange = '0,0',
            adx_threshold    = 50,
            adx_slope_window = 3,
            adx_slope_alpha  = 0.1,
            ignore_atr       = True,
            ignore_flatma    = True,
            ignore_slopema   = True,
            ignore_crossma   = True,
            ignore_adx       = True,
            ignore_dmi       = True,
            ignore_adx_slope = True,
            **kwargs):
        
        super().__init__(*args, **kwargs)
        self.ATR_range        = tuple(map(float, atr_range.split(',')))
        self.ATR_window       = int(atr_window)
        self.ADX_slope_window = int(adx_slope_window)
        self.ADX_slope_alpha  = float(adx_slope_alpha)     
        window_1 = int(window_1)
        window_2 = int(window_2)
        self.long_term_ma     = max(window_1, window_2)
        self.short_term_ma    = min(window_1, window_2)
        self.maFlatRange      = tuple(map(float, mashortflatrange.split(',')))
        self.ADX_threshold    = float(adx_threshold)
        self.ignore_ATR       = bool(int(ignore_atr))
        self.ignore_flatMA    = bool(int(ignore_flatma))
        self.ignore_slopeMA   = bool(int(ignore_slopema))
        self.ignore_crossMA   = bool(int(ignore_crossma))
        self.ignore_ADX       = bool(int(ignore_adx))
        self.ignore_ADX_slope = bool(int(ignore_dmi))
        self.ignore_DMI       = bool(int(ignore_adx_slope))
        self.flags = [ATR_flag,
                      movingAvg_flags,
                      ADX_flag,
                      DMI_flag,
                      ADX_slope_flag
                      ]    
    
    def getInputs(self, inputs={}):
        inputs.update({'atr_range':','.join(map(str,self.ATR_range))})
        inputs.update({'atr_window':self.ATR_window})
        inputs.update({'window_1':self.long_term_ma})
        inputs.update({'window_2':self.short_term_ma})
        inputs.update({'mashortflatrange':','.join(map(str,self.maFlatRange))})
        inputs.update({'adx_threshold':self.ADX_threshold})
        inputs.update({'adx_slope_window':self.ADX_slope_window})
        inputs.update({'adx_slope_alpha':self.ADX_slope_alpha})
        inputs.update({'ignore_atr':int(self.ignore_ATR)})
        inputs.update({'ignore_flatma':int(self.ignore_flatMA)})
        inputs.update({'ignore_slopema':int(self.ignore_slopeMA)})
        inputs.update({'ignore_crossma':int(self.ignore_crossMA)})
        inputs.update({'ignore_adx':int(self.ignore_ADX)})
        inputs.update({'ignore_dmi':int(self.ignore_DMI)})
        inputs.update({'ignore_adx_slope':int(self.ignore_ADX_slope)})
        return super().getInputs(inputs)
    
    @property
    def flagsTriggered(self):
        triggers = [flag(self) for flag in self.flags]
        return any(triggers)
    


