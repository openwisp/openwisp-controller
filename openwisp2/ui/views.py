from django.shortcuts import render


def index(request):
    # template context
    context = {}
    return render(request, 'index.html', context)
