from django.contrib.gis.db.backends.spatialite import base


class DatabaseWrapper(base.DatabaseWrapper):
    def prepare_database(self):
        # Workaround for https://code.djangoproject.com/ticket/32935
        with self.cursor() as cursor:
            cursor.execute("PRAGMA table_info(geometry_columns);")
            if cursor.fetchall() == []:
                cursor.execute("SELECT InitSpatialMetaData(1)")
        super().prepare_database()
