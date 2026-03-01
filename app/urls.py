from django.urls import path
from . views import auth_view, institution_dashboard, logout_view, farmer_registration

urlpatterns = [
    path('auth/', auth_view, name='auth'),
    path('farmer-registration/', farmer_registration, name='farmer_registration'),
    path('dashboard/', institution_dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
]