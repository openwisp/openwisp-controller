'use strict';
(function ($) {
    django._schemas = new Map();
    django._jsonEditors = new Map();
    var inFullScreenMode = false,
        prevDefaultValues = {},
        defaultValuesUrl = window.location.origin + '/admin/config/device/get-template-default-values/',
    removeDefaultValues = function(contextValue, defaultValues) {
        // remove default values when template is removed.
        Object.keys(prevDefaultValues).forEach(function (key) {
            if (!defaultValues.hasOwnProperty(key) && contextValue.hasOwnProperty(key)) {
                delete contextValue[key];
            }
        });
        return contextValue;
    },
    removeUnchangedDefaultValues = function(contextValue) {
        // This method is called on the submit event to remove any template default
        // value which was not customized which allows to avoid saving redundant data
        Object.keys(prevDefaultValues).forEach(function (key) {
            if (prevDefaultValues[key] == contextValue[key]) {
                delete contextValue[key];
            }
        });
        return contextValue;
    },
    updateContext = function (isLoading, defaultValues={}) {
        var contextField = $('#id_config-0-context'),
            systemContextField = $('#system_context');
        if (contextField.length && systemContextField.length) {
            var contextValue = JSON.parse(contextField.val()),
                systemContextValue = JSON.parse(systemContextField.text());
            // add default values to contextValue
            Object.keys(defaultValues).forEach(function (key) {
                if (!contextValue.hasOwnProperty(key) && !systemContextValue.hasOwnProperty(key)) {
                    contextValue[key] = defaultValues[key];
                }
            });

            if (isLoading && django._owcInitialValues) {
                django._owcInitialValues['config-0-context'] = removeDefaultValues(
                    contextValue,
                    defaultValues
                );
            }

            contextField.val(JSON.stringify(
                removeDefaultValues(contextValue, defaultValues),
                null,
                4
            ));
            prevDefaultValues = JSON.parse(JSON.stringify(defaultValues));
            $('.flat-json-toggle-textarea').trigger('click');
            $('.flat-json-toggle-textarea').trigger('click');
        }
    },
    getDefaultValues = function (isLoading=false) {
        var pks = $('input[name="config-0-templates"]').attr('value');
        if (pks) {
            $.get(defaultValuesUrl, {pks: pks})
                .done( function (data) {
                    updateContext(isLoading, data.default_values);
                })
                .fail(function (data) {
                    window.console.error(data.responseText);
                });
        } else {
            // remove existing default values if no template is selected
            updateContext(isLoading, {});
        }
    },
    toggleFullScreen = function () {
        var advanced = $('.advanced_editor:visible');
        if (!inFullScreenMode) {
            advanced.addClass('full-screen');
            $('html').addClass('editor-full');
            inFullScreenMode = true;
            advanced.find('.jsoneditor-menu a').show();
            advanced.find('.jsoneditor-menu label').show();
        }
        else {
            advanced.removeClass('full-screen');
            $('html').removeClass('editor-full');
            inFullScreenMode = false;
            advanced.find('.jsoneditor-menu a').hide();
            advanced.find('.jsoneditor-menu label').hide();
        }
    };

    var initAdvancedEditor = function (target, data, schema, disableSchema) {
        var advanced = $(target).prev('.advanced_editor');
        if (advanced.length === 0){
            advanced = $('<div class="advanced_editor"></div>');
            $(advanced).insertBefore($(target));
        } else {
            advanced.empty();
        }
        $(target).hide();
        // if disableSchema is true, do not validate againsts schema, default is false
        schema = disableSchema ? {} : schema;
        var options = {
            mode: 'code',
            theme: 'ace/theme/tomorrow_night_bright',
            indentation: 4,
            onEditable: function () {
                return true;
            },
            onChange: function () {
                $(target).val(editor.getText());
            },
            schema: schema
        };

        var editor = new advancedJSONEditor(advanced.get(0), options, data);
        editor.aceEditor.setOptions({
            fontSize: 14,
            showInvisibles: true
        });
        // remove powered by ace link
        advanced.find('.jsoneditor-menu a').remove();
        // add  listener to .screen-mode button for toggleScreenMode
        advanced.parents('.field-config').find('.screen-mode').click(toggleFullScreen);
        // add controls to the editor header
        advanced.find('.jsoneditor-menu')
            .append($(`<a href="javascript:;" class="jsoneditor-exit"><img class="icon" src="${window.staticUrl}admin/img/icon-deletelink.svg" /> back to normal mode</a>`))
            .append(advanced.parents('.field-config').find('#netjsonconfig-hint')
                .clone(true)
                .attr('id', 'netjsonconfig-hint-advancedmode'));
        // hide on esc button
        $('html').on('keydown', function (e) {
            if (inFullScreenMode && e.keyCode === 27) { // ESC
                $('.advanced_editor:visible').find('.jsoneditor-exit').click();
            }
        });
        return editor;
    };

    // returns true if JSON is well formed
    // and valid according to its schema
    var isValidJson = function (advanced) {
        var valid,
            cleanedData;
        try {
            cleanedData = window.cleanData(advanced.get());
            valid = advanced.validateSchema(cleanedData);
        } catch (e) {
            valid = false;
        }
        return valid;
    };

    var alertInvalidJson = function () {
        alert("The JSON entered is not valid");
    };

    var getEditorErrors = function (editor) {
        var value = JSON.parse(JSON.stringify(editor.getValue()));
        var cleanedData = window.cleanData(value),
            error = editor.validate(cleanedData);
        return error;
    };

    var handleMaxLengthAttr = function() {
        $('.jsoneditor input[maxlength]:not(.has-max-length)').map((i, field) => {
            $(field).attr('data-maxlength', $(field).attr('maxLength'));
        });
        $('.jsoneditor input[maxlength]:not(.has-max-length)').addClass('has-max-length');
    };

    var validateOnDefaultValuesChange = function (editor, advancedEditor) {
        window.isContextValid();
        if (inFullScreenMode) {
            advancedEditor.validate();
        } else {
            editor.onChange();
        }
    };

    var loadUi = function (el, backend, schemas, setInitialValue) {
        var field = $(el),
            form = field.parents('form').eq(0),
            value = JSON.parse(field.val()),
            id = field.attr('id') + '_jsoneditor',
            initialField = $('#initial-' + field.attr('id')),
            container = field.parents('.form-row').eq(0),
            labelText = container.find('label:not(#netjsonconfig-hint)').text(),
            startval = $.isEmptyObject(value) ? null : value,
            editorContainer = $('#' + id),
            html, editor, options, wrapper, header,
            getEditorValue, updateRaw, advancedEditor,
            $advancedEl,
            contextField,
            flatJsonField;
        // inject editor unless already present
        if (!editorContainer.length) {
            html = '<div class="jsoneditor-wrapper">';
            html += '<fieldset class="module aligned"><h2>' + labelText + '</h2>';
            html += '<div id="' + id + '" class="jsoneditor"></div></fieldset>';
            html += '</div>';
            container.hide().after(html);
            editorContainer = $('#' + id);
        }
        else {
            editorContainer.html('');
        }

        // stop operation if empty admin inline object
        if (field.attr('id').indexOf('__prefix__') > -1) {
            return;
        }

        wrapper = editorContainer.parents('.jsoneditor-wrapper');
        options = {
            theme: 'django',
            disable_collapse: true,
            disable_edit_json: true,
            startval: startval,
            keep_oneof_values: false,
            show_errors: field.data('show-errors') ? field.data('show-errors'): 'change',
            // if no backend selected use empty schema
            schema: backend ? schemas[backend] : {}
        };
        if (backend) {
            options.schema = schemas[backend];
        }
        // single schema mode
        else if (backend === false) {
            options.schema = schemas;
        }
        // if no backend selected use empty schema
        else {
            options.schema = {};
        }
        if (field.attr("data-options") !== undefined) {
            $.extend(options, JSON.parse(field.attr("data-options")));
        }

        editor = new JSONEditor(document.getElementById(id), options);
        django._jsonEditors[id] = editor;
        // initialise advanced json editor here (disable schema validation in VPN admin)
        advancedEditor = initAdvancedEditor(field, value, options.schema, $('#vpn_form').length === 1);
        $advancedEl = $(advancedEditor.container);
        getEditorValue = function () {
            return JSON.stringify(editor.getValue(), null, 4);
        };
        updateRaw = function () {
            editor.root.showValidationErrors(getEditorErrors(editor));
            field.val(getEditorValue());
        };

        if (editor.editors.root.addproperty_button) {
            editor.editors.root.addproperty_button.value = 'Configuration Menu';
        }
        // set initial field value to the schema default
        if (setInitialValue) {
            initialField.val(getEditorValue());
        }
        // update raw value on change event
        editor.on('change', updateRaw);
        editor.on('change', handleMaxLengthAttr);
        // update raw value before form submit
        form.submit(function (e) {
            // only submit form if the editor is clear of all validation errors
            // eliminating vpn because it's UI is not yet using default values
            if (getEditorErrors(editor).length && !$('.model-vpn').length) {
                e.preventDefault();
                var message = 'Please correct all validation errors below';
                if (gettext) { message = gettext(message); }
                alert(message);
            }
            var contextField = $('#id_config-0-context');
            if (contextField.length) {
                var contextValue = JSON.parse(contextField.val());
                contextField.val(JSON.stringify(
                    removeUnchangedDefaultValues(contextValue)
                ));
            }
            if ($advancedEl.is(':hidden')) { return; }
            // only submit the form if the json in the advanced editor is valid
            if (!isValidJson(advancedEditor)) {
                e.preventDefault();
                alertInvalidJson();
            }
            else {
                if (container.is(':hidden')) { updateRaw(); }
            }
        });

        // trigger schema-data validation on default values change
        contextField = window.getContext();
        if (contextField) {
            contextField.addEventListener('change', function () {
                validateOnDefaultValuesChange(editor, advancedEditor);
            });
        }
        // trigger schema-data validation on flat-json-value change
        flatJsonField = $('.flat-json-rows');
        if (flatJsonField.length) {
            flatJsonField.on('change', function () {
                validateOnDefaultValuesChange(editor, advancedEditor);
            });
        }
        // add advanced edit button
        header = editorContainer.find('> div > h3');
        header.find('span:first-child').hide();  // hides editor title
        header.attr('class', 'controls');
        // move advanced mode button in auto-generated UI
        container.find('.advanced-mode').clone().prependTo(header);
        // advanced mode button
        header.find('.advanced-mode').click(function () {
            if (!window.isContextValid()) {
                alert('Advanced mode does not work when default value field is invalid JSON!');
            } else {
                // update autogenrated advanced json editor with new data
                advancedEditor.set(JSON.parse(field.val()));
                wrapper.hide();
                container.show();
                // set the advanced editor container to full screen mode
                toggleFullScreen();
            }
        });

        // back to normal mode button
        $advancedEl.find('.jsoneditor-exit').click(function () {
            // check if json in advanced mode is valid before coming back to normal mode
            if (isValidJson(advancedEditor)) {
                // update autogenerated UI
                editor.setValue(JSON.parse(field.val()));
                toggleFullScreen();
                container.hide();
                wrapper.show();
            }
            else {
                alertInvalidJson();
            }
        });

        // re-enable click on netjsonconfig hint
        $advancedEl.find('#netjsonconfig-hint-advancedmode a').click(function () {
            var window_ = window.open($(this).attr('href'), '_blank');
            window_.focus();
        });

        // allow to add object properties by pressing enter
        form.on('keypress', '.jsoneditor .modal input[type=text]', function (e) {
            if (e.keyCode == 13) {
                e.preventDefault();
                $(e.target).siblings('input.json-editor-btn-add').trigger('click');
                $(e.target).val('');
            }
        });

        // so that other files can use updateContext
        window.updateContext = updateContext;

        $('.jsoneditor').on('input paste', '.has-max-length:visible', function(e) {
            var field = $(e.target),
                pasteValue = '';

            if (e.originalEvent.type === 'paste') {
                pasteValue = e.originalEvent.clipboardData.getData('text');
            }

            if (field.val().indexOf('{{') > -1 || pasteValue.indexOf('{{') > -1) {
                field.removeAttr('maxlength');
            } else {
                field.attr('maxlength', field.data('maxlength'));
            }
        });
    };

    var bindLoadUi = function () {
        $('.jsoneditor-raw:not([name*="__prefix__"])').each(function (i, el) {
            $.getJSON($(el).data('schema-url'), function (schemas) {
                django._schemas[$(el).data('schema-url')] = schemas;
                var field = $(el),
                    schema = field.attr("data-schema"),
                    schemaSelector = field.attr("data-schema-selector");
                if (schema !== undefined) {
                    loadUi(el, schema, schemas, true);
                } else {
                    if (schemaSelector === undefined) {
                        schemaSelector = '#id_backend, #id_config-0-backend';
                    }
                    var selector = $(schemaSelector),
                        schemaKey = selector.val() || false;
                    // load first time
                    loadUi(el, schemaKey, schemas, true);
                    // reload when selector is changed
                    if (selector.length) {
                        selector.change(function () {
                            loadUi(el, selector.val(), schemas);
                        });
                    }
                }
                $(`#${el.id}`).trigger('jsonschema-schemaloaded');
            });
        });
    };

    $(function () {
        var addConfig = $('#config-group.inline-group .add-row');
        // if configuration is admin inline
        // load it when add button is clicked
        addConfig.click(bindLoadUi);
        // otherwise load immediately
        bindLoadUi();
        // fill device context field with default values of selected templates.
        // If unsaved_changes have already mapped values, then fetch defaultValues,
        // otherwise wait for event to be triggered.
        if (django._owcInitialValues !== undefined){
            getDefaultValues(true);
        } else {
            $(document).one('owcInitialValuesLoaded', function () {
                getDefaultValues(true);
            });
        }
        $('.sortedm2m-items').on('change', function() {
            getDefaultValues();
        });
    });
}(django.jQuery));

