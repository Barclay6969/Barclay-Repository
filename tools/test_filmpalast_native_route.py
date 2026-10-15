#!/usr/bin/env python3
"""Regression checks for routing FilmPalast TMDb native movie callbacks."""
import ast
import base64
import json
import os
from pathlib import Path
import sys
import types
import urllib.parse

source = Path('addons/plugin.video.filmpalast.ex/default.py').read_text(encoding='utf-8')
module = ast.parse(source, filename='default.py')
main_node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
unit = compile(ast.Module(body=[main_node], type_ignores=[]), '<filmpalast-main>', 'exec')

def run_case(mode, url='', resolved_url=None):
    calls = []
    original = sys.modules.get('tmdb_native')
    dummy = types.ModuleType('tmdb_native')
    dummy.native_direct_url = lambda params: calls.append(('scope', params.get('tmdb'))) or resolved_url
    sys.modules['tmdb_native'] = dummy
    namespace = {
        'sys':types.SimpleNamespace(argv=['plugin://plugin.video.filmpalast.ex', '3',
                                        '?mode='+str(mode)]),
        'urllib':urllib, 'base64':base64, 'json':json, 'os':os,
        'xbmcaddon':types.SimpleNamespace(Addon=lambda id:types.SimpleNamespace(getAddonInfo=lambda x:'/test/addon')),
        'ensure_temp_dir':lambda:calls.append(('init',)),
        'get_params':lambda:{'mode':str(mode), 'url':urllib.parse.quote_plus(url),
                             'tmdb':'843843', 'title':'Suddenly'},
        'START':lambda:calls.append(('START',)),
        'INDEX':lambda u:calls.append(('INDEX',u)),
        'CATEGORIES':lambda u:calls.append(('CATEGORIES',u)),
        'ALPHA':lambda:calls.append(('ALPHA',)),
        'SEARCH':lambda u:calls.append(('SEARCH',u)),
        'TMDBSEARCH':lambda p:calls.append(('TMDBSEARCH',)),
        'PLAYVIDEO':lambda u:calls.append(('PLAYVIDEO',u)),
        'pluginhandle':3, 'DEBUG':True,
        'xbmc':types.SimpleNamespace(log=lambda *args:calls.append(('log',)),
                                     executebuiltin=lambda x:calls.append(('execute', x)),
                                     LOGWARNING=2,LOGINFO=1),
        'xbmcgui':types.SimpleNamespace(ListItem=lambda: object()),
        'xbmcplugin':types.SimpleNamespace(
            endOfDirectory=lambda *args,**kwargs:calls.append(('end',)),
            setResolvedUrl=lambda *args:calls.append(('failed_resolve',))),
    }
    try:
        exec(unit, namespace)
        namespace['main']()
    finally:
        if original is None:
            sys.modules.pop('tmdb_native',None)
        else:
            sys.modules['tmdb_native'] = original
    return calls

stream='https://filmpalast.to/stream/suddenly-uberleben-im-eis'
case=run_case(31, resolved_url=stream)
assert ('scope','843843') in case and ('PLAYVIDEO',stream) in case, case
assert ('START',) not in case, case
print('PASS mode=31 with missing URL resolves exact selected film')

case=run_case(31)
assert any(x[0]=='failed_resolve' for x in case) and ('START',) not in case, case
print('PASS expired scope exits without trying another movie')

case=run_case(30, url=stream)
assert ('START',) not in case, case
assert any(x[0]=='end' for x in case), case
assert any(x[0]=='execute' and 'tmdb_info_launcher.py' in x[1] for x in case), case
first_end=next(i for i,x in enumerate(case) if x[0]=='end')
first_launch=next(i for i,x in enumerate(case) if x[0]=='execute')
assert first_end < first_launch, case
assert len([x for x in case if x[0]=='end']) == 1, case
print('PASS mode=30 completes Kodi directory before queuing info launcher')

case=run_case(10, url=stream)
assert ('PLAYVIDEO',stream) in case and ('START',) not in case, case
print('PASS regular mode=10 playback unchanged')
