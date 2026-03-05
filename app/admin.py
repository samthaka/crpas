from django.contrib import admin
from .models import Farmer, Farm, Notification, NotificationPreference, NotificationTriggerLog

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ('fname', 'lname', 'phone', 'email', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('fname', 'lname', 'phone', 'email')
    readonly_fields = ('gemini_chat_history', 'created_at', 'updated_at')


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('farm_name', 'farmer', 'crop_type', 'farm_size', 'sub_county', 'ward', 'created_at')
    list_filter = ('crop_type', 'created_at', 'sub_county')
    search_fields = ('farm_name', 'farmer__fname', 'farmer__lname', 'sub_county', 'ward')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Farmer & Farm Info', {
            'fields': ('farmer', 'farm_name', 'crop_type', 'farm_size')
        }),
        ('Location Details', {
            'fields': ('county', 'sub_county', 'ward', 'lat', 'long', 'gps_accuracy', 'location_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'farmer', 'notification_type', 'status', 'created_at')
    list_filter = ('notification_type', 'status', 'created_at', 'sent_via_website', 'sent_via_email', 'sent_via_sms')
    search_fields = ('title', 'message', 'farmer__fname', 'farmer__lname')
    readonly_fields = ('created_at', 'read_at')
    fieldsets = (
        ('Notification Info', {
            'fields': ('farmer', 'title', 'message', 'notification_type', 'status')
        }),
        ('Delivery Channels', {
            'fields': ('sent_via_website', 'sent_via_email', 'sent_via_sms')
        }),
        ('Additional Data', {
            'fields': ('metadata', 'created_at', 'read_at')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'notify_via_website', 'notify_via_email', 'notify_via_sms', 'updated_at')
    list_filter = ('notify_via_website', 'notify_via_email', 'notify_via_sms')
    search_fields = ('farmer__fname', 'farmer__lname')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NotificationTriggerLog)
class NotificationTriggerLogAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'trigger_type', 'processed', 'created_at')
    list_filter = ('trigger_type', 'processed', 'created_at')
    search_fields = ('farmer__fname', 'farmer__lname')
    readonly_fields = ('created_at',)