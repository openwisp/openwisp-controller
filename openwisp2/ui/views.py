from django.conf import settings
from django.shortcuts import render


def index(request):
    # template context
    context = {
        'ACCOUNT_SIGNUP_ENABLED': getattr(settings, 'ACCOUNT_SIGNUP_ENABLED', True)
    }
    return render(request, 'index.html', context)
