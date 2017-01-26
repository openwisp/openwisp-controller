/* --- gobal utility functions --- */
(function() {
    'use strict';

    /*
    * Get width and height of a hidden element
    * returns an object with height and width
    */
    $.fn.getHiddenDimensions = function () {
        var self = $(this),
        hidden = self, // this element is hidden
        parents,
        dimensions;
        // return immediately if element is visible
        if (self.is(':visible')) {
            return {
                width: self.outerWidth(),
                height: self.outerHeight()
            };
        }
        parents = self.parents(':hidden'); // look for hidden parent elements
        // if any hidden parent element
        if (parents.length) {
            // add to hidden collection
            hidden = $().add(parents).add(hidden);
        }
        /*
        trick all the hidden elements in a way that
        they wont be shown but we'll be able to measure their dimensions
        */
        hidden.css({
            position: 'absolute',
            visibility: 'hidden',
            display: 'block'
        });
        // store width of current element
        dimensions = {
            width: self.outerWidth(),
            height: self.outerHeight()
        }
        // reset hacked css on hidden elements
        hidden.css({
            position: '',
            visibility: '',
            display: ''
        });
        // return width
        return dimensions;
    };

    /*
    * mask an element so it can be closed easily
    */
    $.mask = function (element, close) {
        // both arguments required
        if (!element || !close) {
            throw ('missing required arguments');
        }
        // jQueryfy if necessary
        if (!'jquery' in element) {
            element = $(element);
        }
        // determine mask id
        var maskId = element.attr('id') + '-mask',
        // determine zIndex of mask
        zIndex = parseInt(element.css('z-index'), 10) - 1;
        // append element to body
        $('body').append('<div class="mask" id="' + maskId + '"></div>');
        // apply z-index
        $('#' + maskId).css('z-index', zIndex)
        // bind event to close
        .one('click', function () {
            close(arguments);
            $(this).remove();
        });
    };

    /**
     * cleanup any remaining alerts in layout
     */
    $.cleanupAlerts = function () {
        var div = $('#alerts-container');
        if (div.length) {
            div.hide().remove();
        }
    };

    // extend jquery to be able to retrieve a cookie
    $.getCookie = function (name) {
        var cookieValue = null,
            cookies,
            cookie,
            i;

        if (document.cookie && document.cookie !== '') {
            cookies = document.cookie.split(';');

            for (i = 0; i < cookies.length; i += 1) {
                cookie = $.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    $.csrfSafeMethod = function (method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    };

    $.sameOrigin = function (url) {
        // test that a given url is a same-origin URL
        // url could be relative or scheme relative or absolute
        var host = document.location.host, // host + port
        protocol = document.location.protocol,
        srOrigin = '//' + host,
        origin = protocol + srOrigin;
        // Allow absolute or scheme relative URLs to same origin
        return (url === origin || url.slice(0, origin.length + 1) === origin + '/') ||
        (url === srOrigin || url.slice(0, srOrigin.length + 1) === srOrigin + '/') ||
        // or any other URL that isn't scheme relative or absolute i.e relative.
        !(/^(\/\/|http:|https:).*/.test(url));
    };

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!$.csrfSafeMethod(settings.type) && $.sameOrigin(settings.url)) {
                // Send the token to same-origin, relative URLs only.
                // Send the token only if the method warrants CSRF protection
                // Using the CSRFToken value acquired earlier
                xhr.setRequestHeader("X-CSRFToken", $.getCookie('csrftoken'));
            }
        }
    });

    /*
    * Toggle Loading Div
    * @param operation: string "show" or "hide"
    */
    $.toggleLoading = function (operation) {
        var loading = $('#loading'),
            text_dimensions;
        // create loading div if not already present
        if (!loading.length) {
            $('body').append(_.template($('#loading-template').html()));
            loading = $('#loading');
            // get dimensions of "loading" text
            // might be of different length depending on the language
            text_dimensions = loading.find('.text').getHiddenDimensions();
            loading.width(text_dimensions.width + 54);  // manually fine-tuned
            loading.css({
                left: 0,
                margin: '0 auto'
            });
            // close loading
            $('#loading .icon-close').click(function (e) {
                $.toggleLoading();
                if (Ns.state.currentAjaxRequest) {
                    Ns.state.currentAjaxRequest.abort();
                }
            });
        }
        // show, hide or toggle
        if (operation === 'show') {
            loading.fadeIn(255);
        } else if (operation === 'hide') {
            loading.fadeOut(255);
        } else {
            loading.fadeToggle(255);
        }
    };
}());
