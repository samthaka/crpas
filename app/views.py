from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from .models import Farmer
from .utils import get_rainfall_forecast, get_soil_data, generate_advisory

class FarmerListView(ListView):
    model = Farmer
    template_name = 'app/farmer_list.html'
    context_object_name = 'farmers'

class FarmerDetailView(DetailView):
    model = Farmer
    template_name = 'app/farmer_details.html'
    context_object_name = 'farmer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        farmer = self.object
        forecast = get_rainfall_forecast(farmer.lat, farmer.long)
        soil = get_soil_data(farmer.lat, farmer.long)
        if "error" not in forecast and "error" not in soil:
            advisory = generate_advisory(farmer, forecast, soil)
        else:
            advisory = "Error fetching weather/soil data. Try again later."
        context['advisory'] = advisory
        context['forecast'] = forecast
        context['soil'] = soil
        return context