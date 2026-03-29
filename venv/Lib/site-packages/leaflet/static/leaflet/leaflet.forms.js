L.FieldStore = L.Class.extend({
    initialize: function (fieldid, options) {
        this.formfield = document.getElementById(fieldid);
        L.setOptions(this, options);
    },

    load: function () {
        var value = (this.formfield.value || '');
        return this._deserialize(value);
    },

    save: function (layer) {
        this.formfield.value = this._serialize(layer);
    },

    _serialize: function (layer) {
        var items = typeof(layer.getLayers) == 'function' ? layer.getLayers() : [layer],
            is_multi = this.options.is_collection || items.length > 1,
            is_generic = this.options.is_generic,
            collection_type = this.options.collection_type,
            is_empty = items.length === 0;

        if (is_empty)
            return '';

        var geom = is_multi ? layer : items[0];
        if (typeof geom.toGeoJSON != 'function') {
            throw 'Unsupported layer type ' + geom.constructor.name;
        }

        // Leaflet requires access to original feature attribute for GeoJSON
        // serialization. (see https://github.com/Leaflet/Leaflet/blob/v0.7.3/src/layer/GeoJSON.js#L256-L258)
        // When creating new records, it's empty so we force it here.
        if (!geom.feature) {
            geom.feature = {geometry: {type: this.options.geom_type}};
        }

        var geojson = geom.toGeoJSON(this.options.precision);
        var is_geometrycollection = (geojson.geometry && geojson.geometry.type == 'GeometryCollection');
        if (is_multi && is_generic && !is_geometrycollection) {
            var flat = {type: 'GeometryCollection', geometries: []};
            for (var i=0; i < geojson.features.length; i++) {
                flat.geometries.push(geojson.features[i].geometry);
            }
            geojson = flat;
        }
        // Special case for MultiPolyline/MultiPolygon because it was removed from leaflet 1.0
        else if (is_multi && collection_type != 'featureGroup') {
            var latlngs = [];
            for (var i = 0; i < geojson.features.length; i++) {
                var latlng = [];
                var coord = geojson.features[i].geometry.coordinates;
                if (collection_type == 'polygon') {
                    coord = coord[0];
                }
                for (var j = 0; j < coord.length; j++) {
                    latlng.push([coord[j][1], coord[j][0]]);
                }
                if (collection_type == 'polygon') {
                    latlng = [latlng];
                }
                latlngs.push(latlng);
            }
            geom = L[collection_type](latlngs);
            geojson = geom.toGeoJSON(this.options.precision).geometry;
        }
        // In order to make multipoint work, it seems we need to treat it similarly to the GeometryCollections
        else if (this.options.geom_type == 'MULTIPOINT') {
            var flat = {type: 'MultiPoint', coordinates: []};
            for (var i=0; i < geojson.features.length; i++) {
                flat.coordinates.push(geojson.features[i].geometry.coordinates);
            }
            geojson = flat;
        }
        else {
            geojson = geojson.geometry;
        }
        return JSON.stringify(geojson);
    },

    _deserialize: function (value) {
        if (/^\s*$/.test(value)) {
            return null;
        }
        // Helps to get rid of the float value conversion error
        this.formfield.value = JSON.stringify(JSON.parse(value));
        return L.GeoJSON.geometryToLayer(JSON.parse(value));
    },
});


