"use strict";
var leftArrow, rightArrow, slider;
const scrollDX = 200,
  btnAnimationTime = 100; //ms
var gettext;

(function () {
  document.addEventListener(
    "DOMContentLoaded",
    function () {
      leftArrow = document.querySelector(".filters-bottom .left-arrow");
      rightArrow = document.querySelector(".filters-bottom .right-arrow");
      slider = document.querySelector(".ow-filter-slider");
      initFilterDropdownHandler();
      initSliderHandlers();
      initInputFilterHandler();
      filterHandlers();
      if (slider) {
        setArrowButtonVisibility();
      }
      gettext =
        window.gettext ||
        function (v) {
          return v;
        };
      add_clear_button();
    },
    false,
  );
})();

function showFilterOptions(filter, callback = null) {
  if (!filter) {
    return;
  }
  filter.querySelector(".filter-options").style.display = "block";
  filter.querySelector(".filter-title").setAttribute("aria-expanded", "true");
  setTimeout(function () {
    filter.classList.add("ow-active");
    if (callback) {
      callback(filter);
    }
  }, 10);
}

function hideFilterOptions(filter) {
  if (!filter) {
    return;
  }
  filter.querySelector(".filter-options").style = "";
  filter.querySelector(".filter-title").setAttribute("aria-expanded", "false");
  filter.classList.remove("ow-active");
}

function toggleFilter(filter, callback = null) {
  var activeFilter = document.querySelector(".ow-filter.ow-active");
  if (activeFilter && activeFilter !== filter) {
    hideFilterOptions(activeFilter);
  }
  if (filter.classList.contains("ow-active")) {
    return hideFilterOptions(filter);
  }
  showFilterOptions(filter, callback);
}

function moveFocus(filter) {
  var option = filter.querySelectorAll("a");
  option = option[0];
  option.focus();
}

function initFilterDropdownHandler() {
  const filters = document.querySelectorAll(".ow-filter");
  // When filter title is clicked
  filters.forEach(function (filter) {
    var toggler = filter.querySelector(".filter-title");
    if (!toggler) {
      return;
    }
    toggler.addEventListener("click", function () {
      toggleFilter(filter);
    });
    toggler.addEventListener("keypress", function (e) {
      if (e.key !== "Enter" && e.key !== " ") {
        return;
      }
      toggleFilter(filter, moveFocus);
    });
    // Escape key handler
    var filterDropdown = filter.querySelector(".filter-options");
    filterDropdown.addEventListener("keyup", function (e) {
      e.stopPropagation();
      if (e.key === "Escape") {
        hideFilterOptions(filter);
        filter.querySelector(".filter-title").focus();
      }
    });
  });

  // Handle click outside of an active filter
  document.addEventListener("click", function (e) {
    var activeFilter = document.querySelector(".ow-filter.ow-active");
    if (activeFilter && !activeFilter.contains(e.target)) {
      hideFilterOptions(activeFilter);
    }
  });

  // Handle focus shift from filter
  document.addEventListener("focusin", function (e) {
    var activeFilter = document.querySelector(".ow-filter.ow-active");
    if (activeFilter && !activeFilter.contains(e.target)) {
      hideFilterOptions(activeFilter);
    }
  });

  // Handle change in filter option
  if (filters.length <= 4) {
    return;
  }
  const filterValues = document.querySelectorAll(".filter-options a");
  filterValues.forEach(function (filterValue) {
    filterValue.addEventListener("click", function (e) {
      e.preventDefault();
      var filter = document.querySelector(".ow-filter.ow-active");
      var selectedOption = filter.querySelector(".selected-option");
      var selectedElement = filter.querySelector(".selected");
      selectedElement.classList.remove("selected");
      filterValue.classList.add("selected");
      var text = filterValue.innerHTML;
      selectedOption.innerHTML = text;
      filter.querySelector(".filter-title").setAttribute("title", text);
      hideFilterOptions(filter);
    });
  });
}

function buttonAnimation(button) {
  // Animate button by adding and removing classes
  button.classList.add("down");
  setTimeout(function () {
    button.classList.remove("down");
  }, btnAnimationTime);
}

function scrollLeft() {
  buttonAnimation(leftArrow);
  slider.scrollLeft -= scrollDX;
  if (slider.scrollLeft == 0) {
    leftArrow.classList.add("force-inactive");
  } else {
    leftArrow.classList.remove("force-inactive");
  }
  rightArrow.classList.remove("force-inactive");
}

function scrollRight() {
  buttonAnimation(rightArrow);
  slider.scrollLeft += scrollDX;
  if (slider.scrollLeft + slider.offsetWidth >= slider.scrollWidth) {
    rightArrow.classList.add("force-inactive");
  } else {
    rightArrow.classList.remove("force-inactive");
  }
  leftArrow.classList.remove("force-inactive");
}

