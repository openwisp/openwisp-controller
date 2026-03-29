{
    const withForms = document.getElementById("with-forms") ? JSON.parse(document.getElementById("with-forms").textContent) : false;
    if (withForms) {
        L.drawLocal.draw.toolbar.actions.title = JSON.parse(document.getElementById("draw-toolbar-actions-title").textContent);
        L.drawLocal.draw.toolbar.actions.text = JSON.parse(document.getElementById("draw-toolbar-actions-text").textContent);
        L.drawLocal.draw.toolbar.undo.title = JSON.parse(document.getElementById("draw-toolbar-undo-title").textContent);
        L.drawLocal.draw.toolbar.undo.text = JSON.parse(document.getElementById("draw-toolbar-undo-text").textContent);
        L.drawLocal.draw.toolbar.buttons.polyline = JSON.parse(document.getElementById("draw-toolbar-buttons-polyline").textContent);
        L.drawLocal.draw.toolbar.buttons.polygon = JSON.parse(document.getElementById("draw-toolbar-buttons-polygon").textContent);
        L.drawLocal.draw.toolbar.buttons.rectangle = JSON.parse(document.getElementById("draw-toolbar-buttons-rectangle").textContent);
        L.drawLocal.draw.toolbar.buttons.circle = JSON.parse(document.getElementById("draw-toolbar-buttons-circle").textContent);
        L.drawLocal.draw.toolbar.buttons.marker = JSON.parse(document.getElementById("draw-toolbar-buttons-marker").textContent);
        L.drawLocal.draw.handlers.circle.tooltip.start = JSON.parse(document.getElementById("draw-handlers-circle-tooltip-start").textContent);
        L.drawLocal.draw.handlers.marker.tooltip.start = JSON.parse(document.getElementById("draw-handlers-marker-tooltip-start").textContent);
        L.drawLocal.draw.handlers.polygon.tooltip.start = JSON.parse(document.getElementById("draw-handlers-polygon-tooltip-start").textContent);
        L.drawLocal.draw.handlers.polygon.tooltip.cont = JSON.parse(document.getElementById("draw-handlers-polygon-tooltip-cont").textContent);
        L.drawLocal.draw.handlers.polygon.tooltip.end = JSON.parse(document.getElementById("draw-handlers-polygon-tooltip-end").textContent);
        L.drawLocal.draw.handlers.polyline.error = JSON.parse(document.getElementById("draw-handlers-polyline-error").textContent);
        L.drawLocal.draw.handlers.polyline.tooltip.start = JSON.parse(document.getElementById("draw-handlers-polyline-tooltip-start").textContent);
        L.drawLocal.draw.handlers.polyline.tooltip.cont = JSON.parse(document.getElementById("draw-handlers-polyline-tooltip-cont").textContent);
        L.drawLocal.draw.handlers.polyline.tooltip.end = JSON.parse(document.getElementById("draw-handlers-polyline-tooltip-end").textContent);
        L.drawLocal.draw.handlers.rectangle.tooltip.start = JSON.parse(document.getElementById("draw-handlers-rectangle-tooltip-start").textContent);
        L.drawLocal.draw.handlers.simpleshape.tooltip.end = JSON.parse(document.getElementById("draw-handlers-simpleshape-tooltip-end").textContent);

        L.drawLocal.edit.toolbar.actions.save.title = JSON.parse(document.getElementById("edit-toolbar-actions-save-title").textContent);
        L.drawLocal.edit.toolbar.actions.save.text = JSON.parse(document.getElementById("edit-toolbar-actions-save-text").textContent);
        L.drawLocal.edit.toolbar.actions.cancel.title = JSON.parse(document.getElementById("edit-toolbar-actions-cancel-title").textContent);
        L.drawLocal.edit.toolbar.actions.cancel.text = JSON.parse(document.getElementById("edit-toolbar-actions-cancel-text").textContent);
        L.drawLocal.edit.toolbar.buttons.edit = JSON.parse(document.getElementById("edit-toolbar-buttons-edit").textContent);
        L.drawLocal.edit.toolbar.buttons.editDisabled = JSON.parse(document.getElementById("edit-toolbar-buttons-editDisabled").textContent);
        L.drawLocal.edit.toolbar.buttons.remove = JSON.parse(document.getElementById("edit-toolbar-buttons-remove").textContent);
        L.drawLocal.edit.toolbar.buttons.removeDisabled = JSON.parse(document.getElementById("edit-toolbar-buttons-removeDisabled").textContent);
        L.drawLocal.edit.handlers.edit.tooltip.text = JSON.parse(document.getElementById("edit-handlers-edit-tooltip-text").textContent);
        L.drawLocal.edit.handlers.edit.tooltip.subtext = JSON.parse(document.getElementById("edit-handlers-edit-tooltip-subtext").textContent);
        L.drawLocal.edit.handlers.remove.tooltip.text = JSON.parse(document.getElementById("edit-handlers-remove-tooltip-text").textContent);
    }
}
