/* Standard Qt QWebChannel JavaScript API */
"use strict";

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel transport object is invalid");
        return;
    }

    var channel = this;
    this.transport = transport;
    this.send = function(data) {
        channel.transport.send(JSON.stringify(data));
    };

    this.transport.onmessage = function(message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        var type = data.type;
        if (type === 1) { // signal
            var object = channel.objects[data.object];
            if (object) {
                object.__receiveSignal(data.signal, data.args);
            }
        } else if (type === 2) { // response
            var callback = channel.callbacks[data.id];
            if (callback) {
                delete channel.callbacks[data.id];
                callback(data.data);
            }
        } else if (type === 5) { // init
            channel.exec(data.data);
        }
    };

    this.exec = function(data) {
        channel.objects = {};
        for (var objectName in data) {
            var object = data[objectName];
            channel.objects[objectName] = new QObject(objectName, object, channel);
        }
        if (initCallback) {
            initCallback(channel);
        }
    };

    this.callbacks = {};
    this.send({type: 5}); // init
};

function QObject(name, data, channel) {
    this.__id__ = name;
    this.__channel__ = channel;
    this.__signalCallbacks = {};

    var self = this;
    data.signals.forEach(function(signal) {
        var signalName = signal[0];
        self[signalName] = {
            connect: function(callback) {
                if (!self.__signalCallbacks[signalName]) {
                    self.__signalCallbacks[signalName] = [];
                }
                self.__signalCallbacks[signalName].push(callback);
            }
        };
    });

    data.methods.forEach(function(method) {
        var methodName = method[0];
        self[methodName] = function() {
            var args = Array.prototype.slice.call(arguments);
            var callback = null;
            if (args.length > 0 && typeof args[args.length - 1] === "function") {
                callback = args.pop();
            }
            var id = Math.random().toString(36).substring(2, 9);
            if (callback) {
                self.__channel__.callbacks[id] = callback;
            }
            self.__channel__.send({
                type: 0,
                object: self.__id__,
                method: methodName,
                args: args,
                id: id
            });
        };
    });

    this.__receiveSignal = function(signalName, args) {
        var callbacks = self.__signalCallbacks[signalName];
        if (callbacks) {
            callbacks.forEach(function(cb) {
                cb.apply(cb, args);
            });
        }
    };
}

if (typeof module !== "undefined") {
    module.exports = { QWebChannel: QWebChannel };
}
