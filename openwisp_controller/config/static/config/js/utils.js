var cleanedData,
    pattern = /^\{\{\s*(\w*)\s*\}\}$/g,
    getContext,
    evaluateVars,
    cleanData,
    context_json_valid,
    span = document.createElement('span');

span.setAttribute('style', 'color:red');
span.setAttribute('id', 'context-error');

getContext = function () {
    var context_div = document.querySelectorAll(".field-context, .field-default_values")[0];
    if (context_div && !context_div.querySelector('span')) {
        context_div.appendChild(span);
    }
    return document.querySelectorAll("#id_config-0-context, #id_default_values")[0];
};

// check default_values is valid
context_json_valid = function () {
    var json = getContext();
    try {
        JSON.parse(json.value);
    } catch (e) {
        span.innerHTML = "Invalid JSON: " + e.message;
        return false;
    }
    span.innerHTML = "";
    return true;
}

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

cleanData = function (data) {
    var json = getContext();
    if (json && data && context_json_valid()) {
        cleanedData = evaluateVars(data, JSON.parse(json.value));
        return cleanedData;
    } else {
        return data;
    }
};



