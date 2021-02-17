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
            defaultValues,
            systemContext
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

(function ($) {
    $(document).ready(function($){
        var systemContext = $('#system-context');
        var systemContextBtn = $('.system-context');
        var btnText;
        function setSystemContextHeight() {
            // Hides System Defined Variables when
            // its height is > 182px
            if (systemContext.height() > 182) {
                systemContext.addClass('hide-sc');
                systemContextBtn.addClass('show-sc');
            }
        }
        systemContextBtn.on('click', function (event) {
            event.preventDefault();
            systemContext.toggleClass('hide-sc');
            btnText = "Hide";
            if (systemContext.hasClass('hide-sc')) {
                btnText = "Show";
            }
            if (gettext) { btnText = gettext(btnText); }
            systemContextBtn.text(btnText);
        });
        $(window).on('resize', function () {
            setSystemContextHeight();
        });
        setSystemContextHeight();
    });
}(django.jQuery));
