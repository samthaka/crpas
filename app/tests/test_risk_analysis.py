"""
Comprehensive tests for risk analysis module.
Covers risk_analysis.py with Groq API mocking.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from app.models import Farmer, Farm
from app.risk_analysis import analyze_weather_for_risks, generate_personalized_risk_notification
import json

CustomUser = get_user_model()


class WeatherRiskAnalysisTestCase(TestCase):
    """Test comprehensive weather risk analysis."""

    def setUp(self):
        """Create test user and farm."""
        self.user = CustomUser.objects.create_user(
            email='analysis_farmer@risk.com',
            password='Password123!'
        )
        self.farmer = Farmer.objects.create(
            fname='Analysis',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Analysis Farm',
            crop_type='maize',
            farm_size=2.0,
            county='Nakuru',
            sub_county='Nakuru Town',
            ward='Lake Ward',
            lat=-0.4333,
            long=36.25,
        )

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_risks_flood_high(self, mock_groq):
        """Test flood risk detection with high risk."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': [
                {
                    'risk_type': 'flood',
                    'affected_crop': 'maize',
                    'risk_level': 'high',
                    'probability_score': 85,
                    'description': 'Heavy rainfall expected',
                    'recommendation': 'Prepare drainage'
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 150, 'prob_max': 95, 'temp_min': 15, 'temp_max': 25},
            {'date': '2025-03-16', 'rain_mm': 120, 'prob_max': 90, 'temp_min': 15, 'temp_max': 24},
        ]
        soil_data = {'soil_moisture_top': 0.35}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))
        self.assertGreater(len(result.get('risks', [])), 0)

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_risks_pest_medium(self, mock_groq):
        """Test pest risk detection."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': [
                {
                    'risk_type': 'pest',
                    'affected_crop': 'maize',
                    'risk_level': 'medium',
                    'probability_score': 65,
                    'description': 'Warm humid conditions conducive to armyworm'
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 30, 'prob_max': 60, 'temp_min': 18, 'temp_max': 28},
            {'date': '2025-03-16', 'rain_mm': 40, 'prob_max': 70, 'temp_min': 19, 'temp_max': 29},
            {'date': '2025-03-17', 'rain_mm': 25, 'prob_max': 55, 'temp_min': 17, 'temp_max': 27},
        ]
        soil_data = {}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_risks_drought_high(self, mock_groq):
        """Test drought risk detection."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': [
                {
                    'risk_type': 'dry_spell',
                    'affected_crop': 'maize',
                    'risk_level': 'high',
                    'probability_score': 80,
                    'description': 'Prolonged dry spell expected',
                    'recommendation': 'Increase irrigation'
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 20, 'temp_max': 35},
            {'date': '2025-03-16', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 21, 'temp_max': 36},
            {'date': '2025-03-17', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 20, 'temp_max': 35},
            {'date': '2025-03-18', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 22, 'temp_max': 37},
            {'date': '2025-03-19', 'rain_mm': 0, 'prob_max': 5, 'temp_min': 21, 'temp_max': 36},
        ]
        soil_data = {'soil_moisture_top': 0.12}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_risks_low_risk(self, mock_groq):
        """Test analysis with low overall risk."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 15, 'prob_max': 40, 'temp_min': 15, 'temp_max': 25},
        ]
        soil_data = {'soil_moisture_top': 0.25}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_with_beans_crop(self, mock_groq):
        """Test analysis for beans crop."""
        # Create farm with beans
        beans_farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Beans Farm',
            crop_type='beans',
            farm_size=1.5,
            county='Kisii',
            sub_county='Kisii Central',
            ward='Keumbu Ward',
            lat=-0.6833,
            long=34.7833,
        )
        
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 20, 'prob_max': 50, 'temp_min': 15, 'temp_max': 26},
        ]
        soil_data = {}
        
        result = analyze_weather_for_risks(beans_farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_analyze_weather_multiple_risks(self, mock_groq):
        """Test analysis detecting multiple risks."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': [
                {
                    'risk_type': 'flood',
                    'affected_crop': 'maize',
                    'risk_level': 'medium',
                    'probability_score': 60,
                },
                {
                    'risk_type': 'pest',
                    'affected_crop': 'maize',
                    'risk_level': 'medium',
                    'probability_score': 55,
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 40, 'prob_max': 75, 'temp_min': 18, 'temp_max': 28},
            {'date': '2025-03-16', 'rain_mm': 35, 'prob_max': 70, 'temp_min': 19, 'temp_max': 29},
        ]
        soil_data = {'soil_moisture_top': 0.30}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))


