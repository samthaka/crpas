from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser, BaseUserManager
from datetime import timedelta
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    # Email verification fields
    email_verified = models.BooleanField(
        default=False,
        verbose_name="Email Verified",
        help_text="Indicates whether the user has verified their email address"
    )
    email_verification_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name="Email Verification Code",
        help_text="6-digit code sent to user's email for verification"
    )
    verification_code_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Verification Code Expiry",
        help_text="Timestamp when the verification code expires"
    )
    
    # Phone verification fields
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+254712345678' or '0712345678'. Up to 15 digits allowed."
            )
        ],
        verbose_name="Phone Number",
        help_text="User's phone number for SMS-based authentication"
    )
    phone_verified = models.BooleanField(
        default=False,
        verbose_name="Phone Verified",
        help_text="Indicates whether the user has verified their phone number"
    )
    phone_verification_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name="Phone Verification Code",
        help_text="6-digit code sent to user's phone for verification"
    )
    phone_verification_code_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Phone Verification Code Expiry",
        help_text="Timestamp when the phone verification code expires"
    )
    
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    objects = CustomUserManager()

    def __str__(self):
        return self.email
    
    def is_verification_code_valid(self):
        """Check if email verification code exists and hasn't expired"""
        if not self.email_verification_code:
            return False
        if self.verification_code_expires_at is None:
            return False
        return timezone.now() < self.verification_code_expires_at
    
    def is_phone_verification_code_valid(self):
        """Check if phone verification code exists and hasn't expired"""
        if not self.phone_verification_code:
            return False
        if self.phone_verification_code_expires_at is None:
            return False
        return timezone.now() < self.phone_verification_code_expires_at

class Farmer(models.Model):
    fname = models.CharField(
        max_length=100,
        verbose_name="First Name",
        help_text="Farmer's first name (required)"
    )
    lname = models.CharField(
        max_length=100,
        verbose_name="Last Name",
        help_text="Farmer's last name (required)"
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+254712345678' or '0712345678'. Up to 15 digits allowed."
            )
        ],
        verbose_name="Phone Number",
        help_text="Primary contact (e.g., +2547XXXXXXXX) - optional if email provided"
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name="Email (Optional)"
    )
    # Conversation history with Gemini – stored as JSON list of dicts: [{"role": "user/system", "content": "..."}]
    gemini_chat_history = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Gemini Conversation History",
        help_text="Maintains context across interactions since Gemini is stateless"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        contact = self.phone or self.email or "No contact"
        return f"{self.fname} {self.lname} ({contact})"

    class Meta:
        verbose_name = "Farmer"
        verbose_name_plural = "Farmers"
        ordering = ['-created_at']


