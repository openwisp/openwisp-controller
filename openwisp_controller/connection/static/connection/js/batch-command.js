"use strict";

const DEFAULT_PER_PAGE = 20;
const FILTERED_REFRESH_DELAY = 1000;
const DEVICE_URL_PLACEHOLDER = "00000000-0000-0000-0000-000000000000";
let filteredRefreshTimeout = null;

django.jQuery(function ($) {
  const batchCommandWebSocket = new ReconnectingWebSocket(getWebSocketUrl(), null, {
    debug: false,
    automaticOpen: false,
    timeoutInterval: 7000,
  });
  batchCommandWebSocket.addEventListener("open", function () {
    requestCurrentState($, batchCommandWebSocket);
  });
  batchCommandWebSocket.addEventListener("message", function (e) {
    const data = JSON.parse(e.data);
    if (data.type === "command_update") {
      handleCommandMessage($, data, batchCommandWebSocket);
    } else if (data.type === "batch_status") {
      handleBatchStatusMessage($, data, batchCommandWebSocket);
    } else if (data.type === "batch_state") {
      handleBatchStateMessage($, data);
    }
  });
  batchCommandWebSocket.open();
  // exposed so that a reconnect can be triggered from the browser tests
  window.batchCommandWebSocket = batchCommandWebSocket;
});

function getWebSocketUrl() {
  return `${getWebSocketProtocol()}${owControllerApiHost.host}/ws/controller/batch-command/${batchCommandId}`;
}

function getWebSocketProtocol() {
  let protocol = "ws://";
  if (window.location.protocol === "https:") {
    protocol = "wss://";
  }
  return protocol;
}

function requestCurrentState($, websocket) {
  if (websocket.readyState !== WebSocket.OPEN) {
    return;
  }
  try {
    websocket.send(
      JSON.stringify({
        type: "request_current_state",
        batch_id: batchCommandId,
        page: getCurrentPage($),
        filters: getActiveFilters(),
      }),
    );
  } catch (error) {
    console.error("Error requesting current batch state:", error);
  }
}

function handleCommandMessage($, data, websocket) {
  updateTotals($, data.affected_devices, data.total_rows);
  renderCommand($, data);
  announceUpdate(
    $,
    interpolate(
      gettext("Updated %(device)s: %(status)s"),
      {
        device: data.device_name,
        status: getStatusLabel(data.status),
      },
      true,
    ),
  );
  if (hasActiveFilters()) {
    scheduleFilteredRefresh($, websocket);
  }
}

function scheduleFilteredRefresh($, websocket) {
  if (!websocket || filteredRefreshTimeout) {
    return;
  }
  filteredRefreshTimeout = setTimeout(function () {
    filteredRefreshTimeout = null;
    requestCurrentState($, websocket);
  }, FILTERED_REFRESH_DELAY);
}

function getStatusLabel(status) {
  const element = document.getElementById("batch-status-labels");
  const labels = element ? JSON.parse(element.textContent) : {};
  return labels[status] || status;
}

function getFormattedDateTimeString(dateTimeString) {
  if (!dateTimeString) {
    return "-";
  }
  const formattedString = new Date(dateTimeString).strftime("%B %d, %Y %I:%M %p"),
    stringArray = formattedString.split(" ");
  stringArray[0] = stringArray[0].substring(0, 4) + ".";
  stringArray[4] = stringArray[4] == "AM" ? "a.m." : "p.m.";
  return stringArray.join(" ");
}

function handleBatchStatusMessage($, data, websocket) {
  const $status = $(".field-colored_status .readonly .command-status");
  if ($status.length && data.status) {
    $status
      .removeClass()
      .addClass("command-status " + data.status)
      .text(getStatusLabel(data.status));
  }
  updateSkippedDevices($, data);
  updateTotals($, data.affected_devices, data.total_rows);
  if (data.status) {
    announceUpdate(
      $,
      interpolate(
        gettext("Mass command status: %(status)s"),
        {
          status: getStatusLabel(data.status),
        },
        true,
      ),
    );
  }
  const $table = $("#result_list");
  if (
    websocket &&
    data.skipped_count &&
    data.skipped_count !== $table.data("skippedCount")
  ) {
    $table.data("skippedCount", data.skipped_count);
    requestCurrentState($, websocket);
  }
}

