type ResponseHandler = (response : SocketResponse) => void;

class SocketCommand {
    ID : string;
    Function : string = '';
    Parameters : Array<any>;
    _type : string = 'Command';

    constructor(func : string, args : Array<any>){
        this.Function = func;
        this.ID = func + '|' + Math.random();
        this.Parameters = args;
    }
}

class SocketResponse {
    ID : string;
    Error : boolean = false;
    ErrorMessage : string = '';
    Value : any;
    _type : string = 'Response';

    constructor(id : string){
        this.ID = id;
    }
}

class Eel {
    host : string = '';
    websocket : WebSocket | null = null;
    openCommands : {[id : string] : (response : SocketResponse) => void} = {};
    exposedFunctions : {[name : string] : Function} = {};
    [key : string] : any;
    afterInitFunctions : Array<Function> = [];
    initialized : boolean = false;
    LogMessages : boolean = false;

    constructor () {
        this._onLoad = this._onLoad.bind(this);
        this._init = this._init.bind(this);
        this._onServerMessage = this._onServerMessage.bind(this);
        this._addServerFunction = this._addServerFunction.bind(this);
        document.addEventListener('DOMContentLoaded', this._onLoad);
        this.expose(this._addServerFunction, '_addServerFunction');
    }

    public onInit(f: Function){
        if (this.initialized){
            f();
        }
        else {
            this.afterInitFunctions.push(f);
        }
    }

    public expose(f : Function, name : string | null = null){
        if (name == null){
            name = f.toString();
            let i = 'function '.length, j = name.indexOf('(');
            name = name.substring(i, j).trim();
        }

        this.exposedFunctions[name] = f;
    }

    private _onLoad(event : any) {
        this.host = window.location.origin.replace('http', 'ws');
        this.websocket = new WebSocket(this.host + '/establishConnection');
        this.websocket.onmessage = this._init;
    }

    private _init(event : MessageEvent){
        this._onServerMessage(event);
        this.initialized = true;
        this.afterInitFunctions.forEach((f : Function) => {
            f();
        })
        this.websocket!.onmessage = this._onServerMessage;
    }

    private _onServerMessage(event : MessageEvent) {
        let message = JSON.parse(event.data);
        if (this.LogMessages) console.log('Received message: ' + event.data)
        if (message['_type'] === 'Command'){
            this._executeCommand(message);
        } else if (message['_type'] === 'Response'){
            this._handleResponse(message);
        } else {
            console.log('Hey. I got this message. Whats up with that? ' + JSON.stringify(message));
        }
    }

    // Handling commands from the server
    private _executeCommand(command : SocketCommand){
        let f = this.exposedFunctions[command.Function];
        let response : SocketResponse = new SocketResponse(command.ID);
        if (f){
            try{
                response.Value = f(...command.Parameters);
            }
            catch(error){
                response.Error = true;
                response.ErrorMessage = error.toString();
            }
        } else{
            response.Error = true;
            response.ErrorMessage = 'Function ' + command.Function + ' could not be found.';
        }

        this._send(response);
    }

    // Sending commands to the server
    private _addServerFunction(name : string) {
        this[name] = (...args : any[]) => {
            return this._callServerFunction(name, ...args);
        }
    }
    private _callServerFunction(name : string, ...args : any[]) {
        return (callback : ResponseHandler | null = null) => {
            let command = new SocketCommand(name, args);
            if (callback){
                this.openCommands[command.ID] = callback;
                this._send(command);
            } else {
                return new Promise((resolve) => {
                    this._send(command);
                    this.openCommands[command.ID] = resolve;
                })
            }
        }  
    }

    private _handleResponse(response : SocketResponse){
        let callback = this.openCommands[response.ID];
        if (callback){
            callback(response);
            delete this.openCommands[response.ID];
        } else{
            console.log('Expected callback for response with ID ' + response.ID);
        }
    }

    private _send(message : SocketCommand | SocketResponse){
        if (this.LogMessages) console.log('Sending message: ' + JSON.stringify(message));
        if (this.websocket) this.websocket.send(JSON.stringify(message));
        else console.log('No Websocket!')
    }

}

var eel : Eel = new Eel()