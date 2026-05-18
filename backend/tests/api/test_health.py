from fastapi import status


def test_health_check(client):
    """Tests the health check endpoint using Given-When-Then."""
    # GIVEN
    endpoint = "/api/health"
    expected_status = status.HTTP_200_OK
    expected_response = {"status": "ok"}

    # WHEN
    response = client.get(endpoint)

    # THEN
    assert response.status_code == expected_status
    assert response.json() == expected_response
