"use strict";
class SocketCommand {
    constructor(func, args) {
        this.Function = '';
        this._type = 'Command';
        this.Function = func;
        this.ID = func + '|' + Math.random();
        this.Parameters = args;
    }
}
class SocketResponse {
    constructor(id) {
        this.Error = false;
        this.ErrorMessage = '';
        this._type = 'Response';
        this.ID = id;
    }
}
class Eel {
    constructor() {
        this.host = '';
        this.websocket = null;
        this.openCommands = {};
        this.exposedFunctions = {};
        this.afterInitFunctions = [];
        this.initialized = false;
        this.LogMessages = false;
        this._onLoad = this._onLoad.bind(this);
        this._init = this._init.bind(this);
        this._onServerMessage = this._onServerMessage.bind(this);
        this._addServerFunction = this._addServerFunction.bind(this);
        document.addEventListener('DOMContentLoaded', this._onLoad);
        this.expose(this._addServerFunction, '_addServerFunction');
    }
    onInit(f) {
        if (this.initialized) {
            f();
        }
        else {
            this.afterInitFunctions.push(f);
        }
    }
    expose(f, name = null) {
        if (name == null) {
            name = f.toString();
            let i = 'function '.length, j = name.indexOf('(');
            name = name.substring(i, j).trim();
        }
        this.exposedFunctions[name] = f;
    }
    _onLoad(event) {
        this.host = window.location.origin.replace('http', 'ws');
        this.websocket = new WebSocket(this.host + '/establishConnection');
        this.websocket.onmessage = this._init;
    }
    _init(event) {
        this._onServerMessage(event);
        this.initialized = true;
        this.afterInitFunctions.forEach((f) => {
            f();
        });
        this.websocket.onmessage = this._onServerMessage;
    }
    _onServerMessage(event) {
        let message = JSON.parse(event.data);
        if (this.LogMessages)
            console.log('Received message: ' + event.data);
        if (message['_type'] === 'Command') {
            this._executeCommand(message);
        }
        else if (message['_type'] === 'Response') {
            this._handleResponse(message);
        }
        else {
            console.log('Hey. I got this message. Whats up with that? ' + JSON.stringify(message));
        }
    }
    // Handling commands from the server
    _executeCommand(command) {
        let f = this.exposedFunctions[command.Function];
        let response = new SocketResponse(command.ID);
        if (f) {
            try {
                response.Value = f(...command.Parameters);
            }
            catch (error) {
                response.Error = true;
                response.ErrorMessage = error.toString();
            }
        }
        else {
            response.Error = true;
            response.ErrorMessage = 'Function ' + command.Function + ' could not be found.';
        }
        this._send(response);
    }
    // Sending commands to the server
    _addServerFunction(name) {
        this[name] = (...args) => {
            return this._callServerFunction(name, ...args);
        };
    }
    _callServerFunction(name, ...args) {
        return (callback = null) => {
            let command = new SocketCommand(name, args);
            if (callback) {
                this.openCommands[command.ID] = callback;
                this._send(command);
            }
            else {
                return new Promise((resolve) => {
                    this._send(command);
                    this.openCommands[command.ID] = resolve;
                });
            }
        };
    }
    _handleResponse(response) {
        let callback = this.openCommands[response.ID];
        if (callback) {
            callback(response);
            delete this.openCommands[response.ID];
        }
        else {
            console.log('Expected callback for response with ID ' + response.ID);
        }
    }
    _send(message) {
        if (this.LogMessages)
            console.log('Sending message: ' + JSON.stringify(message));
        if (this.websocket)
            this.websocket.send(JSON.stringify(message));
        else
            console.log('No Websocket!');
    }
}
var eel = new Eel();