class RiskAnalysisErrorHandlingTestCase(TestCase):
    """Test risk analysis error handling and edge cases."""

    def setUp(self):
        """Create test user and farm."""
        self.user = CustomUser.objects.create_user(
            email='error_farmer@risk.com',
            password='Password123!'
        )
        self.farmer = Farmer.objects.create(
            fname='Error',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Error Farm',
            crop_type='maize',
            farm_size=1.5,
            county='Kiambu',
            sub_county='Kiambu',
            ward='Kiambu Ward',
            lat=-1.1667,
            long=36.8167,
        )

    @patch('app.risk_analysis.Groq')
    def test_groq_api_error(self, mock_groq):
        """Test handling of Groq API errors."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception('API Error')
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 10, 'prob_max': 30, 'temp_min': 15, 'temp_max': 25}
        ]
        soil_data = {}
        
        # Should handle gracefully
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        # Result should indicate failure
        self.assertIsNotNone(result)
        self.assertFalse(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_malformed_groq_response(self, mock_groq):
        """Test handling of malformed Groq response."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'Invalid JSON response'
        mock_client.chat.completions.create.return_value = mock_response
        
        forecast_data = [
            {'date': '2025-03-15', 'rain_mm': 10, 'prob_max': 30, 'temp_min': 15, 'temp_max': 25}
        ]
        soil_data = {}
        
        result = analyze_weather_for_risks(self.farm, forecast_data, soil_data)
        
        # Should handle gracefully
        self.assertIsNotNone(result)
        self.assertFalse(result.get('success'))

    @patch('app.risk_analysis.Groq')
    def test_empty_forecast_data(self, mock_groq):
        """Test handling of empty forecast data."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = analyze_weather_for_risks(self.farm, [], {})
        
        # Should handle gracefully
        self.assertIsNotNone(result)

    @patch('app.risk_analysis.Groq')
    def test_none_forecast_data(self, mock_groq):
        """Test handling of None forecast data."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'success': True,
            'risks': []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = analyze_weather_for_risks(self.farm, None, None)
        
        # Should handle gracefully
        self.assertIsNotNone(result)


class PersonalizedRiskNotificationTestCase(TestCase):
    """Test personalized risk notification generation."""

    def setUp(self):
        """Create test user and farm."""
        self.user = CustomUser.objects.create_user(
            email='notif_farmer@risk.com',
            password='Password123!'
        )
        self.farmer = Farmer.objects.create(
            fname='Notification',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Notif Farm',
            crop_type='maize',
            farm_size=2.0,
            county='Uasin Gishu',
            sub_county='Turbo',
            ward='Turbo Ward',
            lat=0.35,
            long=35.25,
        )

    def test_generate_flood_risk_notification(self):
        """Test personalized flood risk notification generation."""
        # Create mock risk alert object with required methods and attributes
        risk_alert = MagicMock()
        risk_alert.get_risk_type_display.return_value = 'Flood'
        risk_alert.get_risk_level_display.return_value = 'High'
        risk_alert.risk_level = 'high'
        risk_alert.description = 'Heavy rainfall forecast'
        risk_alert.recommendation = 'Prepare drainage systems'
        
        result = generate_personalized_risk_notification(self.farmer, self.farm, risk_alert)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn('title', result)
        self.assertIn('message', result)

    def test_generate_pest_risk_notification(self):
        """Test personalized pest risk notification."""
        risk_alert = MagicMock()
        risk_alert.get_risk_type_display.return_value = 'Pest'
        risk_alert.get_risk_level_display.return_value = 'Medium'
        risk_alert.risk_level = 'medium'
        risk_alert.description = 'Warm humid conditions conducive to armyworm'
        risk_alert.recommendation = 'Apply pest control'
        
        result = generate_personalized_risk_notification(self.farmer, self.farm, risk_alert)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_generate_drought_risk_notification(self):
        """Test personalized drought risk notification."""
        risk_alert = MagicMock()
        risk_alert.get_risk_type_display.return_value = 'Dry Spell'
        risk_alert.get_risk_level_display.return_value = 'High'
        risk_alert.risk_level = 'high'
        risk_alert.description = 'Expected dry spell for 10+ days'
        risk_alert.recommendation = 'Increase irrigation'
        
        result = generate_personalized_risk_notification(self.farmer, self.farm, risk_alert)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_generate_critical_risk_notification(self):
        """Test critical risk level notification."""
        risk_alert = MagicMock()
        risk_alert.get_risk_type_display.return_value = 'Flood'
        risk_alert.get_risk_level_display.return_value = 'Critical'
        risk_alert.risk_level = 'critical'
        risk_alert.description = 'Imminent flood threat'
        risk_alert.recommendation = 'Evacuate if necessary'
        
        result = generate_personalized_risk_notification(self.farmer, self.farm, risk_alert)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        # Critical alerts should have urgent messaging
        self.assertIn('🚨', result.get('title', ''))

    def test_generate_low_risk_notification(self):
        """Test low risk level notification."""
        risk_alert = MagicMock()
        risk_alert.get_risk_type_display.return_value = 'Dry Spell'
        risk_alert.get_risk_level_display.return_value = 'Low'
        risk_alert.risk_level = 'low'
        risk_alert.description = 'Minor dry spell expected'
        risk_alert.recommendation = 'Monitor moisture'
        
        result = generate_personalized_risk_notification(self.farmer, self.farm, risk_alert)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
