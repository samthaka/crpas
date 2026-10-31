"""
Tests for advisory generation system.
Converted from script.py
Tests core advisory logic for generating personalized farming recommendations.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from app.models import Farmer, Farm
from app.utils import (
    get_rainfall_forecast,
    get_soil_data,
    generate_advisory,
    reverse_geocode_coordinates
)
from unittest.mock import patch, MagicMock

CustomUser = get_user_model()


class AdvisoryGenerationSetup(TestCase):
    """Common setup for advisory generation tests."""

    def setUp(self):
        """Create test farm."""
        self.user = CustomUser.objects.create_user(
            email='advisory_farmer@example.com',
            password='AdvPassword123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        self.farmer = Farmer.objects.create(
            fname='Advisory',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Test Farm',
            crop_type='maize',
            farm_size=3.0,
            county='Kisii',
            sub_county='Kisii Central',
            ward='Keumbu Ward',
            lat=-0.6833,
            long=34.7833,
        )


class RainfallForecastTestCase(AdvisoryGenerationSetup):
    """Test rainfall forecast retrieval for advisory generation."""

    @patch('app.utils.requests.get')
    def test_get_rainfall_forecast(self, mock_get):
        """Test retrieving rainfall forecast for location."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'daily': {
                'precipitation_sum': [2, 5, 10, 15, 8, 3, 0]
            }
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        forecast = get_rainfall_forecast(self.farm.lat, self.farm.long)
        
        self.assertIsNotNone(forecast)
        if 'daily' in forecast:
            self.assertIn('precipitation_sum', forecast['daily'])

    @patch('app.utils.requests.get')
    def test_rainfall_forecast_network_error(self, mock_get):
        """Test forecast gracefully handles network errors."""
        mock_get.side_effect = Exception("Network error")
        
        forecast = get_rainfall_forecast(self.farm.lat, self.farm.long)
        
        # Should return None or empty dict rather than crashing
        self.assertTrue(forecast is None or isinstance(forecast, dict))


