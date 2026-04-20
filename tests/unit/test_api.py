"""Tests for siphon.api — pure helpers and FastAPI routes via TestClient."""
import pytest

from siphon.api import _normalise_youtube_url


# ---------------------------------------------------------------------------
# _normalise_youtube_url (pure helper — no client needed)
# ---------------------------------------------------------------------------

class TestNormaliseYoutubeUrl:
    def test_mixed_v_and_list_normalised_to_playlist(self):
        url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"
        result = _normalise_youtube_url(url)
        assert result == "https://www.youtube.com/playlist?list=PLxyz"
        assert "v=" not in result

    def test_pure_playlist_url_unchanged(self):
        url = "https://www.youtube.com/playlist?list=PLxyz"
        assert _normalise_youtube_url(url) == url

    def test_single_video_url_unchanged(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert _normalise_youtube_url(url) == url

    def test_non_youtube_url_unchanged(self):
        url = "https://vimeo.com/123456"
        assert _normalise_youtube_url(url) == url

    def test_youtube_com_without_www(self):
        url = "https://youtube.com/watch?v=abc&list=PLxyz"
        result = _normalise_youtube_url(url)
        assert result == "https://www.youtube.com/playlist?list=PLxyz"


# ---------------------------------------------------------------------------
# GET /playlists
# ---------------------------------------------------------------------------

class TestGetPlaylists:
    def test_returns_200_empty_list(self, api_client):
        resp = api_client.get("/playlists")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------

class TestGetJobs:
    def test_returns_200_empty_list(self, api_client):
        resp = api_client.get("/jobs")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------

class TestGetSettings:
    def test_returns_200(self, api_client):
        resp = api_client.get("/settings")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /playlists — validation errors (no real YouTube call needed)
# ---------------------------------------------------------------------------

class TestPostPlaylistValidation:
    def test_missing_url_returns_422(self, api_client):
        resp = api_client.post("/playlists", json={})
        assert resp.status_code == 422