var matchKey = (function () {
    var elem = document.documentElement;
    if (elem.matches) { return 'matches'; }
    if (elem.webkitMatchesSelector) { return 'webkitMatchesSelector'; }
    if (elem.mozMatchesSelector) { return 'mozMatchesSelector'; }
    if (elem.msMatchesSelector) { return 'msMatchesSelector'; }
    if (elem.oMatchesSelector) { return 'oMatchesSelector'; }
}());
// JSON-Schema Edtor django theme
JSONEditor.defaults.themes.django = JSONEditor.AbstractTheme.extend({
    getContainer: function () {
        return document.createElement('div');
    },
    getFloatRightLinkHolder: function () {
        var el = document.createElement('div');
        el.style = el.style || {};
        el.style.cssFloat = 'right';
        el.style.marginLeft = '10px';
        return el;
    },
    getModal: function () {
        var el = document.createElement('div');
        el.className = 'modal';
        el.style.display = 'none';
        return el;
    },
    getGridContainer: function () {
        var el = document.createElement('div');
        el.className = 'grid-container';
        return el;
    },
    getGridRow: function () {
        var el = document.createElement('div');
        el.className = 'grid-row';
        return el;
    },
    getGridColumn: function () {
        var el = document.createElement('div');
        el.className = 'grid-column';
        return el;
    },
    setGridColumnSize: function (el) {
        return el;
    },
    getLink: function (text) {
        var el = document.createElement('a');
        el.setAttribute('href', '#');
        el.appendChild(document.createTextNode(text));
        return el;
    },
    disableHeader: function (header) {
        header.style.color = '#ccc';
    },
    disableLabel: function (label) {
        label.style.color = '#ccc';
    },
    enableHeader: function (header) {
        header.style.color = '';
    },
    enableLabel: function (label) {
        label.style.color = '';
    },
    getFormInputLabel: function (text) {
        var el = document.createElement('label');
        el.appendChild(document.createTextNode(text));
        return el;
    },
    getCheckboxLabel: function (text) {
        var el = this.getFormInputLabel(text);
        return el;
    },
    getHeader: function (text) {
        var el = document.createElement('h3');
        if (typeof text === "string") {
            el.textContent = text;
        } else {
            el.appendChild(text);
        }
        return el;
    },
    getCheckbox: function () {
        var el = this.getFormInputField('checkbox');
        el.style.display = 'inline-block';
        el.style.width = 'auto';
        return el;
    },
    getMultiCheckboxHolder: function (controls, label, description) {
        var el = document.createElement('div'),
            i;

        if (label) {
            label.style.display = 'block';
            el.appendChild(label);
        }

        for (i in controls) {
            if (!controls.hasOwnProperty(i)) { continue; }
            controls[i].style.display = 'inline-block';
            controls[i].style.marginRight = '20px';
            el.appendChild(controls[i]);
        }

        if (description) { el.appendChild(description); }

        return el;
    },
    getSelectInput: function (options) {
        var select = document.createElement('select');
        if (options) { this.setSelectOptions(select, options); }
        return select;
    },
    getSwitcher: function (options) {
        var switcher = this.getSelectInput(options);
        switcher.className = 'switcher';
        return switcher;
    },
    getSwitcherOptions: function (switcher) {
        return switcher.getElementsByTagName('option');
    },
    setSwitcherOptions: function (switcher, options, titles) {
        this.setSelectOptions(switcher, options, titles);
    },
    setSelectOptions: function (select, options, titles) {
        titles = titles || [];
        select.innerHTML = '';
        var i, option;
        for (i = 0; i < options.length; i++) {
            option = document.createElement('option');
            option.setAttribute('value', options[i]);
            option.textContent = titles[i] || options[i];
            select.appendChild(option);
        }
    },
    getTextareaInput: function () {
        var el = document.createElement('textarea');
        el.className = 'vLargeTextField';
        return el;
    },
    getRangeInput: function (min, max, step) {
        var el = this.getFormInputField('range');
        el.setAttribute('min', min);
        el.setAttribute('max', max);
        el.setAttribute('step', step);
        return el;
    },
    getFormInputField: function (type) {
        var el = document.createElement('input');
        el.className = 'vTextField';
        el.setAttribute('type', type);
        return el;
    },
    afterInputReady: function () {
        return;
    },
    getFormControl: function (label, input, description) {
        var el = document.createElement('div');
        el.className = 'form-row';
        if (label) { el.appendChild(label); }
        if (input.type === 'checkbox') {
            label.insertBefore(input, label.firstChild);
        } else {
            el.appendChild(input);
        }
        if (description) { el.appendChild(description); }
        return el;
    },
    getIndentedPanel: function () {
        var el = document.createElement('div');
        el.className = 'inline-related';
        return el;
    },
    getChildEditorHolder: function () {
        var el = document.createElement('div');
        el.className = 'inline-group';
        return el;
    },
    getDescription: function (text) {
        var el = document.createElement('p');
        el.className = 'help';
        el.innerHTML = text;
        return el;
    },
    getCheckboxDescription: function (text) {
        return this.getDescription(text);
    },
    getFormInputDescription: function (text) {
        return this.getDescription(text);
    },
    getHeaderButtonHolder: function () {
        var el = document.createElement('span');
        el.className = 'control';
        return el;
    },
    getButtonHolder: function () {
        var el = document.createElement('div');
        el.className = 'control';
        return el;
    },
    getButton: function (text, icon, title) {
        var el = document.createElement('input'),
            className = 'button';
        if (text.indexOf('Delete') > -1) {
            className += ' deletelink';
        }
        el.className = className;
        el.type = 'button';
        this.setButtonText(el, text, icon, title);
        return el;
    },
    setButtonText: function (button, text, icon, title) {
        button.value = text;
        if (title) { button.setAttribute('title', title); }
    },
    getTable: function () {
        return document.createElement('table');
    },
    getTableRow: function () {
        return document.createElement('tr');
    },
    getTableHead: function () {
        return document.createElement('thead');
    },
    getTableBody: function () {
        return document.createElement('tbody');
    },
    getTableHeaderCell: function (text) {
        var el = document.createElement('th');
        el.textContent = text;
        return el;
    },
    getTableCell: function () {
        var el = document.createElement('td');
        return el;
    },
    getErrorMessage: function (text) {
        var el = document.createElement('p');
        el.style = el.style || {};
        el.style.color = 'red';
        el.appendChild(document.createTextNode(text));
        return el;
    },
    addInputError: function (input, text) {
        input.parentNode.className += ' errors';
        if (!input.errmsg) {
            input.errmsg = document.createElement('li');
            var ul = document.createElement('ul');
            ul.className = 'errorlist';
            ul.appendChild(input.errmsg);
            input.parentNode.appendChild(ul);
        }
        else {
            input.errmsg.parentNode.style.display = '';
        }
        input.errmsg.textContent = text;
    },
    removeInputError: function (input) {
        if (!input.errmsg) { return; }
        input.errmsg.parentNode.style.display = 'none';
        input.parentNode.className = input.parentNode.className.replace(/\s?errors/g, '');
    },
    addTableRowError: function () { return; },
    removeTableRowError: function () { return; },
    getTabHolder: function () {
        var el = document.createElement('div');
        el.innerHTML = "<div style='float: left; width: 130px;' class='tabs'></div><div class='content' style='margin-left: 130px;'></div><div style='clear:both;'></div>";
        return el;
    },
    applyStyles: function (el, styles) {
        el.style = el.style || {};
        var i;
        for (i in styles) {
            if (!styles.hasOwnProperty(i)) { continue; }
            el.style[i] = styles[i];
        }
    },
    closest: function (elem, selector) {
        while (elem && elem !== document) {
            if (matchKey) {
                if (elem[matchKey](selector)) {
                    return elem;
                }
                elem = elem.parentNode;
            } else {
                return false;
            }
        }
        return false;
    },
    getTab: function (span) {
        var el = document.createElement('div');
        el.appendChild(span);
        el.style = el.style || {};
        this.applyStyles(el, {
            border: '1px solid #ccc',
            borderWidth: '1px 0 1px 1px',
            textAlign: 'center',
            lineHeight: '30px',
            borderRadius: '5px',
            borderBottomRightRadius: 0,
            borderTopRightRadius: 0,
            fontWeight: 'bold',
            cursor: 'pointer'
        });
        return el;
    },
    getTabContentHolder: function (tab_holder) {
        return tab_holder.children[1];
    },
    getTabContent: function () {
        return this.getIndentedPanel();
    },
    markTabActive: function (tab) {
        this.applyStyles(tab, {
            opacity: 1,
            background: 'white'
        });
    },
    markTabInactive: function (tab) {
        this.applyStyles(tab, {
            opacity: 0.5,
            background: ''
        });
    },
    addTab: function (holder, tab) {
        holder.children[0].appendChild(tab);
    },
    getBlockLink: function () {
        var link = document.createElement('a');
        link.style.display = 'block';
        return link;
    },
    getBlockLinkHolder: function () {
        var el = document.createElement('div');
        return el;
    },
    getLinksHolder: function () {
        var el = document.createElement('div');
        return el;
    },
    createMediaLink: function (holder, link, media) {
        holder.appendChild(link);
        media.style.width = '100%';
        holder.appendChild(media);
    },
    createImageLink: function (holder, link, image) {
        holder.appendChild(link);
        link.appendChild(image);
    }
});

