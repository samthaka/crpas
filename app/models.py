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
        """Check if verification code exists and hasn't expired"""
        if not self.email_verification_code:
            return False
        if self.verification_code_expires_at is None:
            return False
        return timezone.now() < self.verification_code_expires_at

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
    """A conversation thread for a specific farmer."""
    farmer = models.ForeignKey(Farmer, related_name='chat_threads', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True, default='New chat')
    history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ChatThread for {self.farmer} ({self.created_at:%Y-%m-%d %H:%M})"


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