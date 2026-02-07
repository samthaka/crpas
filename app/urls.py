from django.urls import path
from .views import FarmerListView, FarmerDetailView

urlpatterns = [
    path('farmers/', FarmerListView.as_view(), name='farmer_list'),
    path('farmer/<int:pk>/', FarmerDetailView.as_view(), name='farmer_detail'),
]