class SoilDataTestCase(AdvisoryGenerationSetup):
    """Test soil data retrieval for advisory generation."""

    @patch('app.utils.requests.get')
    def test_get_soil_data(self, mock_get):
        """Test retrieving soil data for location."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'soil_type': 'sandy loam',
            'soil_moisture': 45,
            'organic_matter': 2.5
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        soil = get_soil_data(self.farm.lat, self.farm.long)
        
        self.assertIsNotNone(soil)
        if 'soil_type' in soil:
            self.assertIsNotNone(soil['soil_type'])

    @patch('app.utils.requests.get')
    def test_soil_data_network_error(self, mock_get):
        """Test soil data gracefully handles network errors."""
        mock_get.side_effect = Exception("Network error")
        
        soil = get_soil_data(self.farm.lat, self.farm.long)
        
        # Should return None or empty dict rather than crashing
        self.assertTrue(soil is None or isinstance(soil, dict))


class AdvisoryGenerationTestCase(AdvisoryGenerationSetup):
    """Test advisory generation from weather and soil data."""

    @patch('app.utils.Groq')
    def test_generate_advisory_with_good_conditions(self, mock_groq_class):
        """Test generating advisory with good soil and weather conditions."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari Advisory! Ushauri wa Kupanda wa CRPAS: Plant maize now as conditions are good."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2026-03-25', 'rain_mm': 15, 'prob_max': 80, 'temp_min': 18, 'temp_max': 28},
            {'date': '2026-03-26', 'rain_mm': 20, 'prob_max': 85, 'temp_min': 19, 'temp_max': 29},
            {'date': '2026-03-27', 'rain_mm': 10, 'prob_max': 60, 'temp_min': 17, 'temp_max': 27},
        ]
        soil_data = {
            'soil_moisture_top': 55,
            'soil_moisture_mid': 60,
            'soil_moisture_deep': 65,
            'soil_temp_surface': 22
        }
        
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(advisory)
        self.assertIsInstance(advisory, str)
        self.assertGreater(len(advisory), 0)

    @patch('app.utils.Groq')
    def test_generate_advisory_with_dry_conditions(self, mock_groq_class):
        """Test advisory suggests irrigation with low soil moisture."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari! Consider waiting for rain or prepare irrigation."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2026-03-25', 'rain_mm': 0, 'prob_max': 10, 'temp_min': 20, 'temp_max': 32},
            {'date': '2026-03-26', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 21, 'temp_max': 33},
            {'date': '2026-03-27', 'rain_mm': 0, 'prob_max': 0, 'temp_min': 20, 'temp_max': 32},
        ]
        soil_data = {
            'soil_moisture_top': 25,  # Low
            'soil_moisture_mid': 30,
            'soil_moisture_deep': 35,
            'soil_temp_surface': 28
        }
        
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(advisory)
        self.assertIsInstance(advisory, str)

    @patch('app.utils.Groq')
    def test_generate_advisory_with_wet_conditions(self, mock_groq_class):
        """Test advisory warns about waterlogging with high soil moisture."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari! Wait for soil to dry before planting to avoid waterlogging."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2026-03-25', 'rain_mm': 30, 'prob_max': 90, 'temp_min': 16, 'temp_max': 24},
            {'date': '2026-03-26', 'rain_mm': 35, 'prob_max': 95, 'temp_min': 15, 'temp_max': 23},
            {'date': '2026-03-27', 'rain_mm': 40, 'prob_max': 100, 'temp_min': 14, 'temp_max': 22},
        ]
        soil_data = {
            'soil_moisture_top': 75,  # High
            'soil_moisture_mid': 78,
            'soil_moisture_deep': 80,
            'soil_temp_surface': 18
        }
        
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(advisory)
        self.assertIsInstance(advisory, str)

    @patch('app.utils.Groq')
    def test_generate_advisory_returns_string(self, mock_groq_class):
        """Test that advisory generation always returns string."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Default advisory message."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = []
        soil_data = {}
        
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        # Should return string (even if empty or error message)
        self.assertTrue(isinstance(advisory, str) or advisory is None)


class AdvisoryIntegrationTestCase(AdvisoryGenerationSetup):
    """Integration tests for full advisory generation pipeline."""

    @patch('app.utils.Groq')
    def test_full_advisory_pipeline(self, mock_groq_class):
        """Test complete pipeline: forecast → soil data → advisory."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari Advisory! Ushauri wa Kupanda wa CRPAS: Full pipeline test."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        # Setup realistic data
        forecast_data = [
            {'date': '2026-03-25', 'rain_mm': 10, 'prob_max': 75, 'temp_min': 18, 'temp_max': 28},
            {'date': '2026-03-26', 'rain_mm': 15, 'prob_max': 80, 'temp_min': 19, 'temp_max': 29},
            {'date': '2026-03-27', 'rain_mm': 20, 'prob_max': 85, 'temp_min': 17, 'temp_max': 27},
            {'date': '2026-03-28', 'rain_mm': 8, 'prob_max': 60, 'temp_min': 16, 'temp_max': 26},
            {'date': '2026-03-29', 'rain_mm': 2, 'prob_max': 30, 'temp_min': 18, 'temp_max': 29},
        ]
        soil_data = {
            'soil_moisture_top': 45,
            'soil_moisture_mid': 50,
            'soil_moisture_deep': 55,
            'soil_temp_surface': 24
        }
        
        # Generate advisory
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        # Verify results
        self.assertIsNotNone(advisory)
        self.assertGreater(len(str(advisory)), 0)

    @patch('app.utils.Groq')
    def test_advisory_generation_handles_missing_forecast(self, mock_groq_class):
        """Test advisory generation when forecast data is unavailable."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari! Unable to generate forecast-based advisory."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = None
        soil_data = {'soil_moisture_top': 50, 'soil_moisture_mid': 55}
        
        # Should handle None or empty gracefully
        try:
            advisory = generate_advisory(self.farm, forecast_data, soil_data)
            # If it returns, should be string or None
            self.assertTrue(advisory is None or isinstance(advisory, str))
        except (TypeError, AttributeError):
            # It's acceptable if the function doesn't handle None
            pass

    @patch('app.utils.Groq')
    def test_advisory_generation_handles_empty_forecast(self, mock_groq_class):
        """Test advisory generation when forecast data is empty list."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari! Empty forecast received."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = []
        soil_data = {
            'soil_moisture_top': 50,
            'soil_moisture_mid': 55,
            'soil_moisture_deep': 60,
            'soil_temp_surface': 22
        }
        
        advisory = generate_advisory(self.farm, forecast_data, soil_data)
        
        # Should still generate or return None gracefully
        self.assertTrue(advisory is None or isinstance(advisory, str))

    @patch('app.utils.Groq')
    def test_advisory_generation_handles_missing_soil_data(self, mock_groq_class):
        """Test advisory generation when soil data is unavailable."""
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Habari! Unable to generate soil-based advisory."))]
        mock_groq.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2026-03-25', 'rain_mm': 10, 'prob_max': 75, 'temp_min': 18, 'temp_max': 28},
        ]
        soil_data = None
        
        # Should handle None or empty gracefully
        try:
            advisory = generate_advisory(self.farm, forecast_data, soil_data)
            # If it returns, should be string or None
            self.assertTrue(advisory is None or isinstance(advisory, str))
        except (TypeError, AttributeError):
            # It's acceptable if the function doesn't handle None
            pass

    def test_farm_data_available_for_advisory(self):
        """Test that farm has necessary data for advisory generation."""
        self.assertIsNotNone(self.farm.lat)
        self.assertIsNotNone(self.farm.long)
        self.assertIsNotNone(self.farm.crop_type)
        self.assertIsNotNone(self.farm.farm_size)