function updateSkippedDevices($, data) {
  if (!data.skipped_count) {
    return;
  }
  let $list = $(".field-display_skipped_devices .skipped-devices-list");
  if (!$list.length) {
    const $readonly = $(".field-display_skipped_devices .readonly");
    if (!$readonly.length) {
      return;
    }
    $list = $("<div>").addClass("skipped-devices-list");
    $readonly.empty().append($list);
  }
  $list.empty().append(document.createTextNode(String(data.skipped_count)));
  const rows = data.skipped_preview || [];
  rows.forEach(function (row, index) {
    if (index === rows.length - 1 && rows.length < data.skipped_count) {
      $list.append($("<br>")).append(document.createTextNode("\u2026"));
    }
    $list
      .append($("<br>"))
      .append(document.createTextNode(row.device_name + ": " + row.output));
  });
}

function handleBatchStateMessage($, data) {
  if (data.page) {
    $("#result_list").attr("data-current-page", data.page);
  }
  if (data.batch_status) {
    handleBatchStatusMessage($, data.batch_status);
  }
  updateTotals(
    $,
    data.batch_status ? data.batch_status.affected_devices : null,
    data.total_rows,
    true,
  );
  if (!data.commands || !Array.isArray(data.commands)) {
    return;
  }
  // the snapshot is built with the filters this page is showing, so it is the
  // authoritative content of the table: rows missing from it no longer belong
  reconcileRows($, data.commands);
}

function reconcileRows($, commands) {
  const devices = {};
  commands.forEach(function (command) {
    devices[String(command.device)] = true;
    const $row = $("#batch-command-row-" + command.device);
    if ($row.length) {
      updateRow($, $row, command);
    } else {
      insertRow($, command);
    }
  });
  $("#result_list tbody tr[data-device-pk]").each(function () {
    if (!devices[String($(this).data("device-pk"))]) {
      $(this).remove();
    }
  });
  if (!commands.length && !$("#result_list td.empty-results").length) {
    $("#result_list tbody").append(
      $("<tr>").append(
        $("<td>")
          .attr("colspan", 4)
          .addClass("empty-results")
          .text(gettext("No commands found.")),
      ),
    );
  }
}

function announceUpdate($, message) {
  $("#batch-command-live-status").text(message);
}

function renderCommand($, data) {
  const $row = $("#batch-command-row-" + data.device);
  if ($row.length) {
    updateRow($, $row, data);
  } else if (belongsOnCurrentPage($, data)) {
    insertRow($, data);
  }
  // otherwise the row is on another page, the server renders it there
}

// The server sends the position of newly created results only, the page is
// worked out here from the size the table was rendered with: this keeps the
// first page at "per page" rows while the paginator keeps growing.
function belongsOnCurrentPage($, data) {
  // with a filter on, the pushed totals are unfiltered and page boundaries
  // cannot be worked out
  if (hasActiveFilters()) {
    return false;
  }
  if (data.index == null) {
    return false;
  }
  const renderedRows = $("#result_list tbody tr").not(":has(td.empty-results)").length;
  if (renderedRows >= getPerPage($)) {
    return false;
  }
  // the paginator is 1-based, so position 0 is on page 1
  return Math.floor(data.index / getPerPage($)) + 1 === getCurrentPage($);
}

function updateRow($, $row, data) {
  const activeFilter = getActiveStatusFilter($);
  if (activeFilter && activeFilter !== data.status) {
    $row.remove();
    return;
  }
  $row
    .find(".command-status")
    .removeClass()
    .addClass("command-status " + data.status)
    .text(getStatusLabel(data.status));
  $row.find(".command-output pre").text(data.output || "-");
  $row.find("td:last-child").text(getFormattedDateTimeString(data.modified));
}

