'use strict';

var cleanedData,
    pattern = /^\{\{\s*(\w*)\s*\}\}$/g,
    getContext,
    evaluateVars,
    cleanData,
    getAllContext,
    isContextValid,
    span = document.createElement('span');

span.setAttribute('style', 'color:red');
span.setAttribute('id', 'context-error');

getContext = function () {
    var contextDiv = document.querySelectorAll('.field-context, .field-default_values')[0];
    if (contextDiv && !contextDiv.querySelector('span')) {
        contextDiv.appendChild(span);
    }
    return document.querySelectorAll('#id_config-0-context, #id_default_values')[0];
};

// check default_values is valid
isContextValid = function () {
    var json = getContext();
    if (!json) { return true; }  // VPN server
    try {
        JSON.parse(json.value);
    } catch (e) {
        span.innerHTML = 'Invalid JSON: ' + e.message;
        return false;
    }
    span.innerHTML = '';
    return true;
};

evaluateVars = function (data, context) {
    if (typeof data === 'object') {
        Object.keys(data).forEach(function (key) {
            data[key] = evaluateVars(data[key], context);
        });
    }
    if (typeof data === 'string') {
        var found_vars = data.match(pattern);
        if (found_vars !== null) {
            found_vars.forEach(function (element) {
                element = element.replace(/^\{\{\s+|\s+\}\}$|^\{\{|\}\}$/g, '');
                if (context.hasOwnProperty(element)) {
                    data = data.replace(pattern, context[element]);
                }
            });
        }
    }
    return data;
};

getAllContext = function () {
    var userContextField = getContext(),
        systemContextField = document.getElementById('system_context'),
        value;
    if (userContextField) {
        var defaultValues = JSON.parse(userContextField.value),
            systemContext = JSON.parse(systemContextField.textContent);
        value = Object.assign(
            {},
            systemContext,
            defaultValues
        );
    }
    return value;
};

cleanData = function (data) {
    var json = getAllContext();
    if (json && data && isContextValid()) {
        cleanedData = evaluateVars(data, json);
        return cleanedData;
    } else {
        return data;
    }
};
