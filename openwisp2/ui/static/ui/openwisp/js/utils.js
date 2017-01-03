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
}());
