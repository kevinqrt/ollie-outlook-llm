from datetime import UTC, datetime
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.api.schemas.calendar_schema import CalendarEventSchema, MeetingTimeSuggestionSchema
from app.services.graph_auth_service import GraphAuthError
from app.services.graph_calendar_service import CalendarServiceError


def test_get_calendar_auth_login_success(graph_client: TestClient) -> None:
    with patch("app.services.graph_auth_service.GraphAuthService.get_auth_url") as mock_url:
        mock_url.return_value = "https://login.microsoftonline.com/authorize?..."

        response = graph_client.get("/calendar/auth/login")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"authUrl": "https://login.microsoftonline.com/authorize?..."}
    mock_url.assert_called_once()


def test_get_calendar_auth_login_not_configured(graph_client: TestClient) -> None:
    with patch("app.services.graph_auth_service.GraphAuthService.get_auth_url") as mock_url:
        mock_url.side_effect = GraphAuthError("Microsoft Graph is not configured.")

        response = graph_client.get("/calendar/auth/login")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_post_calendar_auth_callback_success(graph_client: TestClient) -> None:
    with (
        patch(
            "app.services.graph_auth_service.GraphAuthService.acquire_token_by_code"
        ) as mock_acquire,
        patch("app.services.graph_auth_service.GraphAuthService.is_authenticated") as mock_is_auth,
    ):
        mock_acquire.return_value = None
        mock_is_auth.return_value = True

        response = graph_client.post("/calendar/auth/callback", json={"code": "auth-code"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"authenticated": True}
    mock_acquire.assert_called_once_with("auth-code")


def test_post_calendar_auth_callback_failure(graph_client: TestClient) -> None:
    with patch(
        "app.services.graph_auth_service.GraphAuthService.acquire_token_by_code"
    ) as mock_acquire:
        mock_acquire.side_effect = GraphAuthError("Code expired.")

        response = graph_client.post("/calendar/auth/callback", json={"code": "expired-code"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Code expired." in response.json()["detail"]


def test_get_calendar_auth_status(graph_client: TestClient) -> None:
    with patch("app.services.graph_auth_service.GraphAuthService.is_authenticated") as mock_is_auth:
        mock_is_auth.return_value = False

        response = graph_client.get("/calendar/auth/status")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"authenticated": False}


def test_get_calendar_events_success(graph_client: TestClient) -> None:
    event = CalendarEventSchema(
        id="event-1",
        subject="Sprint Planning",
        start=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        organizer="Alice",
        is_organizer=True,
    )

    with patch("app.services.graph_calendar_service.GraphCalendarService.list_events") as mock_list:
        mock_list.return_value = [event]

        response = graph_client.get(
            "/calendar/events",
            params={"start": "2026-08-03T00:00:00Z", "end": "2026-08-04T00:00:00Z"},
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["subject"] == "Sprint Planning"


def test_get_calendar_events_service_error(graph_client: TestClient) -> None:
    with patch("app.services.graph_calendar_service.GraphCalendarService.list_events") as mock_list:
        mock_list.side_effect = CalendarServiceError("Not authenticated with Microsoft Graph.")

        response = graph_client.get(
            "/calendar/events",
            params={"start": "2026-08-03T00:00:00Z", "end": "2026-08-04T00:00:00Z"},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_get_calendar_events_missing_params(graph_client: TestClient) -> None:
    response = graph_client.get("/calendar/events")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_post_calendar_meeting_times_success(graph_client: TestClient) -> None:
    suggestion = MeetingTimeSuggestionSchema(
        start=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        end=datetime(2026, 8, 3, 11, 30, tzinfo=UTC),
        confidence=100.0,
    )

    with patch(
        "app.services.graph_calendar_service.GraphCalendarService.find_meeting_times"
    ) as mock_find:
        mock_find.return_value = [suggestion]

        response = graph_client.post(
            "/calendar/meeting-times",
            json={"attendees": ["alice@example.com"], "durationMinutes": 30},
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body["suggestions"]) == 1
    assert body["suggestions"][0]["confidence"] == 100.0
    mock_find.assert_called_once()
    call_args = mock_find.call_args[0]
    assert call_args[0] == ["alice@example.com"]
    assert call_args[3] == 30


def test_post_calendar_meeting_times_service_error(graph_client: TestClient) -> None:
    with patch(
        "app.services.graph_calendar_service.GraphCalendarService.find_meeting_times"
    ) as mock_find:
        mock_find.side_effect = CalendarServiceError("Not authenticated with Microsoft Graph.")

        response = graph_client.post(
            "/calendar/meeting-times", json={"attendees": ["alice@example.com"]}
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_post_calendar_meeting_times_requires_at_least_one_attendee(
    graph_client: TestClient,
) -> None:
    response = graph_client.post("/calendar/meeting-times", json={"attendees": []})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_calendar_ics_status_initially_unconfigured(client: TestClient) -> None:
    response = client.get("/calendar/ics/status")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"configured": False}


def test_post_calendar_ics_self_success(client: TestClient) -> None:
    with patch(
        "app.services.ics_calendar_service.IcsCalendarService.validate_feed"
    ) as mock_validate:
        mock_validate.return_value = None

        response = client.post("/calendar/ics/self", json={"url": "https://example.com/me.ics"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"configured": True}

    status_response = client.get("/calendar/ics/status")
    assert status_response.json() == {"configured": True}


def test_post_calendar_ics_self_rejects_unreachable_url(client: TestClient) -> None:
    with patch(
        "app.services.ics_calendar_service.IcsCalendarService.validate_feed"
    ) as mock_validate:
        mock_validate.side_effect = CalendarServiceError("Kalender-Link nicht erreichbar.")

        response = client.post("/calendar/ics/self", json={"url": "https://example.com/broken.ics"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    status_response = client.get("/calendar/ics/status")
    assert status_response.json() == {"configured": False}


def test_calendar_ics_known_add_list_remove_roundtrip(client: TestClient) -> None:
    with patch(
        "app.services.ics_calendar_service.IcsCalendarService.validate_feed"
    ) as mock_validate:
        mock_validate.return_value = None

        add_response = client.post(
            "/calendar/ics/known",
            json={"email": "alice@example.com", "url": "https://example.com/alice.ics"},
        )

    assert add_response.status_code == status.HTTP_200_OK
    assert add_response.json() == {
        "calendars": [{"email": "alice@example.com", "url": "https://example.com/alice.ics"}]
    }

    list_response = client.get("/calendar/ics/known")
    assert list_response.json() == {
        "calendars": [{"email": "alice@example.com", "url": "https://example.com/alice.ics"}]
    }

    delete_response = client.delete("/calendar/ics/known/alice@example.com")
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json() == {"calendars": []}


def test_calendar_ics_endpoints_503_when_graph_backend_active(graph_client: TestClient) -> None:
    response = graph_client.post("/calendar/ics/self", json={"url": "https://example.com/me.ics"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
