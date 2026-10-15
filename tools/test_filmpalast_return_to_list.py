#!/usr/bin/env python3
"""Simulate FilmPalast's Android navigation return before the TMDb info dialog."""
import ast
import json
import sys
import time
import types
from pathlib import Path

source = Path('addons/plugin.video.filmpalast.ex/service.py').read_text(encoding='utf-8')
module = ast.parse(source, filename='service.py')
function = next(x for x in module.body if isinstance(x, ast.FunctionDef)
                and x.name == 'consume_info_request')
code = compile(ast.Module(body=[function], type_ignores=[]), 'service.py', 'exec')

class FakeWindow:
    def __init__(self, initial):
        self.props={'filmpalast.barclay.native_info_queue_0611':json.dumps(initial)}
    def getProperty(self,name): return self.props.get(name,'')
    def setProperty(self,name,value): self.props[name]=value
    def clearProperty(self,name): self.props.pop(name,None)

folder={'value':'plugin://plugin.video.filmpalast.ex/?url=movie&mode=30'}
calls=[]
current_time={'value':101.5}
fake_mod=types.ModuleType('tmdb_native')
fake_mod.open_tmdb_info=lambda url,params:calls.append(('info',url))
original=sys.modules.get('tmdb_native')
sys.modules['tmdb_native']=fake_mod
ns={
    'INFO_QUEUE_KEY':'filmpalast.barclay.native_info_queue_0611',
    'json':json,
    'time':types.SimpleNamespace(time=lambda:current_time['value']),
    'xbmc':types.SimpleNamespace(
        getInfoLabel=lambda name:folder['value'],
        executebuiltin=lambda command:calls.append(('action',command)),
        LOGWARNING=2,LOGERROR=3),
    'kodi_idle':lambda:True,
    'log':lambda *args,**kwargs:calls.append(('log',args[0])),
    'traceback':types.SimpleNamespace(format_exc=lambda:'test')
}
try:
    exec(code,ns)
    win=FakeWindow({'url':'https://filmpalast.to/stream/suddenly-uberleben-im-eis',
                    'params':{'title':'Suddenly'},'issued':100})
    assert ns['consume_info_request'](win) is False
    assert ('action','Action(Back)') in calls, calls
    assert not any(c[0]=='info' for c in calls), calls
    state=json.loads(win.getProperty(ns['INFO_QUEUE_KEY']))
    assert state['navigation_restored'] and state['return_issued']==101.5
    print('PASS virtual film folder: one Back action scheduled before TMDb Info')

    current_time['value']=101.9
    folder['value']='plugin://plugin.video.filmpalast.ex/?url=movies&mode=1'
    assert ns['consume_info_request'](win) is False
    assert not any(c[0]=='info' for c in calls)
    current_time['value']=102.2
    assert ns['consume_info_request'](win) is True
    assert ('info','https://filmpalast.to/stream/suddenly-uberleben-im-eis') in calls
    assert sum(c[0]=='action' for c in calls)==1
    assert not win.getProperty(ns['INFO_QUEUE_KEY'])
    print('PASS TMDb Info appears after parent movie list restored; queue consumed')

    calls.clear()
    win=FakeWindow({'url':'https://filmpalast.to/stream/nirgendwo-2023',
                    'params':{'title':'Nirgendwo'},'issued':100})
    folder['value']='plugin://unrelated.video/?mode=1'
    current_time['value']=105
    assert ns['consume_info_request'](win) is True
    assert not any(c[0]=='action' for c in calls)
    print('PASS unrelated Kodi folder: no blind Back action')

finally:
    if original is None: sys.modules.pop('tmdb_native',None)
    else: sys.modules['tmdb_native']=original
