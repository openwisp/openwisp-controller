"use strict";
django.jQuery(document).ready(function () {
  // unbinding default event handlers of admin_auto_filters
  django.jQuery("#changelist-filter select, #grp-filters select").off("change");
  django.jQuery("#changelist-filter select, #grp-filters select").off("clear");

  function setAllPlaceholder(target) {
    var allPlaceholder = gettext("All");
    django.jQuery(target).text(allPlaceholder);
  }

  function initSelect2NullOption() {
    // If the "null" option is selected for an autocomplete filter,
    // then the Django filter does not render option for the "null" option.
    // This function adds the "null" option and selects it depending
    // on the window.location.search (querystring).
    var searchHash = search_to_hash(),
      nullParam;
    django
      .jQuery(".admin-autocomplete.select2-hidden-accessible")
      .each(function (index, el) {
        el = django.jQuery(el);
        nullParam = el.attr("name") + "__isnull";
        if (searchHash[nullParam] !== undefined) {
          el.append(new Option(el.data("empty-label"), "null", false, false));
          el.val("null");
          el.trigger("change");
        }
      });
  }

  setAllPlaceholder(".auto-filter .select2-selection__placeholder");
  initSelect2NullOption();

  django.jQuery(".auto-filter").on("select2:open", function (event) {
    var optionsContainer = django
        .jQuery(event.target)
        .parent()
        .parent()
        .siblings()
        .last(),
      dropDownContainer = django
        .jQuery(optionsContainer)
        .find(".select2-container--open")[1];
    django.jQuery(optionsContainer).css("min-height", "14.75rem");
    django.jQuery(dropDownContainer).appendTo(optionsContainer);
    django.jQuery(dropDownContainer).removeAttr("style");
  });

  django.jQuery(".auto-filter").on("select2:close", function () {
    django.jQuery(".auto-filter-choices").css("min-height", "");
  });

  function applyFilter(target) {
    var applyFilterButton = django.jQuery("#ow-apply-filter"),
      filterElement = django.jQuery(target),
      val = filterElement.val() || "",
      param = filterElement.attr("name"),
      class_name = filterElement.attr("class"),
      nullParam = param + "__isnull",
      queryString = search_to_hash();
    // Use the "null" querystring if user chose to filter
    // for "null" values.
    if (val === "") {
      delete queryString[param];
      delete queryString[nullParam];
    } else if (val === "null") {
      delete queryString[param];
      queryString[nullParam] = ["true"];
    } else {
      delete queryString[nullParam];
      queryString[param] = [val];
    }
    var filterQuery = hash_to_search(queryString);
    if (!applyFilterButton.length) {
      if (class_name.includes("admin-autocomplete")) {
        window.location.search = filterQuery;
      }
    } else {
      django.jQuery(target).find(".filter-options").remove();
      django.jQuery(target).append(
        `<div class="filter-options">
          <a class="selected" href="${filterQuery}"></a>
        </div>`,
      );
    }
  }

  django.jQuery(".auto-filter").on("select2:select", function (event) {
    applyFilter(event.target);
  });

  django.jQuery(".auto-filter").on("select2:clear", function (event) {
    applyFilter(event.target);
    // execute this after internal select2 events complete
    Promise.resolve().then(function () {
      setAllPlaceholder(
        django.jQuery(event.target).parent().find(".select2-selection__placeholder"),
      );
    });
  });
});
