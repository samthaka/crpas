from django.urls import path
from . views import (
    auth_view, index_redirect, dashboard, logout_view, farmer_registration, 
    farm_registration, edit_farm_details, reverse_geocode_api, conversation_view, 
    new_chat_view, delete_chat_view,
    get_notifications, mark_notification_as_read, delete_notification,
    get_notification_preferences, update_notification_preferences
)
from . views import (
    auth_view, index_redirect, dashboard, logout_view, farmer_registration, 
    reverse_geocode_api, conversation_view, new_chat_view, delete_chat_view, 
    verify_email, resend_verification_email, phone_auth, verify_phone, 
    resend_verification_sms, phone_signup_password, verify_farmer_email
)

urlpatterns = [
    path('', index_redirect, name='index'),
    path('auth/', auth_view, name='auth'),
    path('verify-email/', verify_email, name='verify_email'),
    path('resend-verification/', resend_verification_email, name='resend_verification'),
    path('phone-auth/', phone_auth, name='phone_auth'),
    path('verify-phone/', verify_phone, name='verify_phone'),
    path('resend-sms/', resend_verification_sms, name='resend_sms'),
    path('phone-signup-password/', phone_signup_password, name='phone_signup_password'),
    path('farmer-registration/', farmer_registration, name='farmer_registration'),
    path('verify-farmer-email/', verify_farmer_email, name='verify_farmer_email'),
    path('farm-registration/', farm_registration, name='farm_registration'),
    path('farm/<int:farm_id>/edit/', edit_farm_details, name='edit_farm_details'),
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