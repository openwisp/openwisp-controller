"use strict";
const owContainer = document.getElementById("container");
const owMenu = document.getElementById("menu");
const owMainContent = document.getElementById("main-content");
const owMenuToggle = document.querySelector(".menu-toggle");
const owHamburger = document.querySelector(".hamburger");
const menuBackdrop = document.querySelector(".menu-backdrop");
const owNav = document.querySelector("#menu .nav");
const owAccountMenu = document.querySelector(".account-menu");
const owAccountDropdown = document.querySelector("#account-dropdown");
const accountToggle = document.querySelector(".account-button");
const MenuTransitionTime = "0.1s";
var wasActiveGroupOpen = false;

(function () {
  // popup page or other pages
  // where menu is not displayed
  if (!owMenu) {
    return;
  }
  setMenu();
  initGroupViewHandlers();
  initToggleMenuHandlers();
  initAccountViewHandler();
  initToolTipHandlers();
  initResizeScreenHelpers();
  showActiveItems();
})();

function Window() {
  /*
    To prevent editing of variables from console.
    Because variables are used to manage state of window
  */
  var windowWidth = window.innerWidth;
  this.setWindowWidth = function (size) {
    windowWidth = size;
  };
  this.getWindowWidth = function () {
    return windowWidth;
  };
}

function openMenuGroup(group, mgHead = null, mgDropdown = null) {
  // Open menu group and return first item of the group
  if (!group) {
    return;
  }
  if (!mgHead) {
    mgHead = group.querySelector(".mg-head");
  }
  if (!mgDropdown) {
    mgDropdown = group.querySelector(".mg-dropdown");
  }
  group.classList.add("active");
  mgHead.setAttribute("aria-expanded", "true");
  var group_items = group.querySelectorAll(".mg-link");
  group_items.forEach(function (item) {
    item.setAttribute("tabindex", 0);
  });
  return group_items[0];
}

function closeMenuGroup(group, mgHead, mgDropdown = null) {
  if (!group) {
    return;
  }
  if (!mgHead) {
    mgHead = group.querySelector(".mg-head");
  }
  if (!mgDropdown) {
    mgDropdown = group.querySelector(".mg-dropdown");
  }
  group.classList.remove("active");
  mgDropdown.style = "";
  mgHead.setAttribute("aria-expanded", "false");
  var group_items = group.querySelectorAll(".mg-link");
  group_items.forEach(function (item) {
    item.setAttribute("tabindex", -1);
  });
}

function closeActiveGroup(group = null, mgHead = null, mgDropdown = null) {
  if (group === null) {
    group = document.querySelector(".menu-group.active");
  }
  closeMenuGroup(group, mgHead, mgDropdown);
}

function isMenuOpen() {
  return !owContainer.classList.contains("toggle-menu");
}

function initResizeScreenHelpers() {
  function changeMenuState(owWindow) {
    var currentWidth = window.innerWidth;
    if (currentWidth <= 1024) {
      if (owWindow.getWindowWidth() > 1024 && isMenuOpen()) {
        // close window
        closeActiveGroup();
        owContainer.classList.add("toggle-menu");
        owWindow.setWindowWidth(currentWidth);
        setMenuToggleText();
      }
    } else if (owWindow.getWindowWidth() <= 1024) {
      // when window width is greater than 1024px
      // set class according to user last choice
      setMenuState();
      owWindow.setWindowWidth(currentWidth);
      setMenuToggleText();
    }
  }
  var owWindow = new Window();
  window.addEventListener("resize", function () {
    changeMenuState(owWindow);
  });
}

function toggleGroup(e, callback = null) {
  e.stopPropagation();
  var mgHead = e.target;
  var group = mgHead.closest(".menu-group");
  var dropdown = group.querySelector(".mg-dropdown");
  var currentActiveGroup = document.querySelector(".menu-group.active");
  var firstElement = null;
  if (currentActiveGroup && currentActiveGroup.classList.contains("active-mg")) {
    wasActiveGroupOpen = false;
  }
  if (currentActiveGroup && currentActiveGroup !== mgHead.parentElement) {
    closeActiveGroup(currentActiveGroup);
  }
  if (group.classList.contains("active-mg") && !group.classList.contains("active")) {
    wasActiveGroupOpen = true;
  }
  if (window.innerWidth > 768 && !isMenuOpen()) {
    if (!group.classList.contains("active")) {
      var groupPos = group.offsetTop;
      var scrolledBy = owNav.scrollTop;
      var dropdownHeight = group.querySelector(".mg-dropdown").offsetHeight;
      if (dropdownHeight + groupPos - scrolledBy >= window.innerHeight) {
        dropdown.style.top = groupPos - scrolledBy - dropdownHeight + 87 + "px";
        setTimeout(function () {
          firstElement = openMenuGroup(group, mgHead, dropdown);
          dropdown.style.top = groupPos - scrolledBy - dropdownHeight + 40 + "px";
          if (callback) {
            callback(firstElement);
          }
        }, 10);
      } else {
        dropdown.style.top = groupPos - scrolledBy + 47 + "px";
        setTimeout(function () {
          firstElement = openMenuGroup(group, mgHead, dropdown);
          dropdown.style.top = groupPos - scrolledBy + "px";
          if (callback) {
            callback(firstElement);
          }
        }, 10);
      }
    } else {
      closeMenuGroup(group, mgHead, dropdown);
    }
  } else {
    if (group.classList.contains("active")) {
      closeMenuGroup(group, mgHead, dropdown);
    } else {
      firstElement = openMenuGroup(group, mgHead, dropdown);
      if (callback) {
        callback(firstElement);
      }
    }
  }
}

