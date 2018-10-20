import gevent
import gevent.monkey as mky; mky.patch_all()
import bottle as btl
import bottle.ext.websocket as wbs
import os
import sys
import socket
import traceback
import eel.browsers as browsers
import pkg_resources as pkg
import random
import json

_default_options = {
    'mode': 'chrome-app',
    'host': 'localhost',
    'port': 8000,
    'chromeFlags': []
}

class MessageEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SocketResponse):
            return {
                '_type' : obj._type,
                'ID' : obj.ID,
                'Value' : obj.Value,
                'Error' : obj.Error,
                'ErrorMessage' : obj.ErrorMessage
            }
        elif isinstance(obj, SocketCommand):
            return {
                '_type' : obj._type,
                'ID' : obj.ID,
                'Function' : obj.Function,
                'Parameters' : obj.Parameters
            }
        return json.JSONEncoder.default(obj)

class MessageDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)
    
    def object_hook(self, obj):
        if '_type' in obj:
            if obj['_type'] == 'Command':
                return SocketCommand.FromJSON(obj)
            elif obj['_type'] == 'Response':
                return SocketResponse.FromJSON(obj)
            else: raise ValueError('Cannot parse object with _type of {}'.format(obj['_type']))
        return obj

class SocketCommand:
    _type = 'Command'
    def __init__(self, function):
        self.ID = '{}|{}'.format(function, random.random())
        self.Function = function
        self.Parameters = []

    @classmethod
    def FromJSON(cls, obj):
        command = SocketCommand(obj['Function'])
        command.ID = obj['ID']
        command.Parameters = obj['Parameters']
        return command
    
class SocketResponse:
    _type = 'Response'
    def __init__(self, id):
        self.ID = id
        self.Value = None
        self.Error = False
        self.ErrorMessage = ''
    
    @classmethod
    def FromJSON(cls, obj):
        response = SocketResponse(obj['ID'])
        response.Value = obj.get('Value')
        response.Error = obj.get('Error')
        response.ErrorMessage = obj.get('ErrorMessage')
        return response

class eel:
    RootWebDir = None
    ExposedFunctions = {}
    OpenSocket = None
    Callbacks = {}
    CallReturnValues = {}

    def __init__(self, rootWebDir):
        if eel.RootWebDir is not None:
            raise ValueError('Don\'t make two eels')
        eel.RootWebDir = rootWebDir

    def __getattr__(self, name):
        return lambda *args : eel.callClientFunction(name, *args)

    @staticmethod
    def callClientFunction(function, *args):
        command = SocketCommand(function)
        command.Parameters = args
        eel._send(json.dumps(command, cls = MessageEncoder))
        def callBackHandler(callback = None):
            if callback is not None:
                eel.Callbacks[command.ID] = callback
            else:
                for _ in range(10000):
                    if command.ID in eel.CallReturnValues:
                        return eel.CallReturnValues.pop(call_id)
                    gevent.sleep(0.001)
        return callBackHandler  

    @staticmethod
    def start(url, **kwargs):
        block = kwargs.pop('block', True)
        options = kwargs.pop('options', {})
        size = kwargs.pop('size', None)
        position = kwargs.pop('position', None)
        geometry = kwargs.pop('geometry', {})
        _on_close_callback = kwargs.pop('callback', None)

        for k, v in list(_default_options.items()):
            if k not in options:
                options[k] = v

        if options['port'] == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', 0))
            options['port'] = sock.getsockname()[1]
            sock.close()

        browsers.open([url], options)
        btl.run(host = options['host'],
                port = options['port'],
                server = wbs.GeventWebSocketServer,
                quiet = True)
    
    # Redirect eel js to the file located in the python package
    @staticmethod
    def _eelJSFile():
        return open(pkg.resource_filename('eel', 'eel.js'), encoding='utf-8').read()
    _eelJSFile = btl.route('/eel.js')(_eelJSFile.__func__)

    # Put references to the web folder
    @staticmethod
    def _staticFiles(path):
        return btl.static_file(path, root = eel.RootWebDir)
    _staticFiles = btl.route('/<path:path>')(_staticFiles.__func__)

    # Allow the client page to establish a connect and handle that
    @staticmethod
    def _establishConnection(ws):
        eel.OpenSocket = ws
        for f in eel.ExposedFunctions:
            command = SocketCommand('_addServerFunction')
            command.Parameters = [f]
            eel._send(json.dumps(command, cls = MessageEncoder))

        while True:
            msg = ws.receive()
            print('Received message: {}'.format(msg))
            if msg is not None:
                message = json.loads(msg, cls = MessageDecoder)
                if isinstance(message, SocketCommand):
                    gevent.spawn(eel.handleCommand, message)
                elif isinstance(message, SocketResponse):
                    gevent.spawn(eel.handleResponse, message)
                else:
                    print('Hey. I got this message. Whats up with that? {}'.format(message))
            else:
                sys.exit() 
    _establishConnection = btl.route('/establishConnection',
                            apply = [wbs.websocket])(_establishConnection.__func__)

    @staticmethod
    def handleCommand(command):
        response = SocketResponse(command.ID)
        if command.Function in eel.ExposedFunctions:
            try:
                response.Value = eel.ExposedFunctions[command.Function](*command.Parameters)
            except Exception as e:
                response.Error = True
                response.ErrorMessage = str(e)
        else:
            response.Error = True
            response.ErrorMessage = 'Could not find function: {}'.format(command.Function)
        
        eel._send(json.dumps(response, cls = MessageEncoder))

    @staticmethod
    def handleResponse(response):
        if response.ID in eel.Callbacks:
            eel.Callbacks.pop(response.ID)(response)
        else:
            eel.CallReturnValues[response.ID] = response
        return

    @staticmethod
    def _send(message):
        print('Sending message: {}'.format(message))
        eel.OpenSocket.send(message)

    @staticmethod
    def expose(nameOrFunction):
        # Deal with '@eel.expose()' - treat as '@eel.expose'
        if nameOrFunction is None:
            return expose

        if type(nameOrFunction) == str:   # Called as '@eel.expose("my_name")'
            name = nameOrFunction
            def decorator(function):
                eel._expose(name, function)
                return function
            return decorator
        else:
            function = nameOrFunction
            eel._expose(function.__name__, function)
            return function
    
    @staticmethod
    def _expose(name, function):
        if name in eel.ExposedFunctions:
            raise ValueError('Already exposed function: {}'.format(name))
        eel.ExposedFunctions[name] = function
        if eel.OpenSocket is not None:
            command = SocketCommand('_addServerFunction')
            command.Parameters = [name]
            eel._send(json.dumps(command, cls = MessageEncoder))
        


