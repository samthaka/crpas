from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator

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
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+254712345678' or '0712345678'. Up to 15 digits allowed."
            )
        ],
        verbose_name="Phone Number",
        help_text="Primary contact (e.g., +2547XXXXXXXX) - required for SMS"
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name="Email (Optional)"
    )
    lat = models.FloatField(
        validators=[MinValueValidator(-4.0), MaxValueValidator(5.0)],  # Kenya roughly -4 to 5 lat
        verbose_name="Latitude",
        help_text="Field location latitude (e.g., -1.2921 for Nairobi area)"
    )
    long = models.FloatField(
        validators=[MinValueValidator(33.0), MaxValueValidator(42.0)],  # Kenya roughly 33 to 42 long
        verbose_name="Longitude",
        help_text="Field location longitude (e.g., 36.8219)"
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
        return f"{self.fname} {self.lname} ({self.phone})"

    class Meta:
        verbose_name = "Farmer"
        verbose_name_plural = "Farmers"
        ordering = ['-created_at']