function focusGroupLink(link) {
  // It is used as callback function in setTimeout of toggle_group
  link.focus();
}

function initGroupViewHandlers() {
  var mgHeads = document.querySelectorAll(".mg-head");
  mgHeads.forEach(function (mgHead) {
    // Handle click on menu group
    mgHead.addEventListener("click", toggleGroup);
    mgHead.addEventListener("keypress", function (e) {
      if (e.key !== "Enter" && e.key !== " ") {
        return;
      }
      toggleGroup(e, focusGroupLink);
    });
    // Show menu group label on hover when menu is close
    mgHead.addEventListener("mouseenter", function (e) {
      e.stopPropagation();
      if (window.innerWidth > 768 && !isMenuOpen()) {
        var group = e.target.parentElement;
        var groupPos = group.offsetTop;
        var scrolledBy = owNav.scrollTop;
        var label = e.target.querySelector(".label");
        label.style.top = groupPos - scrolledBy + 13 + "px";
      }
    });
    mgHead.addEventListener("mouseleave", function (e) {
      if (window.innerWidth > 768 && !isMenuOpen()) {
        var label = e.target.querySelector(".label");
        label.style = "";
      }
    });
    // Escape key handler for menu group
    var group = mgHead.closest(".menu-group");
    group.querySelector(".mg-dropdown").addEventListener("keyup", function (e) {
      if (e.key === "Escape") {
        closeMenuGroup(group);
        mgHead.focus();
      }
    });
  });

  // Show menu item label on hover when menu is close
  document.querySelectorAll(".menu-item").forEach(function (item) {
    item.addEventListener("mouseenter", function (e) {
      e.stopPropagation();
      if (window.innerWidth > 768 && !isMenuOpen()) {
        var itemPos = item.offsetTop;
        var scrolledBy = owNav.scrollTop;
        var label = e.target.querySelector(".label");
        label.style.top = itemPos - scrolledBy + 13 + "px";
      }
    });
    item.addEventListener("mouseleave", function (e) {
      var label = e.target.querySelector(".label");
      label.style = "";
    });
  });
  // Handle closing of menu group and account menu when focus is shifted
  document.addEventListener("focusin", function (e) {
    var activeGroup = document.querySelector(".menu-group.active");
    if (activeGroup && !activeGroup.contains(e.target)) {
      if (!activeGroup.classList.contains("active-mg")) {
        closeActiveGroup(activeGroup);
      }
    }
    if (owAccountMenu && !owAccountMenu.contains(e.target)) {
      closeAccountMenu();
    }
  });
  // Handle click out side the current active menu group
  document.addEventListener("click", function (e) {
    var currentActiveGroup = document.querySelector(".menu-group.active");
    if (currentActiveGroup && !currentActiveGroup.contains(e.target)) {
      if (currentActiveGroup.classList.contains("active-mg") && isMenuOpen()) {
        return;
      }
      closeActiveGroup(currentActiveGroup);
    }
  });

  // Close menu group on scroll when close
  owNav.addEventListener("scroll", function () {
    if (!isMenuOpen()) {
      closeActiveGroup();
    }
  });
}

function setMenuState() {
  let openMenu = localStorage.getItem("ow-menu");
  if (window.innerWidth > 1024) {
    if (openMenu === null) {
      // User visits first time. Keep open menu
      localStorage.setItem("ow-menu", true);
      owContainer.classList.remove("toggle-menu");
    } else if (openMenu === "true") {
      // Close the menu
      owContainer.classList.remove("toggle-menu");
    }
  }
}

function setMenuToggleText() {
  if (isMenuOpen()) {
    owMenuToggle.setAttribute("title", "Minimize menu");
    owHamburger.setAttribute("aria-label", "Minimize menu");
  } else {
    owMenuToggle.setAttribute("title", "Maximize menu");
    owHamburger.setAttribute("aria-label", "Maximize menu");
  }
}

