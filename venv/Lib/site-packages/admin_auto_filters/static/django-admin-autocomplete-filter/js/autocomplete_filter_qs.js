django.jQuery(document).ready(function () {
  django.jQuery('#changelist-filter select, #grp-filters select').on(
      'change',
      function (e, choice) {
          var val = django.jQuery(e.target).val() || '';
          var class_name = this.className;
          var param = this.name;
          if (class_name.includes('admin-autocomplete'))
          {
              window.location.search = search_replace(param, val);
          }
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
  
  function search_add(name, value) {
    var new_search_hash = search_to_hash();
    if ( ! (decodeURIComponent(name) in new_search_hash)) {
      new_search_hash[decodeURIComponent(name)] = [];
    }
    new_search_hash[decodeURIComponent(name)].push(decodeURIComponent(value));
    return hash_to_search(new_search_hash);
  }
  // pduey: remove a variable/value pair from the current query string and return updated href
function search_remove(name, value) {
    var new_search_hash = search_to_hash();
    if (new_search_hash[name].indexOf(value) >= 0) {
      new_search_hash[name].splice(new_search_hash[name].indexOf(value), 1);
      if (new_search_hash[name].length == 0) {
        delete new_search_hash[name];
      }
    }
    return hash_to_search(new_search_hash);
}
  
function search_to_hash() {
    var h={};
    if (window.location.search == undefined || window.location.search.length < 1) { return h;}
    q = window.location.search.slice(1).split('&');
    for (var i = 0; i < q.length; i++) {
      var key_val = q[i].split('=');
      // replace '+' (alt space) char explicitly since decode does not
      var hkey = decodeURIComponent(key_val[0]).replace(/\+/g,' ');
      var hval = decodeURIComponent(key_val[1]).replace(/\+/g,' ');
      if (h[hkey] == undefined) {
        h[hkey] = [];
      }
      h[hkey].push(hval);
    }
    return h;
}
  
function hash_to_search(h) {
    var search = String("?");
    for (var k in h) {
      if (k === '') { continue; } // ignore invalid inputs, e.g. '?&=value'
      for (var i = 0; i < h[k].length; i++) {
        search += search == "?" ? "" : "&";
        search += encodeURIComponent(k) + "=" + encodeURIComponent(h[k][i]);
      }
    }
    return search;
}
