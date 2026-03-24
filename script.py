# use this script to test the core logic without running the server
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crpas.settings")
django.setup()

# Code starts here
from app.models import Farm
from app.utils import get_rainfall_forecast, get_soil_data, generate_advisory

farm = Farm.objects.first()  # or create one
forecast = get_rainfall_forecast(farm.lat, farm.long)
soil = get_soil_data(farm.lat, farm.long)
print(generate_advisory(farm, forecast, soil))