function setMenu() {
  setMenuState();
  setTimeout(function () {
    // Transition fix: Add transition to menu and main content
    // after some time.
    if (owMenu) {
      owMenu.style.transitionDuration = MenuTransitionTime;
    }
    if (owMainContent) {
      owMainContent.style.transitionDuration = MenuTransitionTime;
    }
    if (owMenuToggle) {
      owMenuToggle.style.transitionDuration = MenuTransitionTime;
    }
  }, 1000);
  setMenuToggleText();
}

function initToggleMenuHandlers() {
  function toggleMenuHandler() {
    var activeMenuGroup = document.querySelector(".active-mg");
    if (activeMenuGroup && isMenuOpen()) {
      activeMenuGroup.classList.remove("active");
    }
    owContainer.classList.toggle("toggle-menu");
    let isMenuOpen_ = localStorage.getItem("ow-menu");
    if (window.innerWidth > 1024) {
      localStorage.setItem("ow-menu", isMenuOpen_ === "true" ? false : true);
    }
    setMenuToggleText();
    if (activeMenuGroup && isMenuOpen() && wasActiveGroupOpen) {
      activeMenuGroup.classList.add("active");
    }
  }
  if (owMenuToggle && owContainer) {
    owMenuToggle.addEventListener("click", toggleMenuHandler);
  }
  if (owHamburger && owContainer) {
    owHamburger.addEventListener("click", toggleMenuHandler);
  }

  // Close menu when backdrop is clicked
  menuBackdrop.addEventListener("click", function (e) {
    e.stopPropagation();
    closeActiveGroup();
    owContainer.classList.toggle("toggle-menu");
    setMenuToggleText();
  });

  owHamburger.addEventListener("keypress", function (e) {
    if (e.key !== "Enter" && e.key !== " ") {
      return;
    }
    toggleMenuHandler();
  });
}

function openAccountMenu() {
  owAccountMenu.classList.remove("hide");
  accountToggle.setAttribute("aria-expanded", "true");
  var links = owAccountMenu.querySelectorAll("a");
  links.forEach(function (link) {
    link.setAttribute("tabindex", "0");
  });
  return links[0];
}
function closeAccountMenu() {
  owAccountMenu.classList.add("hide");
  accountToggle.setAttribute("aria-expanded", "false");
  var links = owAccountMenu.querySelectorAll("a");
  links.forEach(function (link) {
    link.setAttribute("tabindex", "-1");
  });
  return links[0];
}
function toggleAccount(e) {
  e.stopPropagation();
  if (owAccountMenu.classList.contains("hide")) {
    return openAccountMenu();
  } else {
    closeAccountMenu();
  }
}

function initAccountViewHandler() {
  // When account button is clicked
  if (accountToggle) {
    accountToggle.onclick = function (e) {
      toggleAccount(e);
    };
    accountToggle.addEventListener("keyup", function (e) {
      if (e.key === "Enter") {
        var firstLink = toggleAccount(e);
        firstLink.focus();
      }
    });
  }
  // When clicked outside the account button
  document.addEventListener("click", function (e) {
    if (accountToggle && !accountToggle.contains(e.target)) {
      owAccountMenu.classList.add("hide");
      accountToggle.setAttribute("aria-expanded", "false");
    }
  });
  // Escape key handler
  owAccountDropdown.addEventListener("keyup", function (e) {
    e.stopPropagation();
    if (e.key === "Escape") {
      toggleAccount(e);
      setTimeout(function () {
        accountToggle.focus();
      }, 300);
    }
  });
}

function initToolTipHandlers() {
  // Tooltips shown only on narrow screen
  var tooltips = document.querySelectorAll(".tooltip-sm");
  function mouseLeaveHandler(e) {
    var tooltipText = e.target.getAttribute("tooltip-data");
    e.target.setAttribute("title", tooltipText);
    e.target.removeAttribute("tooltip-data");
    removeMouseLeaveListner(e.target);
  }
  function removeMouseLeaveListner(tooltip) {
    tooltip.removeEventListener("mouseleave", mouseLeaveHandler);
  }
  tooltips.forEach(function (tooltip) {
    tooltip.addEventListener("mouseenter", function () {
      if (window.innerWidth > 768) {
        var tooltipText = tooltip.getAttribute("title");
        tooltip.removeAttribute("title");
        tooltip.setAttribute("tooltip-data", tooltipText);
        tooltip.addEventListener("mouseleave", mouseLeaveHandler);
      }
    });
  });
}

function showActiveItems() {
  if (!owMenu) {
    return;
  }
  var pathname = window.location.pathname;
  const regex = new RegExp(/[\d\w-]*\/change\//);
  pathname = pathname.replace(regex, "");
  var activeLink = document.querySelector(`.nav a[href="${pathname}"]`);
  if (!activeLink) {
    return;
  }
  activeLink.classList.add("active");
  if (activeLink.classList.contains("mg-link")) {
    var group = activeLink.closest(".menu-group");
    group.classList.add("active-mg");
    if (isMenuOpen()) {
      openMenuGroup(group);
    }
    wasActiveGroupOpen = true;
  }
}
