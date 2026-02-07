# use this script to test the core logic without running the server
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crpas.settings")
django.setup()

# Code starts here
from app.models import Farmer
from app.utils import get_rainfall_forecast, get_soil_data, generate_advisory

farmer = Farmer.objects.first()  # or create one
forecast = get_rainfall_forecast(farmer.lat, farmer.long)
soil = get_soil_data(farmer.lat, farmer.long)
print(generate_advisory(farmer, forecast, soil))