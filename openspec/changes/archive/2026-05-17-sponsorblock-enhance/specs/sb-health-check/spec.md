## ADDED Requirements

### Requirement: SponsorBlock health endpoint returns API availability
The system SHALL expose `GET /health/sponsorblock` which probes the SponsorBlock API by requesting `https://sponsor.ajay.app/api/skipSegments?videoID=dQw4w9WgXcQ` (a known video with segments). The endpoint SHALL return `{"status": "healthy"}` with HTTP 200 if the SB API responds with 200, or `{"status": "unhealthy", "reason": "<message>"}` with HTTP 503 if the probe fails.

#### Scenario: SB API is reachable
- **WHEN** a GET request is made to `/health/sponsorblock` and the SB API responds with HTTP 200
- **THEN** the endpoint SHALL return HTTP 200 with body `{"status": "healthy"}`

#### Scenario: SB API is unreachable (timeout)
- **WHEN** a GET request is made to `/health/sponsorblock` and the SB API does not respond within 3 seconds
- **THEN** the system SHALL retry up to 3 times with 3-second timeout each
- **THEN** if all retries fail, the endpoint SHALL return HTTP 503 with body `{"status": "unhealthy", "reason": "timeout"}`

#### Scenario: SB API returns error
- **WHEN** a GET request is made to `/health/sponsorblock` and the SB API responds with HTTP 5xx
- **THEN** the endpoint SHALL NOT retry and SHALL return HTTP 503 with body `{"status": "unhealthy", "reason": "server_error"}`

#### Scenario: SB API returns 4xx
- **WHEN** a GET request is made to `/health/sponsorblock` and the SB API responds with HTTP 4xx
- **THEN** the endpoint SHALL NOT retry and SHALL return HTTP 503 with body `{"status": "unhealthy", "reason": "client_error"}`