function insertRow($, data) {
  $("#result_list td.empty-results").closest("tr").remove();
  const $tableBody = $("#result_list tbody");
  const rowClass = $tableBody.find("tr").length % 2 === 0 ? "row1" : "row2";
  const $row = $("<tr>").attr({
    id: "batch-command-row-" + data.device,
    "data-device-pk": data.device,
    class: rowClass,
  });
  if (data.is_skipped) {
    $row.append(
      $("<td>").append(
        $("<span>").addClass("device-name-disabled").text(data.device_name),
      ),
    );
  } else {
    $row.append(
      $("<td>").append(
        $("<a>")
          .attr({
            href: getDeviceChangeUrl($, data.device),
            class: "device-link",
          })
          .text(data.device_name),
      ),
    );
  }
  $row.append(
    $("<td>").append(
      $("<span>")
        .addClass("command-status " + data.status)
        .text(getStatusLabel(data.status)),
    ),
  );
  $row.append(
    $("<td>")
      .addClass("command-output")
      .append($("<pre>").text(data.output || "-")),
  );
  $row.append($("<td>").text(getFormattedDateTimeString(data.modified)));
  $tableBody.append($row);
}

function updateTotals($, affectedDevices, totalRows, filtered) {
  if (affectedDevices != null) {
    const $affected = $(".field-affected_devices .readonly");
    if ($affected.length) {
      $affected.text(String(affectedDevices));
    }
  }
  // pushed totals are not filtered, only the reconnect snapshot is
  if (totalRows == null || (!filtered && hasActiveFilters())) {
    return;
  }
  const $paginator = $(".results-container .paginator");
  if ($paginator.length) {
    $paginator.text(
      interpolate(ngettext("%s command", "%s commands", totalRows), [totalRows]),
    );
  }
  renderPagination($, totalRows);
}

function renderPagination($, totalRows) {
  const currentPage = getCurrentPage($);
  const perPage = getPerPage($);
  const totalPages = Math.max(1, Math.ceil(totalRows / perPage));
  $(".results-container .pagination").remove();
  if (totalPages <= 1) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  params.delete("page");
  const baseQuery = params.toString();
  const buildHref = function (page) {
    return "?" + (baseQuery ? baseQuery + "&page=" + page : "page=" + page);
  };
  const $stepLinks = $("<span>").addClass("step-links");
  if (currentPage > 1) {
    $stepLinks.append(
      $("<a>")
        .attr("href", buildHref(currentPage - 1))
        .text(gettext("Previous")),
    );
  }
  $stepLinks.append(
    $("<span>")
      .addClass("current-page")
      .text(
        interpolate(
          gettext("Page %(current)s of %(total)s"),
          { current: currentPage, total: totalPages },
          true,
        ),
      ),
  );
  if (currentPage < totalPages) {
    $stepLinks.append(
      $("<a>")
        .attr("href", buildHref(currentPage + 1))
        .text(gettext("Next")),
    );
  }
  $("<div>").addClass("pagination").append($stepLinks).appendTo(".results-container");
}

function getDeviceChangeUrl($, devicePk) {
  const template = $("#result_list").attr("data-device-url");
  if (!template) {
    return "#";
  }
  return template.replace(DEVICE_URL_PLACEHOLDER, devicePk) + "#command_set-2-group";
}

function getActiveStatusFilter($) {
  return $("#result_list").attr("data-active-status") || "";
}

function getActiveFilters() {
  const params = new URLSearchParams(window.location.search);
  const filters = {};
  ["q", "status", "location_id", "group_id", "organization_id"].forEach(
    function (name) {
      filters[name] = params.get(name) || "";
    },
  );
  return filters;
}

function hasActiveFilters() {
  const filters = getActiveFilters();
  return Object.keys(filters).some(function (name) {
    return !!filters[name];
  });
}

function getCurrentPage($) {
  return parseInt($("#result_list").attr("data-current-page"), 10) || 1;
}

function getPerPage($) {
  return parseInt($("#result_list").attr("data-per-page"), 10) || DEFAULT_PER_PAGE;
}
