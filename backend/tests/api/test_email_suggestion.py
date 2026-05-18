from unittest.mock import patch

from fastapi import status


def test_get_email_suggestion_success(client):
    """Tests a successful email suggestion request"""
    # GIVEN
    email_content = "Can we meet tomorrow?"
    expected_reply = "This is a mock reply."

    with patch("app.api.router.LlmService.generate_suggestion") as mock_gen:
        mock_gen.return_value = expected_reply

        # WHEN
        response = client.post("/api/email/suggestion", json={"email_content": email_content})

        # THEN
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"suggestedReply": expected_reply}
        mock_gen.assert_called_once_with(email_content)
