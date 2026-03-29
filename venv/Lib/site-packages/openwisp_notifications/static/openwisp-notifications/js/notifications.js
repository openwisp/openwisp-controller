"use strict";
const notificationReadStatus = new Map();
const userLanguage = navigator.language || navigator.userLanguage;
const owWindowId = String(Date.now());
let fetchedPages = [];

if (typeof gettext === "undefined") {
  var gettext = function (word) {
    return word;
  };
}

(function ($) {
  $(document).ready(function () {
    notificationWidget($);
    initNotificationDropDown($);
    initWebSockets($);
    owNotificationWindow.init($);
  });
})(django.jQuery);

const owNotificationWindow = {
  // Following functions are used to decide which window has authority
  // to play notification alert sound when multiple windows are open.
  init: function init($) {
    // Get authority to play notification sound
    // when current window is in focus
    $(window).on("focus load", function () {
      owNotificationWindow.set();
    });
    // Give up the authority to play sound before
    // closing the window
    $(window).on("beforeunload", function () {
      owNotificationWindow.remove();
      // Disconnect websocket to prevent missed notifications during page reload
      if (typeof notificationSocket !== "undefined") {
        notificationSocket.close();
      }
    });
    // Get authority to play notification sound when
    // other windows are closed
    $(window).on("storage", function () {
      if (localStorage.getItem("owWindowId") === null) {
        owNotificationWindow.set();
      }
    });
  },
  set: function () {
    localStorage.setItem("owWindowId", owWindowId);
  },
  remove: function () {
    if (localStorage.getItem("owWindowId") === owWindowId) {
      localStorage.removeItem("owWindowId");
    }
  },
  canPlaySound: function () {
    // Returns whether current window has the authority to play
    // notification sound
    return localStorage.getItem("owWindowId") === owWindowId;
  },
};

function initNotificationDropDown($) {
  $(".ow-notifications").click(function () {
    $(".ow-notification-dropdown").toggleClass("ow-hide");
  });

  $(document).click(function (e) {
    e.stopPropagation();
    if (
      // Only hide the widget on user-initiated clicks; ignore programmatic clicks
      e.originalEvent?.isTrusted &&
      // Check if the clicked area is dropDown
      $(".ow-notification-dropdown").has(e.target).length === 0 &&
      // Check notification-btn or not
      !$(e.target).is($(".ow-notifications")) &&
      // Hide the notification dropdown when a click occurs outside of it
      !$(e.target).is($(".ow-dialog-close")) &&
      // Do not hide if the user is interacting with the notification dialog
      !$(".ow-overlay-notification").is(":visible")
    ) {
      $(".ow-notification-dropdown").addClass("ow-hide");
    }
  });

  // Handler for adding accessibility from keyboard events
  $(document).focusin(function (e) {
    // Hide notification widget if focus is shifted to an element outside it
    e.stopPropagation();
    if (
      $(".ow-notification-dropdown").has(e.target).length === 0 &&
      // Do not hide if the user is interacting with the notification dialog
      !$(".ow-overlay-notification").is(":visible")
    ) {
      // Don't hide if focus changes to notification bell icon
      if (e.target != $("#openwisp_notifications").get(0)) {
        $(".ow-notification-dropdown").addClass("ow-hide");
      }
    }
  });

  $(".ow-notification-dropdown").on("keyup", function (e) {
    if (e.keyCode !== 27) {
      return;
    }
    // Hide notification widget on "Escape" key
    if ($(".ow-overlay-notification").is(":visible")) {
      $(".ow-overlay-notification").addClass("ow-hide");
      $(".ow-message-target-redirect").addClass("ow-hide");
    } else {
      $(".ow-notification-dropdown").addClass("ow-hide");
      $("#openwisp_notifications").focus();
    }
  });

  // Show notification widget if URL contains #notifications
  if (window.location.hash === "#notifications") {
    $(".ow-notification-dropdown").removeClass("ow-hide");
    $(".ow-notification-wrapper").trigger("refreshNotificationWidget");
  }
}

function convertAbsoluteURLToRelativeURL(urlString) {
  let url = new URL(urlString, window.location.href);
  try {
    if (url.origin) {
      urlString = urlString.replace(url.origin, "");
    }
  } catch (e) {
    // Invalid URLs (e.g., `javascript:void(0)`) are ignored
  }
  return urlString;
}

