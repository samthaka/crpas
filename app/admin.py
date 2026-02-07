from django.contrib import admin
from .models import Farmer

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ('fname', 'lname', 'phone', 'crop_type', 'lat', 'long', 'created_at')
    list_filter = ('crop_type', 'created_at')
    search_fields = ('fname', 'lname', 'phone')
    readonly_fields = ('gemini_chat_history', 'created_at', 'updated_at')