// This method has been copied from jdorn/json-editor library to facilitate
// overriding JSONEditor.defaults.editors.multiple.prototype.setValue
JSONEditor.defaults.editors.multiple.prototype.$each = function (obj, callback) {
    if (!obj || typeof obj !== "object") {
        return;
    }
    var i;
    if (Array.isArray(obj) || (typeof obj.length === 'number' && obj.length > 0 && (obj.length - 1) in obj)) {
        for (i = 0; i < obj.length; i++) {
            if (callback(i, obj[i]) === false) {
                return;
            }
        }
    } else {
        if (Object.keys) {
            var keys = Object.keys(obj);
            for (i = 0; i < keys.length; i++) {
                if (callback(keys[i], obj[keys[i]]) === false) {
                    return;
                }
            }
        } else {
            for (i in obj) {
                if (!obj.hasOwnProperty(i)) {
                    continue;
                }
                if (callback(i, obj[i]) === false) {
                    return;
                }
            }
        }
    }
};

// Override setValue method to allow using variables for fields with maxLength.
// The code is copied from jdorn/json-editor library but contains customization
// to remove maxLength attribute from schema of a field that has a value which
// contains a variable: this customization is required for validation to pass
// (the variable name could be longer than maxlength and may not fit).
// Later, the maxLength attribute is added back to restore validator to it's original form.
JSONEditor.defaults.editors.multiple.prototype.setValue = function (val, initial) {
    // Determine type by getting the first one that validates
    var self = this,
        validatorModification = {};
    this.$each(this.validators, function (i, validator) {
        // Customization to modify validators starts here
        if ((val) && typeof val === 'object') {
            Object.entries(val).forEach(function (entry) {
                if (typeof entry[1] === 'string' && entry[1].indexOf('{{') > -1) {
                    if ((validator.schema.properties) && (validator.schema.properties[entry[0]])) {
                        validatorModification[i] = {
                            propertyName: entry[0],
                            maxLength: validator.schema.properties[entry[0]].maxLength
                        };
                        delete validator.schema.properties[entry[0]].maxLength;
                    }
                }
            });
        }
        // Customization to modify validators ends here
        if (!validator.validate(val).length) {
            self.type = i;
            self.switcher.value = self.display_text[i];
            return false;
        }
    });
    this.switchEditor(this.type);

    this.editors[this.type].setValue(val, initial);

    // Customization to restore validators starts here
    Object.entries(validatorModification).forEach(function (entry) {
        self.validators[entry[0]].schema.properties[entry[1].propertyName].maxLength = entry[1].maxLength;
    });
    // Customization to restore validators ends here

    this.refreshValue();
    self.onChange();
};

