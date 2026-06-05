from django.urls import path, include

from orders import bot_views

urlpatterns = [
    path('', include('orders.dashboard.urls')),
    path('client/', include('orders.client.urls')),
    path('telegram/webhook/', bot_views.telegram_webhook, name='orders_telegram_webhook'),
]