// Converts absolute URLs in notification messages to relative URLs
// (preserving path, query, and hash)
function convertMessageWithRelativeURL(htmlString) {
  const parser = new DOMParser(),
    doc = parser.parseFromString(htmlString, "text/html"),
    links = doc.querySelectorAll("a");
  links.forEach((link) => {
    const path = convertAbsoluteURLToRelativeURL(link.getAttribute("href"));
    if (path) {
      link.setAttribute("href", path);
    }
  });
  return doc.body.innerHTML;
}

function notificationWidget($) {
  let nextPageUrl = getAbsoluteUrl("/api/v1/notifications/notification/"),
    renderedPages = 2,
    busy = false,
    lastRenderedPage = 0;
  // 1 based indexing (0 -> no page rendered)

  function pageContainer(page) {
    var div = $('<div class="page"></div>');
    page.forEach(function (notification) {
      let elem = $(notificationListItem(notification));
      div.append(elem);
    });
    return div;
  }

  function appendPage() {
    $("#ow-notifications-loader").before(pageContainer(fetchedPages[lastRenderedPage]));
    if (lastRenderedPage >= renderedPages) {
      $(".ow-notification-wrapper div:first").remove();
    }
    lastRenderedPage += 1;
    busy = false;
  }

  function fetchNextPage() {
    $.ajax({
      type: "GET",
      url: nextPageUrl,
      xhrFields: {
        withCredentials: true,
      },
      crossDomain: true,
      beforeSend: function () {
        $(".ow-no-notifications").addClass("ow-hide");
        $("#ow-notifications-loader").removeClass("ow-hide");
      },
      complete: function () {
        $("#ow-notifications-loader").addClass("ow-hide");
      },
      success: function (res) {
        nextPageUrl = res.next;
        if (res.count === 0 || (res.results.length === 0 && nextPageUrl === null)) {
          // If response does not have any notification, show no-notifications message.
          $(".ow-no-notifications").removeClass("ow-hide");
          $("#ow-mark-all-read").addClass("disabled");
          busy = false;
        } else {
          if (res.results.length === 0 && nextPageUrl !== null) {
            fetchNextPage();
          }
          fetchedPages.push(res.results);
          appendPage();
          // Enable filters
          $(".toggle-btn").removeClass("disabled");
        }
      },
      error: function (error) {
        busy = false;
        showNotificationDropdownError(
          gettext("Failed to fetch notifications. Try again later."),
        );
        throw error;
      },
    });
  }

  function pageDown() {
    busy = true;
    if (fetchedPages.length > lastRenderedPage) {
      appendPage();
    } else if (nextPageUrl !== null) {
      fetchNextPage();
    } else {
      busy = false;
    }
  }

  function pageUp() {
    busy = true;
    if (lastRenderedPage > renderedPages) {
      $(".ow-notification-wrapper div.page:last").remove();
      var addedDiv = pageContainer(fetchedPages[lastRenderedPage - renderedPages - 1]);
      $(".ow-notification-wrapper").prepend(addedDiv);
      lastRenderedPage -= 1;
    }
    busy = false;
  }

  function onUpdate() {
    if (!busy) {
      var scrollTop = $(".ow-notification-wrapper").scrollTop(),
        scrollBottom = scrollTop + $(".ow-notification-wrapper").innerHeight(),
        height = $(".ow-notification-wrapper")[0].scrollHeight;
      if (height * 0.9 <= scrollBottom) {
        pageDown();
      } else if (height * 0.1 >= scrollTop) {
        pageUp();
      }
    }
  }

  function notificationListItem(elem) {
    let klass;
    const datetime = dateTimeStampToDateTimeLocaleString(new Date(elem.timestamp));

    if (!notificationReadStatus.has(elem.id)) {
      if (elem.unread) {
        notificationReadStatus.set(elem.id, "unread");
      } else {
        notificationReadStatus.set(elem.id, "read");
      }
    }
    klass = notificationReadStatus.get(elem.id);

    let message;
    if (elem.description) {
      // Remove hyperlinks from generic notifications to enforce the opening of the message dialog
      message = elem.message.replace(/<a [^>]*>([^<]*)<\/a>/g, "$1");
    } else {
      message = convertMessageWithRelativeURL(elem.message);
    }

    return `<div class="ow-notification-elem ${klass}" id=ow-${elem.id}
                        data-location="${convertAbsoluteURLToRelativeURL(elem.target_url)}" role="link" tabindex="0">
                    <div class="ow-notification-inner">
                        <div class="ow-notification-meta">
                            <div class="ow-notification-level-wrapper">
                                <div class="ow-notify-${elem.level} icon"></div>
                                <div class="ow-notification-level-text">${elem.level}</div>
                            </div>
                            <div class="ow-notification-date">${datetime}</div>
                        </div>
                        ${message}
                    </div>
                </div>`;
  }

  function initNotificationWidget() {
    $(".ow-notification-wrapper").on("scroll", onUpdate);
    $(".ow-notification-wrapper").trigger("refreshNotificationWidget");
    $(".ow-notifications").off("click", initNotificationWidget);
  }

  function refreshNotificationWidget(
    e = null,
    url = "/api/v1/notifications/notification/",
  ) {
    $(".ow-notification-wrapper > div").remove(".page");
    fetchedPages.length = 0;
    lastRenderedPage = 0;
    nextPageUrl = getAbsoluteUrl(url);
    notificationReadStatus.clear();
    onUpdate();
  }

  function showNotificationDropdownError(message) {
    $("#ow-notification-dropdown-error").html(message);
    $("#ow-notification-dropdown-error-container").slideDown(1000);
    setTimeout(closeNotificationDropdownError, 10000);
  }

  function closeNotificationDropdownError() {
    $("#ow-notification-dropdown-error-container").slideUp(1000, function () {
      $("#ow-notification-dropdown-error").html("");
    });
  }

  $("#ow-notification-dropdown-error-container").on(
    "click mouseleave focusout",
    closeNotificationDropdownError,
  );

  $(".ow-notifications").on("click", initNotificationWidget);

  // Handler for marking all notifications read
  $("#ow-mark-all-read").click(function () {
    var unreads = $(".ow-notification-elem.unread");
    unreads.removeClass("unread");
    $("#ow-notification-count").hide();
    $.ajax({
      type: "POST",
      url: getAbsoluteUrl("/api/v1/notifications/notification/read/"),
      headers: {
        "X-CSRFToken": $('input[name="csrfmiddlewaretoken"]').val(),
      },
      xhrFields: {
        withCredentials: true,
      },
      crossDomain: true,
      success: function () {
        $("#ow-notification-count").remove();
      },
      error: function (error) {
        unreads.addClass("unread");
        $("#ow-notification-count").show();
        showNotificationDropdownError(
          gettext("Failed to mark notifications as unread. Try again later."),
        );
        throw error;
      },
    });
  });

  // Handler for marking notification as read and opening target url
  $(".ow-notification-wrapper").on(
    "click keypress",
    ".ow-notification-elem",
    function (e) {
      // Open target URL only when "Enter" key is pressed
      if (e.type === "keypress" && e.which !== 13) {
        return;
      }
      let elem = $(this);
      notificationHandler($, elem);
    },
  );

  // Close dialog on click, keypress or esc
  $(".ow-dialog-close").on("click keypress", function (e) {
    if (e.type === "keypress" && e.which !== 13 && e.which !== 27) {
      return;
    }
    $(".ow-overlay-notification").addClass("ow-hide");
    $(".ow-message-target-redirect").addClass("ow-hide");
  });

  // Handler for marking notification as read on mouseout event
  $(".ow-notification-wrapper").on(
    "mouseleave focusout",
    ".ow-notification-elem",
    function () {
      let elem = $(this);
      if (elem.hasClass("unread")) {
        markNotificationRead(elem.get(0));
      }
    },
  );
  $(".ow-notification-wrapper").bind(
    "refreshNotificationWidget",
    refreshNotificationWidget,
  );
}

