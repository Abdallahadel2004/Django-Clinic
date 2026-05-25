from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.split if hasattr(admin.site, 'split') else admin.site.urls), 
    path('api/', include('clinic.urls')),
]