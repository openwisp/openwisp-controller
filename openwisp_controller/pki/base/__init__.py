from import_export.admin import ImportExportMixin


class PkiReversionTemplatesMixin(ImportExportMixin, object):
    change_list_template = 'pki/change_list.html'