function markNotificationRead(elem) {
  let elemId = elem.id.replace("ow-", "");
  try {
    document
      .querySelector(`#${elem.id}.ow-notification-elem`)
      .classList.remove("unread");
  } catch (error) {
    // no op
  }
  notificationReadStatus.set(elemId, "read");
  notificationSocket.send(
    JSON.stringify({
      type: "notification",
      notification_id: elemId,
    }),
  );
}

function notificationHandler($, elem) {
  var notification = fetchedPages
      .flat()
      .find((notification) => notification.id == elem.get(0).id.replace("ow-", "")),
    targetUrl = elem.data("location");

  // If notification is unread then send read request
  if (!notification.description && elem.hasClass("unread")) {
    markNotificationRead(elem.get(0));
  }

  if (notification.target_url && notification.target_url !== "#") {
    $(".ow-message-target-redirect").removeClass("ow-hide");
  }

  // Notification with overlay dialog
  if (notification.description) {
    var datetime = dateTimeStampToDateTimeLocaleString(
      new Date(notification.timestamp),
    );

    $(".ow-dialog-notification-level-wrapper").html(`
            <div class="ow-notification-level-wrapper">
                <div class="ow-notify-${notification.level} icon"></div>
                <div class="ow-notification-level-text">${notification.level}</div>
            </div>
            <div class="ow-notification-date">${datetime}</div>
        `);
    $(".ow-message-title").html(convertMessageWithRelativeURL(notification.message));
    $(".ow-message-description").html(notification.description);
    $(".ow-overlay-notification").removeClass("ow-hide");

    $(document).on("click", ".ow-message-target-redirect", function () {
      window.location = targetUrl;
    });
    // standard notification
  } else {
    window.location = targetUrl;
  }
}

