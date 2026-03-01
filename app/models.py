from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser, BaseUserManager

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
    lat = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(-4.0), MaxValueValidator(5.0)],  # Kenya roughly -4 to 5 lat
        verbose_name="Latitude",
        help_text="Field location latitude - auto-captured from device GPS"
    )
    long = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(33.0), MaxValueValidator(42.0)],  # Kenya roughly 33 to 42 long
        verbose_name="Longitude",
        help_text="Field location longitude - auto-captured from device GPS"
    )
    sub_county = models.CharField(
        max_length=100,
        verbose_name="Sub-County",
        help_text="Sub-county/Constituency of the farm location (e.g., Kasipul, Muhoroni)"
    )
    ward = models.CharField(
        max_length=100,
        verbose_name="Ward",
        help_text="Ward/Location of the farm (e.g., Kabar, Chemase)"
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
    crop_type = models.CharField(
        max_length=50,
        choices=[
            ('maize', 'Maize'),
            ('beans', 'Beans'),
            ('maize_beans', 'Maize and Beans (intercropped)'),
        ],
        verbose_name="Crop Type",
        help_text="Only maize, beans, or both allowed"
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