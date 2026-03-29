"""
The following serializers are not used to send
response to user but in swagger documentation of
the API.
"""

from rest_framework import serializers
from rest_framework.authtoken.serializers import AuthTokenSerializer


class ObtainTokenRequest(AuthTokenSerializer):
    pass


class ObtainTokenResponse(serializers.Serializer):
    token = serializers.CharField(read_only=True)
