from django.urls import path
from . views import (
    auth_view, index_redirect, dashboard, logout_view, farmer_registration, 
    reverse_geocode_api, conversation_view, new_chat_view, delete_chat_view,
    get_notifications, mark_notification_as_read, delete_notification,
    get_notification_preferences, update_notification_preferences
)

urlpatterns = [
    path('', index_redirect, name='index'),
    path('auth/', auth_view, name='auth'),
    path('farmer-registration/', farmer_registration, name='farmer_registration'),
    path('api/reverse-geocode/', reverse_geocode_api, name='reverse_geocode_api'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('conversation/', conversation_view, name='conversation'),
    path('conversation/new/', new_chat_view, name='new_chat'),
    path('conversation/<int:thread_id>/delete/', delete_chat_view, name='delete_chat'),
    
    # Notification endpoints
    path('api/notifications/', get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', mark_notification_as_read, name='mark_notification_as_read'),
    path('api/notifications/<int:notification_id>/delete/', delete_notification, name='delete_notification'),
    path('api/notification-preferences/', get_notification_preferences, name='get_notification_preferences'),
    path('api/notification-preferences/update/', update_notification_preferences, name='update_notification_preferences'),
]