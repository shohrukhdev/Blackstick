from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from Blackstick import settings
from booket.views import landing

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('b/', include('booket.urls')),
    path('dashboard/', include('booket.dashboard.urls')),
    path('orders/', include('orders.urls')),
    path('', landing, name='landing'),
    path('', include('booket.client.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
