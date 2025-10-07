Truck Routing Phase 1 - Implementation TODO

Status legend: Completed / In Progress / Pending

Completed
- Design DB schema: address_cache, customer_locations, distance_cache, depot_config
- Lightweight DB init on startup to create tables if missing
- Address extraction/normalization from Excel uploads
- Geocoding interface (Google) + caching with confidence scoring
- Geocode validate endpoint (/geocode/validate)
- Distance service (Google Distance Matrix with Haversine fallback)
- Distance endpoints (/distance-matrix) and depot GET/PUT endpoints
- Frontend Address Validation panel with counts/progress
- Frontend Depot configuration form + API clients

In Progress
- Geocoding endpoints (batch + status) per PRD

Pending
- Frontend Address Management view (edit table + map preview)
- Wire Route flow to use geocode + distance data and show planning results
- Configuration/docs: .env for API keys and feature flags
- Tests: unit/integration for services and endpoints

Notes
- Backend health: http://127.0.0.1:8010/health
- Frontend dev: http://localhost:3001
- Google key env var: GOOGLE_MAPS_API_KEY (backend)