L.GeometryField = L.Class.extend({
    statics: {
        unsavedText: 'Map geometry is unsaved'
    },

    options: {
        field_store_class: L.FieldStore
    },

    initialize: function (options) {

        var geom_type = options.geom_type.toLowerCase();
        options.is_generic = /geometry/.test(geom_type);
        options.is_collection = /(^multi|collection$)/.test(geom_type);
        options.is_linestring = /linestring$/.test(geom_type) || options.is_generic;
        options.is_polygon = /polygon$/.test(geom_type) || options.is_generic;
        options.is_point = /point$/.test(geom_type) || options.is_generic;
        options.collection_type = ({
            'multilinestring': 'polyline',
            'multipolygon': 'polygon',
        })[geom_type] || 'featureGroup';


        L.setOptions(this, options);

        this._drawControl = null;
        this._unsavedChanges = false;

        // Warn if leaving with unsaved changes
        var _beforeunload = window.onbeforeunload;
        window.onbeforeunload = L.Util.bind(function(e) {
            if (this._unsavedChanges)
                return L.GeometryField.unsavedText;
            if (typeof(_beforeunload) == 'function')
                return _beforeunload();
        }, this);
    },

    addTo: function (map) {
        this._map = map;

        var store_opts = L.Util.extend(this.options, {defaults: map.defaults});
        this.store = new this.options.field_store_class(this.options.fieldid, store_opts);

        this.drawnItems = this._editionLayer();
        map.addLayer(this.drawnItems);

        // Initialize the draw control and pass it the FeatureGroup of editable layers
        var drawControl = this._drawControl = new L.Control.Draw(this._controlDrawOptions());

        if (this.options.modifiable) {
            map.addControl(drawControl);
            L.DomUtil.addClass(drawControl._container, this.options.fieldid);

            //
            // In case there is several draw controls on the same map (target map option)
            map['drawControl' + this.options.fieldid] = drawControl;
            // We use a flag to ignore events of other draw controls
            for (var toolbar in drawControl._toolbars) {
                drawControl._toolbars[toolbar].on('enable disable', function (e) {
                    this._acceptDrawEvents = e.type === 'enable';
                }, this);
            }

            map.on('draw:created draw:edited draw:deleted', function (e) {
                // Ignore if coming from other Draw controls
                if (!this._acceptDrawEvents)
                    return;
                // Call onCreated(), onEdited(), onDeleted()
                var eventName = e.type.replace('draw:', ''),
                    method = 'on' + eventName.charAt(0).toUpperCase() + eventName.slice(1);
                this[method](e);
            }, this);

            // Flag for unsaved changes
            map.on('draw:drawstart draw:editstart', function () {
                if (this._acceptDrawEvents) this._unsavedChanges = true;
            }, this);
            map.on('draw:drawstop draw:editstop', function () {
                if (this._acceptDrawEvents) this._unsavedChanges = false;
            }, this);
        }

        this.load();

        map.fire('map:loadfield', {field: this, fieldid: this.options.fieldid});

        return this;
    },

    load: function () {
        var geometry = this.store.load();
        if (geometry) {
            // Add initial geometry to the map
            if (geometry instanceof L.LayerGroup) {
                geometry.eachLayer(function (l) {
                    this.drawnItems.addLayer(l);
                }, this);
            }
            else if (this.options.collection_type !== 'featureGroup'
                        && (geometry instanceof L.Polygon || geometry instanceof L.Polyline)) {
                var latlngs = geometry.getLatLngs();
                for (var i = 0; i < latlngs.length; i++) {
                    this.drawnItems.addLayer(L[this.options.collection_type](latlngs[i]));
                }
            }
            else {
                this.drawnItems.addLayer(geometry);
            }
            this.drawnItems.addTo(this._map);
        }
        this._setView();
        return geometry;
    },

    _setView: function () {
        // Change view extent
        if (this.drawnItems.getLayers().length > 0) {
            var bounds = this.drawnItems.getBounds();
            var options = {
                maxZoom: this._map.maxZoom || 15
            };
            this._map.fitBounds(bounds, options);
        }
        // Else keep view extent set by django-leaflet template tag
    },

    onCreated: function (e) {
        // Remove previously drawn if field is not collection.
        if (!this.options.is_collection) {
            this.drawnItems.eachLayer(function (l) {
                this._map.removeLayer(l);
            }, this);
            this.drawnItems.clearLayers();
        }
        var layer = e.layer;
        this._map.addLayer(layer);
        this.drawnItems.addLayer(layer);
        this.store.save(this.drawnItems);
    },

    onEdited: function (e) {
        this.store.save(this.drawnItems);
    },

    onDeleted: function (e) {
        var layer = e.layer || e.layers;
        this.drawnItems.removeLayer(layer);
        this.store.save(this.drawnItems);
    },

    _editionLayer: function () {
        var type = 'featureGroup',
            constructor = L[type];
        if (typeof(constructor) != 'function') {
            throw 'Unsupported geometry type: ' + type;
        }
        return constructor([], {});
    },

    _controlDrawOptions: function () {
        return {
            edit: {
                featureGroup: this.drawnItems
            },
            draw: {
                polyline: this.options.is_linestring,
                polygon: this.options.is_polygon,
                circle: false, // Turns off this drawing tool
                circlemarker: false, // Turns off this drawing tool
                rectangle: this.options.is_polygon,
                marker: this.options.is_point,
            }
        };
    }
});
