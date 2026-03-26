from django.contrib import admin
from .models import (
    Farmer, Farm, Notification, NotificationPreference, 
    NotificationTriggerLog, RegionalNotification, RegionalNotificationLog,
    WeatherDataCache, RiskAlert
)

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


@admin.register(RegionalNotification)
class RegionalNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'region_name', 'region_level', 'notification_type', 'status', 'sent_count', 'created_at')
    list_filter = ('region_level', 'notification_type', 'status', 'created_at', 'region_name')
    search_fields = ('title', 'message', 'region_name')
    readonly_fields = ('created_at', 'updated_at', 'sent_at', 'sent_count', 'failed_count', 'target_farmer_count')
    
    fieldsets = (
        ('Regional Notification Info', {
            'fields': ('title', 'message', 'notification_type', 'status', 'created_by')
        }),
        ('Region Targeting', {
            'fields': ('region_level', 'region_name', 'sub_region_names'),
            'description': 'Select the geographic level and region(s) to target'
        }),
        ('Crop Targeting', {
            'fields': ('crop_types',),
            'description': 'Leave empty to send to all crops'
        }),
        ('Delivery Channels', {
            'fields': ('send_via_website', 'send_via_email', 'send_via_sms')
        }),
        ('Scheduling', {
            'fields': ('scheduled_for',),
            'description': 'Leave empty to send immediately'
        }),
        ('Additional Data', {
            'fields': ('metadata',)
        }),
        ('Statistics & Tracking', {
            'fields': ('target_farmer_count', 'sent_count', 'failed_count', 'created_at', 'updated_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_draft', 'mark_as_scheduled', 'send_now']
    
    def mark_as_draft(self, request, queryset):
        queryset.update(status='draft')
        self.message_user(request, f"{queryset.count()} notifications marked as draft")
    mark_as_draft.short_description = "Mark selected as Draft"
    
    def mark_as_scheduled(self, request, queryset):
        queryset.update(status='scheduled')
        self.message_user(request, f"{queryset.count()} notifications marked as scheduled")
    mark_as_scheduled.short_description = "Mark selected as Scheduled"
    
    def send_now(self, request, queryset):
        from .notification_utils import send_regional_notification
        
        for regional_notif in queryset:
            if regional_notif.status in ['draft', 'scheduled']:
                result = send_regional_notification(regional_notif, send_immediately=True)
                self.message_user(
                    request,
                    f"Sent '{regional_notif.title}': {result['sent']} notifications sent, "
                    f"{result['failed']} failed"
                )
    send_now.short_description = "Send selected notifications now"


@admin.register(RegionalNotificationLog)
class RegionalNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('regional_notification', 'farmer', 'status', 'sent_at')
    list_filter = ('status', 'sent_at', 'regional_notification')
    search_fields = ('farmer__fname', 'farmer__lname', 'regional_notification__title')
    readonly_fields = ('created_at', 'sent_at')
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('regional_notification', 'farmer', 'notification')
        }),
        ('Status', {
            'fields': ('status', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Logs are created automatically, not manually
        return False


@admin.register(WeatherDataCache)
class WeatherDataCacheAdmin(admin.ModelAdmin):
    list_display = ('farm', 'fetched_at', 'fetch_success', 'analyzed', 'created_at')
    list_filter = ('fetch_success', 'analyzed', 'fetched_at', 'created_at')
    search_fields = ('farm__farmer__fname', 'farm__farmer__lname', 'farm__ward', 'farm__sub_county')
    readonly_fields = ('created_at', 'updated_at', 'latitude', 'longitude')
    
    fieldsets = (
        ('Farm Location', {
            'fields': ('farm', 'latitude', 'longitude')
        }),
        ('Weather Data', {
            'fields': ('forecast_data', 'soil_data'),
            'classes': ('collapse',)
        }),
        ('Fetch Status', {
            'fields': ('fetch_success', 'fetch_error', 'analyzed')
        }),
        ('Timestamps', {
            'fields': ('fetched_at', 'created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Cache entries are created automatically by tasks
        return False


@admin.register(RiskAlert)
class RiskAlertAdmin(admin.ModelAdmin):
    list_display = ('farm', 'risk_type', 'risk_level', 'affected_crop', 'probability_score', 'notification_sent', 'created_at')
    list_filter = ('risk_type', 'risk_level', 'affected_crop', 'notification_sent', 'created_at')
    search_fields = ('farm__farmer__fname', 'farm__farmer__lname', 'farm__ward', 'farm__sub_county')
    readonly_fields = ('created_at', 'updated_at', 'weather_cache', 'farm')
    
    fieldsets = (
        ('Risk Alert Details', {
            'fields': ('farm', 'weather_cache', 'risk_type', 'risk_level', 'affected_crop')
        }),
        ('Risk Analysis', {
            'fields': ('description', 'recommendation', 'probability_score')
        }),
        ('Notification', {
            'fields': ('notification_sent', 'notification'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Risk alerts are created automatically by LLM analysis
        return False