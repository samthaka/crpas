# CRPAS

CRPAS (Climate-Responsive Precision Agriculture System) is a Django-based agricultural decision-support platform built for Kenyan smallholder farmers. The system helps farmers register their farms, connect location and crop information, receive climate and soil insights, and get practical advisory messages that support planting, crop protection, and risk management decisions.

## What the system does

CRPAS combines farm registration, geolocation, weather analysis, risk detection, and notification delivery into a single platform.

Key capabilities include:
- Farmer account creation with email and phone verification
- Farm registration with GPS coordinates, acreage, crop type, and location details
- Reverse geocoding to identify county, sub-county, and ward from GPS coordinates
- Weather and soil data collection using external climate APIs
- Risk analysis for flood, pest, and dry spell conditions
- Daily or triggered agricultural advisories for farmers
- Multi-channel notifications through the web dashboard, email, and SMS
- AI-powered conversation support for agronomy questions
- Scheduled background tasks for automated advisory processing

## Problem it solves

Smallholder farmers in Kenya often face major uncertainty around:
- Sudden rainfall and false-start planting conditions
- Prolonged dry spells that stress crops
- Pest outbreaks under warm, humid conditions
- Poor access to localized agricultural information
- Delayed communication about weather-based risks

CRPAS addresses this by making crop and weather information more accessible, localized, and actionable. Instead of relying only on scattered advice, farmers receive data-driven recommendations based on their own farm location and crop profile.

## Main features

### Farmer and farm management
- Secure custom user accounts using Django authentication
- Email verification and phone verification flows
- Farmer profile creation and farm registration
- Support for maize and bean cropping systems, including intercropped farms

### Location-aware agriculture
- GPS-based farm registration
- Reverse geocoding against Kenya administrative geography data
- County and ward-level awareness for local advisory generation

### Climate and risk intelligence
- Weather forecast retrieval from Open-Meteo
- Soil moisture and temperature checks
- Risk detection using Groq-hosted large language models and meteorological thresholds
- Daily advisory generation tailored to the farmer's crop and conditions

### Communication and alerts
- Website notifications stored in the application database
- Email alerts via Gmail SMTP
- SMS alerts through an external gateway
- Notification preference controls per farmer

### AI assistant
- Chat thread support for agricultural conversations
- Context-aware advisor responses using weather and soil information
- Real-time recommendations tied to the specific farm and crop

## Tech stack

This application is built using the following technologies:

- Python 3
- Django 5.2
- PostgreSQL (main production/database layer)
- SQLite (used for certain local/offline data and test database behavior)
- Docker and Docker Compose
- HTML / CSS / JavaScript
- Django templates and static assets
- Django-allauth for social authentication and account integration
- Django APScheduler for task scheduling
- Custom Django models and admin interface
- Requests library for API integrations
- Python-dotenv for environment management
- Groq API for agricultural risk analysis and advisory generation
- Open-Meteo API for rainfall and soil data
- OpenStreetMap/Nominatim-style reverse geocoding support
- Kenya administrative GIS data stored locally in `county-data/kenya_admin.db`
- Gmail SMTP for email delivery
- External SMS gateway via HTTP JSON request

## Setup and run

### Option 1: Local Python environment
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example environment file and add your configuration:
   ```bash
   cp .env.example .env
   ```
4. Update the values for your database, Groq key, Gmail credentials, security settings, and SMS gateway.
5. Run migrations:
   ```bash
   python manage.py migrate
   ```
6. Start the application:
   ```bash
   python manage.py runserver
   ```

### Option 2: Docker Compose
```bash
docker-compose up --build
```

The app should be available at:
- http://localhost:8000

## Environment variables

The project expects values such as:
- SECRET_KEY
- DEBUG
- ALLOWED_HOSTS
- DB_NAME
- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT
- GROQ_API_KEY
- GMAIL_ADDRESS
- GMAIL_APP_PASSWORD
- SMS_GATEWAY_URL
- Google OAuth credentials for allauth

## Notes

This project is designed as a practical climate-smart farming application for Kenya, with a focus on local conditions, weather-driven decision support, and farmer communication. It combines modern Django backend development with agricultural data APIs and AI-based interpretation to help farmers act before climate risks damage their crops.

## License

This project does not appear to declare a license in the repository contents reviewed here. If you plan to distribute or publish it, add a license file and confirm the intended usage terms.