function setArrowButtonVisibility() {
  if (slider.scrollLeft === 0) {
    leftArrow.classList.add("force-inactive");
  } else {
    leftArrow.classList.remove("force-inactive");
  }
  if (slider.scrollLeft + slider.offsetWidth + 1 >= slider.scrollWidth) {
    rightArrow.classList.add("force-inactive");
  } else {
    rightArrow.classList.remove("force-inactive");
  }
}

function initInputFilterHandler() {
  if (!document.querySelector("#ow-apply-filter")) {
    return;
  }
  var inputFilterFields = document.querySelectorAll(".ow-input-filter-field");
  inputFilterFields.forEach(function (field) {
    field.addEventListener("change", function (e) {
      var filter = e.target.closest(".ow-input-filter"),
        selectedOption = filter.querySelector(".filter-options a"),
        value = e.target.value,
        newHref = "?" + selectedOption.getAttribute("parameter_name") + "=" + value;
      selectedOption.setAttribute("href", newHref);
    });
  });
  var inputFilterForms = document.querySelectorAll(".ow-input-filter form");
  inputFilterForms.forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
    });
  });
}

function initSliderHandlers() {
  // When left arrow is clicked
  if (leftArrow) {
    leftArrow.addEventListener("click", scrollLeft);
  }
  // When right arrow is clicked
  if (rightArrow) {
    rightArrow.addEventListener("click", scrollRight);
  }
  // When slider is scrolled
  if (slider) {
    slider.addEventListener("scroll", setArrowButtonVisibility);
  }
  window.addEventListener("resize", setArrowButtonVisibility);
}

function filterHandlers() {
  const filterButton = document.querySelector("#ow-apply-filter");
  if (!filterButton) {
    return;
  }
  filterButton.addEventListener("click", function () {
    const selectedOptions = document.querySelectorAll(".filter-options .selected");
    const inputFilters = document.querySelectorAll(
      ".ow-input-filter .filter-options a",
    );
    // Create params map which knows about the last applied filters
    var path = window.location.href.split("?");
    var paramsMap = {};
    if (path.length > 1) {
      // Only if path contains query params
      path[1].split("&").map(function (param) {
        const [name, val] = param.split("=");
        paramsMap[name] = val;
      });
    }
    var qs = Object.assign({}, paramsMap);
    var appliedFilters = {}; // To manage duplicate filters
    // qs will be modified according to the last applied filters
    // and current filters that need to be applied
    selectedOptions.forEach(function (selectedOption) {
      let value = selectedOption.getAttribute("href");
      // create params map for each option
      let currParamsMap = {};
      value
        .substring(1)
        .split("&")
        .forEach(function (param) {
          if (param != "") {
            let [name, val] = param.split("=");
            currParamsMap[name] = val;
          }
        });
      Object.keys(paramsMap).forEach(function (key) {
        /*
            LOGIC:
              For any filter if we check the values present in the options available
              for it, we will notice that only its options have the different pararms
              that can change or remove from currently applied filter but all other
              options of other filters always remain same.
          */
        if (key in qs) {
          if (key in currParamsMap) {
            if (currParamsMap[key] != paramsMap[key]) {
              qs[key] = currParamsMap[key];
              appliedFilters[key] = true;
            }
          } else {
            delete qs[key];
            appliedFilters[key] = false;
          }
        }
        delete currParamsMap[key];
      });
      Object.keys(currParamsMap).forEach(function (key) {
        // Add if any new filter is applied
        qs[key] = currParamsMap[key];
        appliedFilters[key] = true;
      });
    });
    inputFilters.forEach(function (filter) {
      var href = filter.getAttribute("href");
      var [key, val] = href.substring(1).split("=");
      if (val.length === 0 && key in qs) {
        if (!(key in appliedFilters) || !appliedFilters[key]) {
          delete qs[key];
        }
      } else if (val.length !== 0) {
        qs[key] = val;
      }
    });
    var queryParams = "";
    if (Object.keys(qs).length) {
      queryParams =
        "?" +
        Object.keys(qs)
          .map(function (q) {
            return `${q}=${qs[q]}`;
          })
          .join("&");
    }
    window.location.href = window.location.pathname + queryParams;
  });
}

function add_clear_button() {
  /*
  Some django versions do not support filter clear functionality
  */
  var path = window.location.href.split("?");
  if (
    path.length > 1 &&
    path[1] != "" &&
    !document.querySelector("#changelist-filter-clear")
  ) {
    var button = document.createElement("h3");
    button.setAttribute("id", "changelist-filter-clear");
    var link = document.createElement("a");
    link.setAttribute("href", path[0]);
    link.innerText = gettext("Clear all filters");
    button.appendChild(link);
    document.querySelector(".filters-control").prepend(button);
  }
}