class Farm(models.Model):
    farmer = models.ForeignKey(
        Farmer,
        related_name='farms',
        on_delete=models.CASCADE,
        help_text="The farmer who owns this farm"
    )
    farm_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Farm Name",
        help_text="Optional name/identifier for this farm (e.g., 'Main Farm', 'North Field')"
    )
    crop_type = models.CharField(
        max_length=50,
        choices=[
            ('maize', 'Maize'),
            ('beans', 'Beans'),
            ('maize_beans', 'Maize and Beans (intercropped)'),
        ],
        verbose_name="Crop Type",
        help_text="Primary crop type for this farm"
    )
    farm_size = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Farm Size (acres)",
        help_text="Size of the farm in acres"
    )
    lat = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(-4.0), MaxValueValidator(5.0)],
        verbose_name="Latitude",
        help_text="Farm location latitude - auto-captured from device GPS"
    )
    long = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(33.0), MaxValueValidator(42.0)],
        verbose_name="Longitude",
        help_text="Farm location longitude - auto-captured from device GPS"
    )
    county = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="County",
        help_text="County extracted from GPS coordinates using reverse geocoding"
    )
    sub_county = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Sub-County",
        help_text="Sub-county/Constituency of the farm location"
    )
    ward = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Ward",
        help_text="Ward/Location of the farm"
    )
    gps_accuracy = models.FloatField(
        blank=True,
        null=True,
        verbose_name="GPS Accuracy (meters)",
        help_text="Accuracy of GPS coordinates in meters"
    )
    location_verified = models.BooleanField(
        default=False,
        verbose_name="Location Verified",
        help_text="Indicates if GPS location and admin location have been verified as accurate"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        farm_identifier = self.farm_name or f"Farm at {self.ward}, {self.sub_county}"
        return f"{self.farmer.fname} {self.farmer.lname} - {farm_identifier}"

    class Meta:
        verbose_name = "Farm"
        verbose_name_plural = "Farms"
        ordering = ['-created_at']


class ChatThread(models.Model):
    """A conversation thread for a specific farm/farmer."""
    farmer = models.ForeignKey(Farmer, related_name='chat_threads', on_delete=models.CASCADE)
    farm = models.ForeignKey(Farm, related_name='chat_threads', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True, default='New chat')
    history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        farm_info = f" - {self.farm.farm_name}" if self.farm and self.farm.farm_name else ""
        return f"ChatThread for {self.farmer}{farm_info} ({self.created_at:%Y-%m-%d %H:%M})"


class NotificationPreference(models.Model):
    """
    Stores the notification channel preferences for a farmer.
    Allows farmers to choose which channels they want to receive notifications on.
    """
    farmer = models.OneToOneField(
        Farmer,
        related_name='notification_preference',
        on_delete=models.CASCADE
    )
    notify_via_website = models.BooleanField(
        default=True,
        help_text="Receive notifications on the website/dashboard"
    )
    notify_via_email = models.BooleanField(
        default=True,
        help_text="Receive notifications via email"
    )
    notify_via_sms = models.BooleanField(
        default=True,
        help_text="Receive notifications via SMS"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification Preferences for {self.farmer}"

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"


class Notification(models.Model):
    """
    Stores individual notifications for farmers.
    Notifications can be triggered by various factors like rainfall, soil moisture, etc.
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('planting_date', 'Planting Date Alert'),
        ('rainfall', 'Rainfall Alert'),
        ('dry_spell', 'Dry Spell Warning'),
        ('soil_moisture', 'Soil Moisture Alert'),
        ('risk_alert', 'Risk Alert'),
        ('advisory', 'Advisory/General'),
    ]

    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('read', 'Read'),
    ]

    farmer = models.ForeignKey(
        Farmer,
        related_name='notifications',
        on_delete=models.CASCADE
    )
    title = models.CharField(
        max_length=200,
        help_text="Short title of the notification"
    )
    message = models.TextField(
        help_text="Detailed notification message"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='advisory',
        help_text="Type of notification"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='unread',
        help_text="Read status of the notification"
    )
    sent_via_website = models.BooleanField(
        default=False,
        help_text="Whether notification was sent via website"
    )
    sent_via_email = models.BooleanField(
        default=False,
        help_text="Whether notification was sent via email"
    )
    sent_via_sms = models.BooleanField(
        default=False,
        help_text="Whether notification was sent via SMS"
    )
    # Additional data stored as JSON (e.g., rainfall amount, soil moisture percentage)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata related to the notification"
    )
    
    # Region information (for tracking if this is part of a regional notification)
    county = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="County where the farmer receiving this notification is located"
    )
    sub_county = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sub-county where the farmer receiving this notification is located"
    )
    ward = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Ward where the farmer receiving this notification is located"
    )
    
    # Link to parent regional notification (if any)
    regional_notification = models.ForeignKey(
        'RegionalNotification',
        related_name='individual_notifications',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Parent regional notification if this was sent as part of a bulk campaign"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when notification was read"
    )

    def __str__(self):
        return f"{self.notification_type.upper()} - {self.farmer}: {self.title}"

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']


class NotificationTriggerLog(models.Model):
    """
    Logs trigger events that cause notifications to be sent.
    Helps track what triggered notifications for monitoring and debugging.
    """
    TRIGGER_TYPE_CHOICES = [
        ('rainfall', 'Rainfall Data'),
        ('soil_moisture', 'Soil Moisture Data'),
        ('planting_date', 'Planting Date Check'),
        ('dry_spell', 'Dry Spell Detection'),
        ('manual', 'Manual Trigger'),
    ]

    farmer = models.ForeignKey(
        Farmer,
        related_name='trigger_logs',
        on_delete=models.CASCADE
    )
    trigger_type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPE_CHOICES,
        help_text="Type of trigger that caused the notification"
    )
    trigger_data = models.JSONField(
        help_text="Raw data that triggered the notification"
    )
    notification = models.ForeignKey(
        Notification,
        related_name='trigger_logs',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The notification that was created from this trigger"
    )
    processed = models.BooleanField(
        default=True,
        help_text="Whether this trigger has been processed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trigger_type.upper()} trigger for {self.farmer} on {self.created_at}"

    class Meta:
        verbose_name = "Notification Trigger Log"
        verbose_name_plural = "Notification Trigger Logs"
        ordering = ['-created_at']


class RegionalNotification(models.Model):
    """
    Stores notifications sent to entire regions (counties, sub-counties, or wards).
    These notifications are bulk-sent to all farmers in the specified region(s).
    """
    REGION_LEVEL_CHOICES = [
        ('county', 'County'),
        ('sub_county', 'Sub-County'),
        ('ward', 'Ward'),
    ]

    NOTIFICATION_TYPE_CHOICES = [
        ('weather_alert', 'Weather Alert'),
        ('pest_alert', 'Pest/Disease Alert'),
        ('advisory', 'Regional Advisory'),
        ('market_update', 'Market Update'),
        ('emergency', 'Emergency Alert'),
        ('custom', 'Custom Regional Alert'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    title = models.CharField(
        max_length=200,
        help_text="Title of the regional notification"
    )
    message = models.TextField(
        help_text="Detailed message for the regional notification"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='advisory',
        help_text="Type of regional notification"
    )
    
    # Region targeting
    region_level = models.CharField(
        max_length=20,
        choices=REGION_LEVEL_CHOICES,
        default='county',
        help_text="Geographic level for this notification"
    )
    region_name = models.CharField(
        max_length=100,
        help_text="Name of county, sub-county, or ward (depending on region_level)"
    )
    
    # Alternative: specific sub-county or ward within a county
    sub_region_names = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional list of specific sub-counties or wards within the region (for targeted alerts)"
    )
    
    # Crop type targeting (optional - send to all crops if empty)
    crop_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional list of crop types to target (empty = all crops)"
    )
    
    # Notification settings
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Current status of the notification"
    )
    
    # Sending options
    send_via_website = models.BooleanField(
        default=True,
        help_text="Send notification via website/dashboard"
    )
    send_via_email = models.BooleanField(
        default=True,
        help_text="Send notification via email"
    )
    send_via_sms = models.BooleanField(
        default=True,
        help_text="Send notification via SMS"
    )
    
    # Scheduling
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule notification for future sending (leave empty to send immediately)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (e.g., weather data, pest info, market prices)"
    )
    
    # Tracking
    created_by = models.CharField(
        max_length=100,
        default='system',
        help_text="User or system that created this notification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when notification was sent"
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    # Statistics
    target_farmer_count = models.IntegerField(
        default=0,
        help_text="Number of farmers targeted by this notification"
    )
    sent_count = models.IntegerField(
        default=0,
        help_text="Number of notifications successfully sent"
    )
    failed_count = models.IntegerField(
        default=0,
        help_text="Number of notifications that failed to send"
    )

    def __str__(self):
        return f"{self.notification_type.upper()} - {self.region_name}: {self.title}"

    class Meta:
        verbose_name = "Regional Notification"
        verbose_name_plural = "Regional Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'region_level']),
            models.Index(fields=['region_name', 'region_level']),
        ]


class RegionalNotificationLog(models.Model):
    """
    Tracks individual notifications sent as part of a regional notification campaign.
    Links individual notifications to their parent regional notification.
    """
    
    regional_notification = models.ForeignKey(
        RegionalNotification,
        related_name='notification_logs',
        on_delete=models.CASCADE,
        help_text="Parent regional notification"
    )
    
    farmer = models.ForeignKey(
        Farmer,
        related_name='regional_notification_logs',
        on_delete=models.CASCADE,
        help_text="Farmer who received the notification"
    )
    
    notification = models.ForeignKey(
        Notification,
        related_name='regional_log',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The individual notification sent to this farmer"
    )
    
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        help_text="Status of notification delivery to this farmer"
    )
    
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if delivery failed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when notification was sent to farmer"
    )

    def __str__(self):
        return f"{self.regional_notification.title} → {self.farmer}"

    class Meta:
        verbose_name = "Regional Notification Log"
        verbose_name_plural = "Regional Notification Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['regional_notification', 'status']),
            models.Index(fields=['farmer', 'status']),
        ]


class WeatherDataCache(models.Model):
    """
    Stores cached weather data fetched every 6 hours as a fallback for API failures.
    This data is used by the LLM to analyze risks (floods, pest infestation, dry spells).
    """
    farm = models.ForeignKey(
        Farm,
        related_name='weather_cache',
        on_delete=models.CASCADE,
        help_text="The farm for which weather data is cached"
    )
    
    # Weather data snapshot
    latitude = models.FloatField(
        help_text="Farm latitude"
    )
    longitude = models.FloatField(
        help_text="Farm longitude"
    )
    
    # Raw weather forecast data (JSON array of daily forecasts)
    # Format: [{"date": "2025-03-24", "temp_min": 15, "temp_max": 28, "rain_mm": 5, "prob_max": 60, ...}, ...]
    forecast_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Cached weather forecast data from Open-Meteo (10 days)"
    )
    
    # Soil data snapshot
    soil_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached soil moisture and temperature data"
    )
    
    # Timestamp when this data was fetched
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this weather data was fetched"
    )
    
    # Whether this data was used for risk analysis
    analyzed = models.BooleanField(
        default=False,
        help_text="Whether this data has been analyzed for risks"
    )
    
    # Store the API response status
    fetch_success = models.BooleanField(
        default=True,
        help_text="Whether the API fetch was successful"
    )
    
    fetch_error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if fetch failed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "✓" if self.fetch_success else "✗"
        return f"{status} {self.farm} weather cache ({self.fetched_at:%Y-%m-%d %H:%M})"

    class Meta:
        verbose_name = "Weather Data Cache"
        verbose_name_plural = "Weather Data Caches"
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['farm', '-fetched_at']),
            models.Index(fields=['analyzed', 'fetch_success']),
        ]


class RiskAlert(models.Model):
    """
    Stores detected environmental risks (floods, pest infestation, dry spells)
    that were identified by the LLM during weather data analysis.
    Linked to WeatherDataCache to trace which data triggered the alert.
    """
    RISK_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    RISK_TYPES = [
        ('flood', 'Flood Risk'),
        ('pest', 'Pest Infestation'),
        ('dry_spell', 'Dry Spell'),
    ]
    
    CROP_CHOICES = [
        ('maize', 'Maize'),
        ('beans', 'Beans'),
        ('both', 'Both Maize and Beans'),
    ]
    
    farm = models.ForeignKey(
        Farm,
        related_name='risk_alerts',
        on_delete=models.CASCADE,
        help_text="The farm affected by this risk"
    )
    
    weather_cache = models.ForeignKey(
        WeatherDataCache,
        related_name='detected_risks',
        on_delete=models.CASCADE,
        help_text="The weather data that triggered this risk alert"
    )
    
    risk_type = models.CharField(
        max_length=20,
        choices=RISK_TYPES,
        help_text="Type of risk detected"
    )
    
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_LEVELS,
        default='medium',
        help_text="Severity level of the risk"
    )
    
    # Which crop(s) are affected
    affected_crop = models.CharField(
        max_length=20,
        choices=CROP_CHOICES,
        help_text="Which crop(s) are affected by this risk"
    )
    
    # LLM's description of the risk
    description = models.TextField(
        help_text="Detailed explanation of the risk from LLM analysis"
    )
    
    # LLM's recommendations
    recommendation = models.TextField(
        help_text="Recommended action to mitigate this risk"
    )
    
    # Probability score (0-100) from LLM analysis
    probability_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="LLM's confidence score (0-100) that this risk will occur"
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(
        default=False,
        help_text="Whether a notification was sent for this risk"
    )
    
    notification = models.ForeignKey(
        Notification,
        related_name='triggered_by_risk',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The notification sent for this risk alert"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_risk_level_display()} {self.get_risk_type_display()} - {self.farm} ({self.created_at:%Y-%m-%d %H:%M})"

    class Meta:
        verbose_name = "Risk Alert"
        verbose_name_plural = "Risk Alerts"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farm', '-created_at']),
            models.Index(fields=['risk_level', 'notification_sent']),
            models.Index(fields=['risk_type', 'affected_crop']),
        ]