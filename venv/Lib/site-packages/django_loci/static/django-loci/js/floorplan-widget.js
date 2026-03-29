(function () {
  "use strict";
  django.loadFloorPlan = function (widgetName, imageUrl, imageW, imageH) {
    var $input = django.jQuery("#id_" + widgetName),
      $parent = $input.parents("fieldset").eq(0),
      url = imageUrl || $parent.find("a.floorplan-image").attr("href"),
      $dim = $parent.find("#id_" + widgetName.replace("indoor", "image") + "-dim"),
      $indoorPosition = $parent.find(".field-indoor"),
      mapId = "id_" + widgetName + "_map",
      w = imageW || $dim.data("width"),
      h = imageH || $dim.data("height"),
      coordinates,
      map;

    if (!url) {
      return;
    }
    $indoorPosition.show();

    map = L.map(mapId, {
      crs: L.CRS.Simple,
      minZoom: -1,
      maxZoom: 2,
    });

    // calculate the edges of the image, in coordinate space
    var bottomRight = map.unproject([0, h * 2], map.getMaxZoom() - 1),
      upperLeft = map.unproject([w * 2, 0], map.getMaxZoom() - 1),
      bounds = new L.LatLngBounds(bottomRight, upperLeft);
    L.imageOverlay(url, bounds).addTo(map);
    map.fitBounds(bounds);
    map.setMaxBounds(bounds);
    map.setView([0, 0], 0);

    function updateInput(e) {
      var latlng = e.latlng || e.target._latlng;
      $input.val(latlng.lat + "," + latlng.lng);
    }

    if ($input.val()) {
      var latlng = $input.val().split(",");
      coordinates = { lat: latlng[0], lng: latlng[1] };
    } else {
      coordinates = undefined;
    }
    var draggable = true;
    // if readonly field, don't allow dragging
    if ($indoorPosition.find(".readonly").length) {
      draggable = false;
    }

    var marker = new L.marker(coordinates, { draggable: draggable });
    marker.bindPopup(gettext("Drag to reposition"));
    marker.on("dragend", updateInput);
    if (coordinates) {
      marker.addTo(map);
    }

    map.on("click", function (e) {
      if (marker.getLatLng() === undefined) {
        marker.setLatLng(e.latlng);
        marker.addTo(map);
        updateInput(e);
      }
    });

    // clear indoor coordinates if map is removed
    map.on("unload", function () {
      $input.val("");
    });

    return map;
  };
})();