function initWebSockets($) {
  notificationSocket.addEventListener("message", function (e) {
    let data = JSON.parse(e.data);
    if (data.type !== "notification") {
      return;
    }

    // Update notification count
    let countTag = $("#ow-notification-count");
    if (data.notification_count === 0) {
      countTag.remove();
    } else {
      // If unread tag is not present than insert it.
      // Otherwise, update innerHTML.
      if (countTag.length === 0) {
        let html = `<span id="ow-notification-count">${data.notification_count}</span>`;
        $(".ow-notifications").append(html);
      } else {
        countTag.html(data.notification_count);
      }
    }
    // Check whether to update notification widget
    if (data.reload_widget) {
      $(".ow-notification-wrapper").trigger("refreshNotificationWidget");
    }
    // Check whether to display notification toast
    if (data.notification) {
      let toast = $(`<div class="ow-notification-toast ${data.notification.level}"
                                data-location="${convertAbsoluteURLToRelativeURL(data.notification.target_url)}"
                                id="ow-${data.notification.id}">
                                <div class="icon ow-notify-close btn" role="button" tabindex="1"></div>
                                <div style="display:flex">
                                    <div class="icon ow-notify-${data.notification.level}"></div>
                                    ${data.notification.message}
                                </div>
                           </div>`);
      $(".ow-notification-toast-wrapper").prepend(toast);
      if (owNotificationWindow.canPlaySound()) {
        // Play notification sound only from authorized window
        notificationSound.currentTime = 0;
        notificationSound.play();
      }
      toast.slideDown("slow", function () {
        setTimeout(function () {
          toast.slideUp("slow", function () {
            toast.remove();
          });
        }, 30000);
      });
    }
  });
  // Make toast message clickable
  $(document).on("click", ".ow-notification-toast", function () {
    markNotificationRead($(this).get(0));
    notificationHandler($, $(this));
  });
  $(document).on(
    "click",
    ".ow-notification-toast .ow-notify-close.btn",
    function (event) {
      event.stopPropagation();
      let toast = $(this).parent();
      markNotificationRead(toast.get(0));
      toast.slideUp("slow");
    },
  );
}

function getAbsoluteUrl(url) {
  return notificationApiHost.origin + url;
}

function dateTimeStampToDateTimeLocaleString(dateTimeStamp) {
  let date = dateTimeStamp.toLocaleDateString(userLanguage, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }),
    time = dateTimeStamp.toLocaleTimeString(userLanguage, {
      hour: "numeric",
      minute: "numeric",
    }),
    at = gettext("at"),
    dateTimeString = `${date} ${at} ${time}`;
  return dateTimeString;
}
