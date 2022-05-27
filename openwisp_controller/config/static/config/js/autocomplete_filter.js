'use strict';
django.jQuery(document).ready(function () {
    django.jQuery('#ow-apply-filter').on('click', function () {
        var filter = django.jQuery('.auto-filter select, #grp-filters select');
        var val = filter.val() || '';
        var class_name = filter.attr('class');
        var param = filter.attr('name');
        if (class_name.includes('admin-autocomplete')) {
            window.location.search = search_replace(param, val);
        }
    });

    django.jQuery('.auto-filter').on('select2:open', function () {
        var dropDownContainer = django.jQuery('.select2-container--open')[1];
        django.jQuery(dropDownContainer).appendTo('#auto-filter-choices');
        django.jQuery(dropDownContainer).removeAttr('style');
    });
});

function search_replace(name, value) {
    var new_search_hash = search_to_hash();
    if (value) {
        new_search_hash[decodeURIComponent(name)] = [];
        new_search_hash[decodeURIComponent(name)].push(decodeURIComponent(value));
    } else {
        delete new_search_hash[decodeURIComponent(name)];
    }
    return hash_to_search(new_search_hash);
}

function search_to_hash() {
    var h = {};
    if (window.location.search == undefined || window.location.search.length < 1) {
        return h;
    }
    var q = window.location.search.slice(1).split('&');
    for (var i = 0; i < q.length; i++) {
        var key_val = q[i].split('=');
        // replace '+' (alt space) char explicitly since decode does not
        var hkey = decodeURIComponent(key_val[0]).replace(/\+/g, ' ');
        var hval = decodeURIComponent(key_val[1]).replace(/\+/g, ' ');
        if (h[hkey] == undefined) {
            h[hkey] = [];
        }
        h[hkey].push(hval);
    }
    return h;
}

function hash_to_search(h) {
    var search = String('?');
    for (var k in h) {
        if (k === '') {
            continue;
        } // ignore invalid inputs, e.g. '?&=value'
        for (var i = 0; i < h[k].length; i++) {
            search += search == '?' ? '' : '&';
            search += encodeURIComponent(k) + '=' + encodeURIComponent(h[k][i]);
        }
    }
    return search;
}
