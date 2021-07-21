# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 00:13:41 2020

@author: justi
"""
import asyncio
import subprocess
from ib_insync import IB, IBC
from ib_insync.util import dataclassAsDict, run, startLoop

class IBGW(IBC, IB):
    
    
    def __init__(self,
            tradingMode='paper',
            gateway=True,
            userid='',
            password='',
            version=972,
            mod=True,
            local=True,
            **kwargs
        ):
        
        self.port = {
            'paper': 4002 if gateway else 7497,
            'live' : 4001 if gateway else 7496
        }[tradingMode]
        
        IBC.__init__(
            self,
            version,
            userid=userid,
            password=password,
            gateway=gateway,
            tradingMode=tradingMode,
            **kwargs
        )
        if self._isWindows:
            asyncio.set_event_loop(asyncio.ProactorEventLoop())
        IB.__init__(self)
        
        self._gateway = gateway
        self.mod      = mod
        self.local = local
        
        self.connectedEvent += lambda: self.message_logger('IB Connected')
        self.disconnectedEvent += lambda: self.message_logger('IB Disconnected')
    
    def message_logger(self, msg: str) -> None:
        if self.local:
            print(msg)
        else:
            pass
    
    def connect(self, client_id=0, ip='127.0.0.1', notebook=False):
        if notebook:
            startLoop()
        return IB.connect(self, ip, self.port, client_id)
    
    def start(self):
        if self.mod:
            run(self.startAsyncMOD())
        else:
            run(self.startAsync())
    
    def terminate(self):
        if self.mod:
            run(self.terminateAsyncMOD())
        else:
            run(self.terminateAsync())
    
    def close(self):
        if self._isWindows:
            subprocess.call([
                'taskkill',
                '/F',
                '/IM', 'python.exe',
                '/T'
            ])
        else:
            exit()
    
    
    def begin(self, clientId=1):
        self.message_logger('starting')
        self.start()
        self.message_logger('started')
        
        self.message_logger('sleep')
        self.sleep(15)
        self.message_logger('awake')
        try:
            self.connect(clientId)
        except:
            self.message_logger('sleep')
            self.sleep(10)
            self.message_logger('awake')
            self.connect(clientId)
            
    def end(self):
        self.disconnect()
        self.sleep(3)
        self.terminate()
        self.message_logger('terminated')

    
    async def startAsyncMOD(self):
        if self._proc:
            return
        self._logger.info('Starting')

        # map from field names to cmd arguments; key=(UnixArg, WindowsArg)
        args = dict(
            twsVersion=('', ''),
            gateway=('--gateway', '/Gateway'),
            tradingMode=('--mode=', '/Mode:'),
            twsPath=('--tws-path=', '/TwsPath:'),
            twsSettingsPath=('--tws-settings-path=', ''),
            ibcPath=('--ibc-path=', '/IbcPath:'),
            ibcIni=('--ibc-ini=', '/Config:'),
            javaPath=('--java-path=', '/JavaPath:'),
            userid=('--user=', '/User:'),
            password=('--pw=', '/PW:'),
            fixuserid=('--fix-user=', '/FIXUser:'),
            fixpassword=('--fix-pw=', '/FIXPW:')
        )
        
        # create shell command
        if self._isWindows:
            ibcApp = 'StartGateway' if self._gateway else 'StartTWS'
            cmd = [f'{self.ibcPath}\\{ibcApp}.bat']
        else:
            ibcApp = 'gatewaystart' if self._gateway else 'twsstart'
            cmd = [f'{self.ibcPath}/{ibcApp}.sh']
        for k, v in dataclassAsDict(self).items():
            arg = args[k][self._isWindows]
            if v:
                if arg.endswith('=') or arg.endswith(':'):
                    cmd.append(f'{arg}{v}')
                elif arg:
                    cmd.append(arg)
                else:
                    cmd.append(str(v))
        # run shell command
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE)
        self._monitor = asyncio.ensure_future(self.monitorAsync())
        self.message_logger(f'proc_id = {self._proc.pid}')


    async def terminateAsyncMOD(self):
        if not self._proc:
            return
        self._logger.info('Terminating')
        if self._monitor:
            self._monitor.cancel()
            self._monitor = None
        
        if self._isWindows:
            subprocess.call([
                'taskkill',
                '/F',
                '/IM', 'java.exe',
                '/T'
            ])
        else:
            import contextlib
            with contextlib.suppress(ProcessLookupError):
                self._proc.terminate()
                await self._proc.wait()
        self._proc = None