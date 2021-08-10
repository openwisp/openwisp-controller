'use strict';
django.jQuery(function ($) {

  if ($('.add-form').length || !$('#device_form').length) {
    return;
  }

  // trigger window resize event
  // workaround that fixes problems with leafelet maps
  var triggerResize = function () {
    var resizeEvent = window.document.createEvent('UIEvents');
    resizeEvent.initUIEvent('resize', true, false, window, 0);
    window.dispatchEvent(resizeEvent);
  },
    showTab = function (menuLink) {
      var tabId = menuLink.attr('href');
      $('ul.tabs a').removeClass('current');
      $('.tab-content').removeClass('current');
      menuLink.addClass('current');
      $(tabId).addClass('current');
      triggerResize();
      $.event.trigger({
        type: 'tabshown',
        tabId: tabId,
      });
      return tabId;
    },
    showFragment = function (fragment) {
      if (!fragment) { return; }
      showTab($('ul.tabs a[href="' + fragment + '"]'));
    };

  $('ul.tabs a').click(function (e) {
    var tabId = showTab($(this));
    e.preventDefault();
    history.pushState(tabId, '', tabId);
  });

  var overview = $('#device_form > div > fieldset.module.aligned')
    .addClass('tab-content')
    .attr('id', 'overview-group'),
    tabs = $('#device_form > div > div.inline-group')
      .addClass('tab-content'),
    tabsContainer = $('#tabs-container ul');
  tabs.each(function (i, el) {
    var $el = $(el),
      tabId = $el.attr('id'),
      label = $el.find('> fieldset.module > h2, ' +
        '> .tabular > fieldset.module > h2').text();
    tabsContainer.append(
      '<li class="'+ label.toLowerCase().replace(' ', '-') +'"><a class="button" href="#' + tabId + '">' + label + '</a></li>'
    );
  });

  $('.tabs-loading').hide();

  // open fragment
  $(window).on('hashchange', function () {
    showFragment(window.location.hash);
  });

  // open fragment on page opening if present
  if (window.location.hash) {
    showFragment(window.location.hash);
  } else {
    $('ul.tabs li:first-child a').addClass('current');
    overview.addClass('current');
  }

  // if there's any validation error, show the first one
  var errors = $('.errorlist');
  if (errors.length) {
    var erroredTab = errors.eq(0).parents('.tab-content');
    if (erroredTab.length) {
      window.location.hash = '#' + erroredTab.attr('id');
    }
  }

  // replaces the management ip field with text with the option to edit it
  $(".field-management_ip > div").append(
    '<a id="edit_management_ip" class="button">Edit</a>'
  );
  var ip_input = $(".field-management_ip > div > input");
  var initial_ip = ip_input.prop("value");
  ip_input.after(function () {
    ip_input.hide();
    return (
      '<div class="readonly" id="management_ip_text">' +
      (initial_ip === "" ? "n/a" : initial_ip) +
      "</div>"
    );
  });
  $("#edit_management_ip").click(function () {
    var ip_text = $("#management_ip_text");
    if (this.text === "Edit") {
      ip_input.show();
      ip_text.hide();
      this.text = "Cancel";
    } else {
      ip_text.show();
      ip_input.hide();
      ip_input.val(initial_ip);
      this.text = "Edit";
    }
  });

  $('#loading-overlay').fadeOut(400);
});
