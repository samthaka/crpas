from django.urls import path
from . views import auth_view, dashboard, logout_view, farmer_registration, conversation_view, new_chat_view, delete_chat_view

urlpatterns = [
    path('auth/', auth_view, name='auth'),
    path('farmer-registration/', farmer_registration, name='farmer_registration'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('conversation/', conversation_view, name='conversation'),
    path('conversation/new/', new_chat_view, name='new_chat'),
    path('conversation/<int:thread_id>/delete/', delete_chat_view, name='delete_chat'),
]