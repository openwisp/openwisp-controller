"use strict";

// admin/change_form.html loads the translation catalog, these fallbacks only
// keep the page working if it ever fails to load
var gettext =
  window.gettext ||
  function (word) {
    return word;
  };
var ngettext =
  window.ngettext ||
  function (singular, plural, count) {
    return count === 1 ? singular : plural;
  };
var interpolate =
  window.interpolate ||
  function (fmt, args) {
    return fmt.replace(/%s/g, function () {
      return args.shift();
    });
  };

django.jQuery(function ($) {
  if (
    typeof owControllerApiHost === "undefined" ||
    typeof batchCommandId === "undefined"
  ) {
    return;
  }
  const batchCommandWebSocket = new ReconnectingWebSocket(
    getWebSocketUrl(),
    null,
    {
      debug: false,
      automaticOpen: false,
      // The library re-connects if it fails to establish a connection in "timeoutInterval".
      // On slow internet connections, the default value of "timeoutInterval" will
      // keep terminating and re-establishing the connection.
      timeoutInterval: 7000,
    },
  );
  batchCommandWebSocket.addEventListener("open", function () {
    requestCurrentState(batchCommandWebSocket);
  });

  batchCommandWebSocket.addEventListener("message", function (e) {
    let data = JSON.parse(e.data);
    if (data.model === "Command") {
      handleCommandMessage($, data.data);
    } else if (data.model === "BatchCommand") {
      handleBatchCommandMessage($, data.data);
    } else if (data.model === "BatchState") {
      handleBatchStateMessage($, data.data);
    }
  });

  // "automaticOpen: false" above means the socket never connects unless
  // .open() is called explicitly (mirrors commands.js's initCommandWebSockets).
  batchCommandWebSocket.open();

  function getWebSocketUrl() {
    let protocol = getWebSocketProtocol();
    return `${protocol}${owControllerApiHost.host}/ws/controller/batch-command/${batchCommandId}`;
  }

  function getWebSocketProtocol() {
    let protocol = "ws://";
    if (window.location.protocol === "https:") {
      protocol = "wss://";
    }
    return protocol;
  }

  function requestCurrentState(websocket) {
    if (websocket.readyState === WebSocket.OPEN) {
      try {
        websocket.send(
          JSON.stringify({
            type: "request_current_state",
            batch_id: batchCommandId,
            // only the page being shown is sent back, a mass command can
            // target thousands of devices
            page: getCurrentPage(),
          }),
        );
      } catch (error) {
        console.error("Error requesting current batch state:", error);
      }
    }
  }

  function handleBatchStateMessage($, data) {
    if (data.batch_status) {
      handleBatchCommandMessage($, data.batch_status);
    }
    updateTotals(
      $,
      data.batch_status ? data.batch_status.affected_devices : null,
      data.total_rows,
    );
    if (data.commands && Array.isArray(data.commands)) {
      // These are the results of the page being shown, selected as such by
      // the server, so they are drawn unconditionally: running them through
      // the eligibility test used for live messages would reject them, since
      // an individual result carries no page of its own.
      data.commands.forEach(function (command) {
        let $row = $("#batch-command-row-" + command.device);
        if ($row.length) {
          updateRow($, $row, command);
        } else {
          insertRow($, command);
        }
      });
    }
  }

  function getActiveStatusFilter() {
    return $("#result_list").attr("data-active-status") || "";
  }

  function getCurrentPage() {
    return parseInt($("#result_list").attr("data-current-page"), 10) || 1;
  }

  function getPerPage() {
    return parseInt($("#result_list").attr("data-per-page"), 10) || 20;
  }

  function handleCommandMessage($, data) {
    // The totals are updated on every message, whatever happens to the DOM
    // afterwards. They used to be updated at the end of insertRow(), which
    // returns early once the page is full, so the counter and the paginator
    // silently froze as soon as the first page filled up.
    updateTotals($, data.affected_devices, data.total_rows);
    renderCommand($, data);
  }

  function renderCommand($, data) {
    let $row = $("#batch-command-row-" + data.device);
    if ($row.length) {
      updateRow($, $row, data);
    } else if (belongsOnCurrentPage($, data)) {
      insertRow($, data);
    }
    // otherwise the row belongs to another page and is left alone: it will
    // be rendered by the server when that page is opened
  }

  /*
   * The server states the page a result belongs to, and only does so for
   * results it has just created. Draw it when that is the page being shown
   * and it still has room, which is what makes the first page stop at "per
   * page" rows while the paginator keeps growing, without moving the user.
   *
   * The page cannot be derived here from the total number of results: the
   * total describes the whole batch, not the position of this result. A
   * status change on the third result still arrives with the total of the
   * batch, and would be placed on the last page instead of being left alone.
   */
  function belongsOnCurrentPage($, data) {
    // with a filter on, the totals pushed over the websocket are unfiltered
    // and cannot be used to work out page boundaries
    if (getActiveStatusFilter()) {
      return false;
    }
    if (data.page == null) {
      // a status change, not a new result: it is either already displayed
      // or it lives on another page
      return false;
    }
    let renderedRows = $("#result_list tbody tr").not(
      ":has(td.empty-results)",
    ).length;
    if (renderedRows >= getPerPage()) {
      return false;
    }
    return data.page === getCurrentPage();
  }

  function updateRow($, $row, data) {
    let activeFilter = getActiveStatusFilter();
    if (activeFilter && activeFilter !== data.status) {
      // the row no longer matches the filter the page was rendered with
      $row.remove();
      return;
    }
    let $status = $row.find(".command-status");
    $status
      .removeClass()
      .addClass("command-status " + data.status)
      .text(data.status_display);
    $row.find(".command-output pre").text(data.output || "-");
    $row.find("td:last-child").text(formatTimestamp(data.created));
  }

  // Only draws the row: whether it should be drawn at all is decided by
  // belongsOnCurrentPage(), and the totals are updated independently.
  function insertRow($, data) {
    // remove the "No commands found." empty state
    $("#result_list td.empty-results").closest("tr").remove();
    let $tableBody = $("#result_list tbody");
    let rowClass = $tableBody.find("tr").length % 2 === 0 ? "row1" : "row2";
    let $row = $("<tr>").attr({
      id: "batch-command-row-" + data.device,
      "data-device-pk": data.device,
      class: rowClass,
    });
    let $deviceTd = $("<td>").append(
      $("<a>")
        .attr({ href: getDeviceChangeUrl(data.device), class: "device-link" })
        .text(data.device_name),
    );
    $row.append($deviceTd);
    $row.append(
      $("<td>").append(
        $("<span>")
          .addClass("command-status " + data.status)
          .text(data.status_display),
      ),
    );
    $row.append(
      $("<td>")
        .addClass("command-output")
        .append($("<pre>").text(data.output || "-")),
    );
    $row.append($("<td>").text(formatTimestamp(data.created)));
    $tableBody.append($row);
  }

  function getDeviceChangeUrl(devicePk) {
    let template = $("#result_list").attr("data-device-url");
    if (!template) {
      return "#";
    }
    return template.replace("00000000-0000-0000-0000-000000000000", devicePk);
  }

  /*
   * "affected_devices" counts Command rows, "total_rows" also counts the
   * skipped devices the table paginates alongside them. They are two
   * different numbers and drive two different things: passing one for both
   * makes the page count too small and the last page unreachable whenever a
   * device was skipped.
   *
   * Both are authoritative values recomputed server side on every send,
   * never a client tracked delta, so a missed or duplicate message cannot
   * desync them permanently.
   */
  function updateTotals($, affectedDevices, totalRows) {
    if (affectedDevices != null) {
      let $affected = $(".field-affected_devices .readonly");
      if ($affected.length) {
        $affected.text(String(affectedDevices));
      }
    }
    if (totalRows == null) {
      return;
    }
    // counts are filtered server side, the totals pushed here are not
    if (getActiveStatusFilter()) {
      return;
    }
    let $paginator = $(".results-container .paginator");
    if ($paginator.length) {
      $paginator.text(
        interpolate(ngettext("%s command", "%s commands", totalRows), [
          totalRows,
        ]),
      );
    }
    renderPagination($, totalRows);
  }

  /*
   * Rebuilt from scratch rather than patched, so there is a single code
   * path whether or not the widget was rendered by the server. Patching
   * only the "Page X of Y" label used to leave the last page without a
   * "Next" link: at "3 of 3" growing to "3 of 5" the label changed but
   * there was still no way to move forward.
   *
   * This only touches the pagination widget, never the rows: the user is
   * never navigated automatically, and no page is ever re-fetched.
   */
  function renderPagination($, totalRows) {
    let currentPage = getCurrentPage();
    let perPage = getPerPage();
    let totalPages = Math.max(1, Math.ceil(totalRows / perPage));
    $(".results-container .pagination").remove();
    if (totalPages <= 1) {
      return;
    }
    let pageLabel =
      gettext("Page") +
      " " +
      currentPage +
      " " +
      gettext("of") +
      " " +
      totalPages;
    let params = new URLSearchParams(window.location.search);
    params.delete("page");
    let baseQuery = params.toString();
    let buildHref = function (page) {
      return "?" + (baseQuery ? baseQuery + "&page=" + page : "page=" + page);
    };
    let $stepLinks = $("<span>").addClass("step-links");
    if (currentPage > 1) {
      $stepLinks.append(
        $("<a>")
          .attr("href", buildHref(currentPage - 1))
          .text(gettext("Previous")),
      );
    }
    $stepLinks.append($("<span>").addClass("current-page").text(pageLabel));
    if (currentPage < totalPages) {
      $stepLinks.append(
        $("<a>")
          .attr("href", buildHref(currentPage + 1))
          .text(gettext("Next")),
      );
    }
    $("<div>")
      .addClass("pagination")
      .append($stepLinks)
      .appendTo(".results-container");
  }

  function handleBatchCommandMessage($, data) {
    let $status = $(".field-colored_status .readonly .command-status");
    if ($status.length && data.status && data.status_display) {
      $status
        .removeClass()
        .addClass("command-status " + data.status)
        .text(data.status_display);
    }
    if (data.skipped_devices && Object.keys(data.skipped_devices).length) {
      let $list = $(".field-display_skipped_devices .skipped-devices-list");
      if ($list.length) {
        let $first = $list.contents().first();
        if ($first.length && $first[0].nodeType === 3) {
          $first[0].textContent = Object.keys(data.skipped_devices).length;
        }
      }
    }
  }

  function formatTimestamp(iso) {
    if (!iso) {
      return "-";
    }
    let date = new Date(iso);
    if (isNaN(date.getTime())) {
      return "-";
    }
    return date.toLocaleString();
  }
});
