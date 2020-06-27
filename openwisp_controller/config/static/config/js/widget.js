(function ($) {
    var inFullScreenMode = false,
        oldHeight = 0,
        oldWidth = 0;
    var toggleFullScreen = function () {
        var advanced = $('#advanced_editor');
        if (!inFullScreenMode) {
            // store the old height and width of the editor before going to fullscreen mode in order to be able to restore them
            oldHeight = advanced.height();
            oldWidth = advanced.width();
            advanced.addClass('full-screen').height($(window).height()).width(window.outerWidth);
            $('body').addClass('editor-full');
            $(window).resize(function () {
                advanced.height($(window).height()).width(window.outerWidth);
            });
            inFullScreenMode = true;
            advanced.find('.jsoneditor-menu a').show();
            advanced.find('.jsoneditor-menu label').show();
            window.scrollTo(0, 0);
        }
        else {
            advanced.removeClass('full-screen').height(oldHeight).width(oldWidth);
            $('body').removeClass('editor-full');
            // unbind all events listened to while going to full screen mode
            $(window).unbind('resize');
            inFullScreenMode = false;
            document.getElementById('advanced_editor').scrollIntoView(true);
            advanced.find('.jsoneditor-menu a').hide();
            advanced.find('.jsoneditor-menu label').hide();
        }
    };

    var initAdvancedEditor = function (target, data, schema, disableSchema) {
        var advanced = $("<div id='advanced_editor'></div>");
        $(advanced).insertBefore($(target));
        $(target).hide();
        // if disableSchema is true, do not validate againsts schema, default is false
        schema = disableSchema ? {} : schema;
        var options = {
            mode: 'code',
            theme: 'ace/theme/tomorrow_night_bright',
            indentation: 4,
            onEditable: function (node) {
                return true;
            },
            onChange: function () {
                $(target).val(editor.getText());
            },
            schema: schema
        };

        var editor = new advancedJSONEditor(document.getElementById(advanced.attr('id')), options, data);
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
            .append($('<a href="javascript:;" class="jsoneditor-exit"><img class="icon" src="/static/admin/img/icon-deletelink.svg" /> back to normal mode</a>'))
            .append(advanced.parents('.field-config').find('#netjsonconfig-hint')
                .clone(true)
                .attr('id', 'netjsonconfig-hint-advancedmode'));
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
            contextField;
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
            show_errors: 'change',
            // if no backend selected use empty schema
            schema: backend ? schemas[backend] : {}
        };
        if (field.attr("data-options") !== undefined) {
            $.extend(options, JSON.parse(field.attr("data-options")));
        }
        editor = new JSONEditor(document.getElementById(id), options);
        // initialise advanced json editor here (disable schema validation in VPN admin)
        advancedEditor = initAdvancedEditor(field, value, options.schema, $('#vpn_form').length === 1);
        $advancedEl = $('#advanced_editor');
        getEditorValue = function () {
            return JSON.stringify(editor.getValue(), null, 4);
        };
        updateRaw = function () {
            field.val(getEditorValue());
        };

        editor.editors.root.addproperty_button.value = 'Configuration Menu';
        // set initial field value to the schema default
        if (setInitialValue) {
            initialField.val(getEditorValue());
        }
        // update raw value on change event
        editor.on('change', updateRaw);

        // update raw value before form submit
        form.submit(function (e) {
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
                window.context_json_valid();
                if (inFullScreenMode) {
                    advancedEditor.validate();
                } else {
                    editor.onChange(JSON.parse(field.val()));
                }
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
            if (!window.context_json_valid()) {
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
    };

    var bindLoadUi = function () {
        $.getJSON(django._netjsonconfigSchemaUrl, function (schemas) {
            $('.jsoneditor-raw').each(function (i, el) {
                var field = $(el),
                    schema = field.attr("data-schema"),
                    schema_selector = field.attr("data-schema-selector");
                if (schema !== undefined) {
                    loadUi(el, schema, schemas, true);
                } else {
                    if (schema_selector === undefined) {
                        schema_selector = '#id_backend, #id_config-0-backend';
                    }
                    var backend = $(schema_selector);
                    // load first time
                    loadUi(el, backend.val(), schemas, true);
                    // reload when backend is changed
                    backend.change(function () {
                        loadUi(el, backend.val(), schemas);
                    });
                }
            });
        });
    };

    $(function () {
        var add_config = $('#config-group.inline-group .add-row');
        // if configuration is admin inline
        // load it when add button is clicked
        add_config.click(bindLoadUi);
        // otherwise load immediately
        bindLoadUi();
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
    setGridColumnSize: function (el, size) {
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
    afterInputReady: function (input) {
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
    addTableRowError: function (row) { return; },
    removeTableRowError: function (row) { return; },
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
