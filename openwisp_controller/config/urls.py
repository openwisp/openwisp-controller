from django.urls import path

from .views import schema

app_name = 'openwisp_controller'
urlpatterns = [path('config/schema.json', schema, name='schema')]
