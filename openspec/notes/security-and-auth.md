# Security & Authentication

## Design decision: No built-in authentication

Siphon is designed for home server / LAN environments (Unraid, self-hosted).
It does not implement API authentication by default. This is intentional and
consistent with the *arr ecosystem (Sonarr, Radarr, Lidarr, Prowlarr) which
follow the same pattern.

## Why this is acceptable

- Container runs on a local network, not exposed to the public internet
- Docker network isolation means only containers on the same bridge network
  can reach the API port
- SQLite is never network-accessible — it is an internal implementation detail
- The *arr apps are the established precedent for this class of home-server
  media tooling

## Reverse proxy guidance (for README)

Users who want to expose Siphon externally should place it behind a reverse
proxy with their own auth layer:
- NGINX Proxy Manager (common on Unraid)
- Swag (Linuxserver.io)
- Traefik
- Caddy

This should be documented clearly in the README.

## Future: API key support

If auth becomes necessary (e.g., remote access, multi-user), the pattern is
a single API key stored in the `settings` table, validated via FastAPI
middleware. This is the same pattern used by the *arr apps for
service-to-service integration (e.g., Radarr ↔ Jackett).

No action needed now. The design does not preclude adding this later.

## Container network note

On Unraid, containers share a user-defined bridge network by default. Any
container on that network can reach Siphon's API port. This is the accepted
norm for home-server containers and is not considered a threat for personal
use.
