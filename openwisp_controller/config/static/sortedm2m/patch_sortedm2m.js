"use strict";
(function ($) {
  $(document).ready(function () {
    if ($(".sortedm2m-items").length < 2) {
      destroyHiddenSortableWidget($);
    }
    $(document).on("click", "a.inline-deletelink", function () {
      destroyHiddenSortableWidget($);
    });
  });

  function destroyHiddenSortableWidget($) {
    $(".inline-related.empty-form .sortedm2m-items").sortable("destroy");
  }
})(django.jQuery);
