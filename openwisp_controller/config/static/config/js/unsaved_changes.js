(function ($) {
    var form = '#content-main form',
        mapValues = function(object) {
            $('input, select, textarea', form).each(function(i, el){
                var field = $(el),
                    name = field.attr('name'),
                    value = field.val();
                // ignore fields that have no name attribute, begin with "_" or "initial-"
                if (!name || name.substr(0, 1) == '_' || name.substr(0, 8) == 'initial-' ||
                // ignore hidden fields
                name == 'csrfmiddlewaretoken' ||
                // ignore hidden inline helper fields
                name.indexOf('__prefix__') >= 0 ||
                name.indexOf('root') === 0) {
                    return;
                }
                // fix checkbox values inconsistency
                if (field.attr('type') == 'checkbox') {
                    object[name] = field.is(':checked');
                }
                else {
                    object[name] = value;
                }
                // convert JSON string to Javascript object in order
                // to perform object comparison with `objectIsEqual`
                if (name == 'config' || name == 'config-0-config' || name == 'config-0-context') {
                    try{
                        object[name] = JSON.parse(value);
                    }
                    catch(ignore){}
                }
            });
        };

    var unsaved_changes = function(e) {
        // get current values
        var current_values = {};
        mapValues(current_values);
        var changed = false,
            message = 'You haven\'t saved your changes yet!',
            initialField, initialValue,
            name;
        if (gettext) { message = gettext(message); }  // i18n if enabled
        // compare initial with current values
        for (name in django._njc_initial_values) {
            // use initial values from initial fields if present
            initialField = $('#initial-id_' + name);
            initialValue = initialField.length ? initialField.val() : django._njc_initial_values[name];
            // fix checkbox value inconsistency
            if (initialValue == 'True') { initialValue = true; }
            else if (initialValue == 'False') { initialValue = false; }
            if (name == 'config') { initialValue = JSON.parse(initialValue); }

            if (!objectIsEqual(initialValue, current_values[name])) {
                changed = true;
                break;
            }
        }
        if (changed) {
            e.returnValue = message;
            return message;
        }
    };

    // compares equality of two objects
    var objectIsEqual = function(obj1, obj2) {
        if (typeof obj1 != 'object' && typeof obj2 != 'object') {
            return obj1 == obj2;
        }

        // jslint doesn't like comparing typeof with a non-constant
        // see https://stackoverflow.com/a/18526510
        var obj1Type = typeof obj1,
            obj2Type = typeof obj2;
        if (obj1Type != obj2Type) {
            return false;
        }
        var p;
        for(p in obj1) {
            switch(typeof obj1[p]) {
                case 'object':
                    if (!objectIsEqual(obj1[p], obj2[p])) { return false; } break;
                default:
                    if (obj1[p] != obj2[p]) { return false; }
            }
        }
        for(p in obj2) {
            if(obj1[p] === undefined) { return false; }
        }
        return true;
    };

    $(function ($) {
        if (!$('.submit-row').length) { return; }
        // populate initial map of form values
        django._njc_initial_values = {};
        mapValues(django._njc_initial_values);
        // do not perform unsaved_changes if submitting form
        $(form).submit(function() {
            $(window).unbind('beforeunload', unsaved_changes);
        });
        // bind unload event
        $(window).bind('beforeunload', unsaved_changes);
    });
}(django.jQuery));
