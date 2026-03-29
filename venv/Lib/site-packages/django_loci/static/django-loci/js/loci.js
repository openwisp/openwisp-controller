/*global
alert, confirm, console, Debug, opera, prompt, WSH
*/
/*
this JS is shared between:
    - DeviceLocationForm
    - LocationForm
*/
django.jQuery(function ($) {
  "use strict";

  var $outdoor = $(".loci.coords"),
    $indoor = $(".indoor.coords"),
    $allSections = $(".coords"),
    $geoEdit = $(
      ".field-name, .field-type, .field-is_mobile, " +
        ".field-address, .field-geometry",
      ".loci.coords",
    ),
    $indoorRows = $(".indoor.coords .form-row:not(.field-indoor)"),
    $indoorEdit = $(".indoor.coords .form-row:not(.field-floorplan_selection)"),
    $indoorPositionRow = $(".indoor.coords .field-indoor"),
    geometryId = $(".field-geometry label").attr("for") || "geometry", // fallback for readonly
    mapName = "leafletmap" + geometryId + "-map",
    loadMapName = "loadmap" + geometryId + "-map",
    $typeRow = $(".inline-group .field-type"),
    $type = $typeRow.find("select"),
    $isMobile = $(
      ".coords .field-is_mobile input, #location_form .field-is_mobile input",
    ),
    $locationSelectionRow = $(".field-location_selection"),
    $locationSelection = $locationSelectionRow.find("select"),
    $locationRow = $(".loci.coords .field-location"),
    $location = $locationRow.find("select, input"),
    $locationLabel = $(".field-location .item-label"),
    $name = $(".field-name input", ".loci.coords"),
    $address = $(".coords .field-address input, #location_form .field-address input"),
    $geometryTextarea = $(".field-geometry textarea"),
    baseLocationJsonUrl = $("#loci-location-json-url").attr("data-url"),
    baseLocationFloorplansJsonUrl = $("#loci-location-floorplans-json-url").attr(
      "data-url",
    ),
    $geometryRow = $geometryTextarea.parents(".form-row"),
    msg = gettext("Location data not received yet"),
    $noLocationDiv = $(".no-location", ".loci.coords"),
    $floorplanSelectionRow = $(".indoor.coords .field-floorplan_selection"),
    $floorplanSelection = $floorplanSelectionRow.find("select"),
    $floorplanRow = $(".indoor .field-floorplan"),
    $floorplan = $floorplanRow.find("select").eq(0),
    $floorplanImage = $(".indoor.coords .field-image input"),
    $floorplanMap = $(".indoor.coords .floorplan-widget"),
    isNew = true,
    $addressInput = $(".field-address input"),
    $mapGeojsonTextarea = $(".django-leaflet-raw-textarea"),
    $oldLat,
    $oldLng,
    $coordsUrl = $("#loci-geocode-url").attr("data-url"),
    $addrUrl = $("#loci-reverse-geocode-url").attr("data-url");

  // define dummy gettext if django i18n is not enabled
  if (!gettext) {
    window.gettext = function (text) {
      return text;
    };
  }

  function getLocationJsonUrl(pk) {
    return baseLocationJsonUrl.replace("00000000-0000-0000-0000-000000000000", pk);
  }

  function getLocationFloorplansJsonUrl(pk) {
    return baseLocationFloorplansJsonUrl.replace(
      "00000000-0000-0000-0000-000000000000",
      pk,
    );
  }

  function getMap() {
    return window[mapName];
  }

  function invalidateMapSize() {
    var map = getMap();
    if (map) {
      map.invalidateSize();
    }
    return map;
  }

  function resetOutdoorForm(keepLocationSelection) {
    $locationSelectionRow.show();
    if (!keepLocationSelection) {
      $type.val("");
    }
    $location.val("");
    $locationLabel.text("");
    $isMobile.prop("checked", false);
    $name.val("");
    $address.val("");
    $geometryTextarea.val("");
    $geoEdit.hide();
    $locationRow.hide();
    $locationSelection.show();
    $noLocationDiv.hide();
  }

  function resetIndoorForm(keepFloorplanSelection) {
    if (!keepFloorplanSelection) {
      $indoor.hide();
      $floorplanSelection.val("");
    }
    $indoorRows.hide();
    $floorplanSelectionRow.show();
    // reset values
    $indoorEdit.find("input,select").val("");
  }

  function resetDeviceLocationForm() {
    resetOutdoorForm();
    resetIndoorForm();
  }

  function indoorForm(selection) {
    // fallbacks for view only users
    var type = $type.val() || $typeRow.find(".readonly").text(),
      floorplanValue =
        $floorplanSelection.val() || $floorplanSelectionRow.find(".readonly").text(),
      locationSelectionValue =
        $locationSelection.val() || $locationSelectionRow.find(".readonly").text();
    if (type !== "indoor") {
      return;
    }
    $indoorPositionRow.hide();
    $indoor.show();
    if (!selection) {
      $indoorRows.hide();
      $floorplanSelectionRow.show();
    } else if (selection === "new") {
      $indoorRows.show();
      $floorplan.val("");
      $floorplanRow.hide();
    }
    if (locationSelectionValue === "new") {
      $floorplanSelection.val("new");
      $floorplanSelectionRow.hide();
    }
    if (!floorplanValue) {
      $indoorRows.hide();
      $floorplanSelectionRow.show();
    }
  }

  function locationSelectionChange(e, initial) {
    // get value from 'readonly' in case of view only permissions
    var value =
      $locationSelection.val() || $locationSelectionRow.find(".readonly").text();
    $allSections.hide();
    if (!initial) {
      resetDeviceLocationForm();
    }
    if (value === "new") {
      $outdoor.show();
      $typeRow.show();
      indoorForm(value);
    } else if (value === "existing") {
      $outdoor.show();
      $locationRow.show();
    }
  }

  function isMobileChange() {
    var rows = [$address, $geometryTextarea];
    if ($isMobile.prop("checked")) {
      $(rows).each(function (i, el) {
        if (!$(el).val()) {
          $(el).parents(".form-row").hide();
        }
      });
      // name not relevant in mobile locations
      $name.parents(".form-row").hide();
      if (!$geometryTextarea.val()) {
        $(".no-location").show();
      }
    } else {
      $(rows).each(function (i, el) {
        $(el).parents(".form-row").show();
      });
      $name.parents(".form-row").show();
      $(".no-location").hide();
    }
  }

  function typeChange(e, initial) {
    // get value from 'readonly' in case of view only permissions
    var value = $type.val() || $typeRow.find(".readonly").text(),
      // floorplansLength for choice field includes the placeholder option so
      // need to subtract it.
      floorplansLength = $floorplan.find("option").length - 1;
    if (value) {
      $outdoor.show();
      $geoEdit.show();
      invalidateMapSize();
      isMobileChange();
    } else {
      $geoEdit.hide();
      $indoor.hide();
      $typeRow.show();
    }
    if (value === "indoor") {
      $indoor.show();
      indoorForm($locationSelection.val());
    } else if (value === "outdoor" && floorplansLength >= 1) {
      // Confirm deletion on switching indoor to outdoor, if floorplans exist
      var msg = gettext(
        "This location has floorplans associated to it. " +
          "Converting it to outdoor will remove all these floorplans, " +
          "affecting all devices related to this location. " +
          "Do you want to proceed?",
      );
      if (!confirm(msg)) {
        $type.val("indoor");
        return;
      }
      $indoor.hide();
    } else {
      $indoor.hide();
    }
  }

  function floorplanSelectionChange(e, initial) {
    // fallbacks for view only users
    var value =
        $floorplanSelection.val() || $floorplanSelectionRow.find(".readonly").text(),
      optionsLength =
        $floorplan.find("option").length ||
        $floorplanSelectionRow.find(".readonly").length;
    // do not reset indoor form at first load
    if (!initial) {
      resetIndoorForm(true);
    }
    indoorForm(value);
    // optionslength includes the placeholder option
    if (value === "existing" && optionsLength >= 1) {
      $floorplanRow.show();
      // if no floorplan available, make it obvious
    } else if (value === "existing" && optionsLength < 1) {
      alert(gettext("This location has no floorplans available yet"));
      $floorplanSelection.val("");
    }
  }

  // HACK to override `dismissRelatedLookupPopup()` and
  // `dismissAddAnotherPopup()` in Django's RelatedObjectLookups.js to
  // trigger change event when an ID is selected or added via popup.
  function triggerChangeOnField(win, chosenId) {
    // In Django 4.2, the popup index is appended to the window name.
    // Hence, we remove that before selecting the element.
    $(document.getElementById(win.name.replace(/__\d+$/, ""))).change();
  }
  window.ORIGINAL_dismissRelatedLookupPopup = window.dismissRelatedLookupPopup;
  window.dismissRelatedLookupPopup = function (win, chosenId) {
    window.ORIGINAL_dismissRelatedLookupPopup(win, chosenId);
    triggerChangeOnField(win, chosenId);
  };
  window.ORIGINAL_dismissAddAnotherPopup = window.dismissAddAnotherPopup;
  window.dismissAddAnotherPopup = function (win, chosenId) {
    window.ORIGINAL_dismissAddAnotherPopup(win, chosenId);
    triggerChangeOnField(win, chosenId);
  };

  $type.change(typeChange);
  typeChange(null, true);

  $locationSelection.change(locationSelectionChange);
  locationSelectionChange(null, true);

  function locationChange(e, initial) {
    function loadIndoor() {
      indoorForm();
      // fallback for view only users
      var type = $type.val() || $typeRow.find(".readonly").text();
      if (type !== "indoor") {
        $indoor.hide();
        return;
      }
      var floorplansUrl = getLocationFloorplansJsonUrl($location.val());
      $.getJSON(floorplansUrl, function (data) {
        var $current = $floorplan.find("option:selected"),
          currentValue = $current.val();
        $floorplan.find('option[value!=""]').remove();
        $(data.choices).each(function (i, el) {
          var o = $("<option></option>")
            .attr("value", el.id)
            .text(el.str)
            .data("floor", el.floor)
            .data("image", el.image)
            .data("image_width", el.image_width)
            .data("image_height", el.image_height);
          if (el.id === currentValue) {
            o.attr("selected", "selected");
          }
          $floorplan.append(o);
        });
      });
    }
    $typeRow.show();
    if (!initial) {
      // update location fields
      var url = getLocationJsonUrl($location.val());
      $.getJSON(url, function (data) {
        $locationLabel.text(data.name);
        $name.val(data.name);
        $type.val(data.type);
        $isMobile.prop("checked", data.is_mobile);
        $address.val(data.address);
        $geometryTextarea.val(data.geometry ? JSON.stringify(data.geometry) : "");
        var map = getMap();
        if (map) {
          map.remove();
        }
        $geoEdit.show();
        window[loadMapName]();
        isMobileChange();
        loadIndoor();
      });
    } else {
      loadIndoor();
    }
  }

  // listen to change events
  // although these events are being artificially triggered
  // see the override of dismissRelatedLookupPopup above
  $location.change(locationChange);
  // initial set up
  locationChange(null, true);

  $isMobile.change(isMobileChange);

  $floorplanSelection.change(floorplanSelectionChange);
  floorplanSelectionChange(null, true);

  $floorplan.change(function () {
    // reset floorplan data if no floorplan is chosen
    if (!$floorplan.val()) {
      resetIndoorForm(true);
      $indoorRows.show();
      $indoorEdit.hide();
      $floorplanRow.show();
      return;
    }
    var option = $floorplan.find("option:selected"),
      widgetName = $floorplanMap
        .parents(".field-indoor")
        .find(".floorplan-widget")
        .attr("id")
        .replace("id_", "")
        .replace("_map", ""),
      globalName = "django-loci-floorplan-" + widgetName,
      image = option.data("image"),
      $a = $indoor.find(".field-image a"),
      $aText = $a.text(),
      $aNewText = $aText.split(": ")[0] + ": " + image.split("/").slice(-1);
    $indoor.find(".field-floor input").val(option.data("floor"));
    $indoor.find(".form-row:not(.field-floorplan_selection)").show();
    $a.attr("href", image).text($aNewText);
    // remove previous indoor map if present
    if (window[globalName]) {
      window[globalName].remove();
    }
    window[globalName] = django.loadFloorPlan(
      widgetName,
      image,
      option.data("image_width"),
      option.data("image_height"),
    );
  });

  $floorplanImage.change(function () {
    var input = this,
      reader = new FileReader(),
      image = new Image(),
      $indoorRow = $floorplanMap.parents(".field-indoor"),
      widgetName = $indoorRow
        .find(".floorplan-widget")
        .attr("id")
        .replace("id_", "")
        .replace("_map", ""),
      globalName = "django-loci-floorplan-" + widgetName;
    if (!input.files || !input.files[0]) {
      return;
    }
    reader.onload = function (e) {
      image.src = e.target.result;
      image.onload = function () {
        $indoorRow.show();
        // remove previous indoor map if present
        if (window[globalName]) {
          window[globalName].remove();
        }
        window[globalName] = django.loadFloorPlan(
          widgetName,
          this.src,
          this.width,
          this.height,
        );
      };
    };
    reader.readAsDataURL(input.files[0]);
  });

  $("#content-main form").submit(function (e) {
    var indoorPosition = $(".field-indoor .floorplan-raw input").val(),
      typeSelect = $type.find("option").length
        ? $type
        : $(".module.aligned .field-type").find("select");
    if (isNew && $type.val() === "indoor" && !indoorPosition) {
      var message = gettext(
        "You have set this location as indoor but have " +
          "not specified indoor cordinates on a floorplan, " +
          "do you want to save anyway?",
      );
      if (!confirm(message)) {
        e.preventDefault();
      } else {
        $floorplanSelection.val("");
        indoorForm();
      }
    }
  });

  // websocket for mobile coords
  function listenForLocationUpdates(pk) {
    var host = window.location.host,
      protocol = window.location.protocol === "http:" ? "ws" : "wss",
      ws = new ReconnectingWebSocket(
        protocol + "://" + host + "/ws/loci/location/" + pk + "/",
      );
    ws.onmessage = function (e) {
      const data = JSON.parse(e.data);
      $geometryRow.show();
      $noLocationDiv.hide();
      $geometryTextarea.val(JSON.stringify(data.geometry));
      $address.val(data.address);
      getMap().remove();
      window[loadMapName]();
    };
  }

  // returns marker or featureGroup
  function getMarkerFeatureGroup(option) {
    var map = getMap(),
      layer;
    map.eachLayer(function (lay) {
      if (lay.hasOwnProperty(option)) {
        layer = lay;
      }
    });
    return layer;
  }
  // returns placed marker
  function getMarker() {
    return getMarkerFeatureGroup("_latlng");
  }

  // returns map's feature group
  function getFeatureGroup() {
    return getMarkerFeatureGroup("_layers");
  }

  // update lat and lng
  function updateLatLng(latlng) {
    $oldLat = latlng.lat.toString();
    $oldLng = latlng.lng.toString();
  }

  // update map view
  function updateMapView(data) {
    var geojson =
      '{ "type": "Point", "coordinates": [ ' + data.lng + ", " + data.lat + "] }";
    $mapGeojsonTextarea.val(geojson);
    getMap().setView([data.lat, data.lng], 15);
  }

  // update map
  function updateMap() {
    var addressValue = $addressInput.val(),
      message;
    if (!addressValue) {
      getFeatureGroup().clearLayers();
      return;
    }
    $.get($coordsUrl, { address: addressValue })
      .done(function (data) {
        var marker = getMarker(),
          featureGroup = getFeatureGroup();
        if (marker === undefined) {
          updateLatLng(data);
          featureGroup.addLayer(L.marker([data.lat, data.lng]));
        } else {
          var latlng = marker.getLatLng();
          if (latlng.lat !== data.lat || latlng.lng !== data.lng) {
            message = gettext(
              "The address was changed, would you like to " +
                "automatically update the location on the map?",
            );
            if (confirm(message)) {
              updateLatLng(data);
              featureGroup.removeLayer(marker);
              featureGroup.addLayer(L.marker([data.lat, data.lng]));
            }
          }
        }
      })
      .fail(function () {
        message = gettext(
          "Location with address: " + $addressInput.val() + "was not found.",
        );
        alert(message);
      });
  }

  function updateAdress() {
    var marker = getMarker(),
      message,
      latlng;
    if (marker === undefined) {
      return;
    }
    latlng = marker.getLatLng();
    if (latlng.lat.toString() === $oldLat && latlng.lng.toString() === $oldLng) {
      return;
    }
    updateLatLng(latlng);
    $.get($addrUrl, { lat: latlng.lat, lng: latlng.lng })
      .done(function (data) {
        if (!$addressInput.val()) {
          $addressInput.val(data.address);
        } else {
          message = gettext(
            "The location on the map was changed, would you " +
              "like to update the address to",
          );
          message += ' "' + data.address + '"?';
          if (confirm(message)) {
            $addressInput.val(data.address);
          }
        }
      })
      .fail(function () {
        message = gettext("Could not find any address related to this location.");
        alert(message);
      });
  }

  // triggers update of the address when the location on the map is changed
  function updateAddressOnMapChange() {
    var marker = getMarker();
    if (!marker) {
      return;
    }
    getMap().on("draw:edited", function (e) {
      updateAdress();
      updateMapView(marker.getLatLng());
    });
  }

  $addressInput.change(function () {
    updateMap();
  });

  function geometryListeners() {
    if (!getMap()) {
      return;
    }
    var featureGroup = getFeatureGroup(),
      marker = getMarker();
    featureGroup.on("layeradd", function () {
      updateAdress();
      updateAddressOnMapChange();
      marker = getMarker();
      if (!marker) {
        return;
      }
      updateMapView(marker.getLatLng());
    });
    if (marker !== undefined) {
      updateLatLng(marker.getLatLng());
      updateAddressOnMapChange();
    }
  }
  // some browsers fires load event before attaching listener
  // so we need to check if the document is ready
  if (document.readyState === "complete") {
    geometryListeners();
  } else {
    $(window).on("load", function () {
      geometryListeners();
    });
  }

  // show existing location
  var pk;
  if ($location.val()) {
    $locationSelectionRow.hide();
    $geoEdit.show();
    isNew = false;
    pk = $location.val();
  } else {
    pk = window.location.pathname.split("/").slice("-3", "-2")[0];
  }
  // fallback for view only users
  var typeLength = $type.length || $typeRow.find(".readonly").length;
  // show mobile map (hide not relevant fields)
  if ($isMobile.prop("checked")) {
    listenForLocationUpdates(pk);
    $outdoor.show();
    $locationSelection.parents(".form-row").hide();
    $locationRow.hide();
    $name.parents(".form-row").hide();
    if (!$address.val()) {
      $address.parents(".form-row").hide();
    }
    // if no location data yet
    if (!$geometryTextarea.val()) {
      $geometryRow.hide();
      $geometryRow.parent().append('<div class="no-location">' + msg + "</div>");
      $noLocationDiv = $(".no-location", ".loci.coords");
    }
    // this is triggered in the location form page
  } else if (!typeLength) {
    if (pk !== "location") {
      listenForLocationUpdates(pk);
    }
  }
  // show existing indoor
  // fallbacks for view only users
  if ($floorplan.val() || $floorplanSelectionRow.find(".readonly").text()) {
    $indoor.show();
    if ($floorplanSelection.val() || $floorplanSelectionRow.find(".readonly").text()) {
      $indoorRows.show();
      $floorplanSelectionRow.hide();
    }
    // adding indoor
  } else if (($type.val() || $typeRow.find(".readonly").text()) === "indoor") {
    $indoor.show();
    $indoorRows.show();
    indoorForm(
      $locationSelection.val() || $locationSelectionRow.find(".readonly").text(),
    );
  }
});