// Overriding following methods on the JSONEditor is required for
// working of select2 fields. Refer to https://git.io/J4Qcp for
// more information.
JSONEditor.defaults.editors.select.prototype.enable = function () {
    if (!this.always_disabled) {
        this.input.disabled = false;
        if (this.select2) {
            this.select2.disabled = false;
        }
    }
    this.disabled = false;
};

JSONEditor.defaults.editors.select.prototype.disable = function () {
    this.input.disabled = true;
    if (this.select2) {
        this.select2.disabled = true;
    }
    this.disabled = true;
};

JSONEditor.defaults.editors.multiselect.prototype.enable = function () {
    if (!this.always_disabled) {
        if (this.input) {
            this.input.disabled = false;
        } else if (this.inputs) {
            for (var i in this.inputs) {
                if (!this.inputs.hasOwnProperty(i)) {
                    continue;
                }
                this.inputs[i].disabled = false;
            }
        }
        // Modified code begins
        if (this.select2) {
            this.select2.disabled = false;
        }
        this.disabled = false;
        // Modified code ends
    }
};

JSONEditor.defaults.editors.multiselect.prototype.disable = function () {
    if (this.input) {
        this.input.disabled = true;
    } else if (this.inputs) {
        for (var i in this.inputs) {
            if (!this.inputs.hasOwnProperty(i)) {
                continue;
            }
            this.inputs[i].disabled = true;
        }
    }
    // Modified code begins
    if (this.select2) {
        this.select2.disabled = true;
        this._super();
        // Modified code ends
    }
};
