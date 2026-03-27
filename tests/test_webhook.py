"""
Tests for Delimit webhook notification module.

Run with:
    python -m pytest tests/test_webhook.py -v
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.webhook import (
    build_slack_payload,
    build_discord_payload,
    build_generic_payload,
    build_payload,
    detect_webhook_type,
    send_webhook,
)

# Common test parameters
REPO = "delimit-ai/example-api"
PR_NUMBER = 42
PR_TITLE = "Update user endpoints"
BREAKING = 3
ADDITIVE = 1
SEMVER = "MAJOR"
PR_URL = "https://github.com/delimit-ai/example-api/pull/42"


class TestDetectWebhookType(unittest.TestCase):
    """Tests for webhook type detection from URL."""

    def test_slack_url(self):
        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        self.assertEqual(detect_webhook_type(url), "slack")

    def test_discord_url(self):
        url = "https://discord.com/api/webhooks/123456/abcdef"
        self.assertEqual(detect_webhook_type(url), "discord")

    def test_generic_url(self):
        url = "https://example.com/webhook"
        self.assertEqual(detect_webhook_type(url), "generic")

    def test_generic_for_unknown(self):
        url = "https://api.pagerduty.com/hooks/abc"
        self.assertEqual(detect_webhook_type(url), "generic")


class TestBuildSlackPayload(unittest.TestCase):
    """Tests for Slack payload formatting."""

    def test_structure(self):
        payload = build_slack_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("text", payload)
        self.assertIn("blocks", payload)
        self.assertEqual(len(payload["blocks"]), 1)

    def test_block_type(self):
        payload = build_slack_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        block = payload["blocks"][0]
        self.assertEqual(block["type"], "section")
        self.assertEqual(block["text"]["type"], "mrkdwn")

    def test_content_contains_key_info(self):
        payload = build_slack_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        text = payload["blocks"][0]["text"]["text"]
        self.assertIn(REPO, text)
        self.assertIn(str(PR_NUMBER), text)
        self.assertIn(PR_TITLE, text)
        self.assertIn("3 breaking", text)
        self.assertIn("MAJOR", text)
        self.assertIn(PR_URL, text)

    def test_is_valid_json(self):
        payload = build_slack_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        # Ensure it serializes without error
        serialized = json.dumps(payload)
        self.assertIsInstance(json.loads(serialized), dict)


class TestBuildDiscordPayload(unittest.TestCase):
    """Tests for Discord payload formatting."""

    def test_structure(self):
        payload = build_discord_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("embeds", payload)
        self.assertEqual(len(payload["embeds"]), 1)

    def test_embed_fields(self):
        payload = build_discord_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        embed = payload["embeds"][0]
        self.assertIn("title", embed)
        self.assertEqual(embed["color"], 15158332)
        self.assertEqual(embed["url"], PR_URL)
        self.assertEqual(len(embed["fields"]), 4)

    def test_field_values(self):
        payload = build_discord_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        fields = payload["embeds"][0]["fields"]
        field_map = {f["name"]: f["value"] for f in fields}
        self.assertEqual(field_map["Repo"], REPO)
        self.assertIn(str(PR_NUMBER), field_map["PR"])
        self.assertIn("3 breaking", field_map["Changes"])
        self.assertEqual(field_map["Semver"], SEMVER)

    def test_all_fields_inline(self):
        payload = build_discord_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        for field in payload["embeds"][0]["fields"]:
            self.assertTrue(field["inline"])

    def test_is_valid_json(self):
        payload = build_discord_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        serialized = json.dumps(payload)
        self.assertIsInstance(json.loads(serialized), dict)


class TestBuildGenericPayload(unittest.TestCase):
    """Tests for generic webhook payload formatting."""

    def test_structure(self):
        payload = build_generic_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertEqual(payload["event"], "breaking_changes_detected")
        self.assertEqual(payload["repo"], REPO)
        self.assertEqual(payload["pr_number"], PR_NUMBER)
        self.assertEqual(payload["pr_title"], PR_TITLE)
        self.assertEqual(payload["breaking_changes"], BREAKING)
        self.assertEqual(payload["additive_changes"], ADDITIVE)
        self.assertEqual(payload["semver"], SEMVER)
        self.assertEqual(payload["pr_url"], PR_URL)

    def test_is_valid_json(self):
        payload = build_generic_payload(REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        serialized = json.dumps(payload)
        self.assertIsInstance(json.loads(serialized), dict)


class TestBuildPayload(unittest.TestCase):
    """Tests for the build_payload dispatcher."""

    def test_dispatches_to_slack(self):
        payload = build_payload("slack", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("blocks", payload)

    def test_dispatches_to_discord(self):
        payload = build_payload("discord", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("embeds", payload)

    def test_dispatches_to_generic(self):
        payload = build_payload("generic", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertEqual(payload["event"], "breaking_changes_detected")

    def test_unknown_type_falls_back_to_generic(self):
        payload = build_payload("unknown", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertEqual(payload["event"], "breaking_changes_detected")


class TestSendWebhook(unittest.TestCase):
    """Tests for the send_webhook function."""

    def test_empty_url_returns_false(self):
        result = send_webhook("", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertFalse(result)

    def test_blank_url_returns_false(self):
        result = send_webhook("   ", REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertFalse(result)

    def test_none_url_returns_false(self):
        result = send_webhook(None, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertFalse(result)

    @patch("core.webhook.urllib.request.urlopen")
    def test_successful_slack_post(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        result = send_webhook(url, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertTrue(result)

        # Verify the request was made with correct content type
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(req.method, "POST")

    @patch("core.webhook.urllib.request.urlopen")
    def test_successful_discord_post(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 204  # Discord returns 204 No Content
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = "https://discord.com/api/webhooks/123456/abcdef"
        result = send_webhook(url, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertTrue(result)

    @patch("core.webhook.urllib.request.urlopen")
    def test_network_error_returns_false(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")

        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        result = send_webhook(url, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertFalse(result)

    @patch("core.webhook.urllib.request.urlopen")
    def test_timeout_returns_false(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        result = send_webhook(url, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertFalse(result)

    @patch("core.webhook.urllib.request.urlopen")
    def test_payload_sent_as_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        send_webhook(url, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("blocks", body)  # Slack format


class TestEndToEndPayloads(unittest.TestCase):
    """Integration tests verifying full URL-to-payload pipeline."""

    def test_slack_url_produces_slack_payload(self):
        url = "https://hooks.slack.com/services/T00/B00/xxxx"
        wh_type = detect_webhook_type(url)
        payload = build_payload(wh_type, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("blocks", payload)
        self.assertIn("text", payload)

    def test_discord_url_produces_discord_payload(self):
        url = "https://discord.com/api/webhooks/123456/abcdef"
        wh_type = detect_webhook_type(url)
        payload = build_payload(wh_type, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertIn("embeds", payload)

    def test_custom_url_produces_generic_payload(self):
        url = "https://myapp.example.com/hooks/delimit"
        wh_type = detect_webhook_type(url)
        payload = build_payload(wh_type, REPO, PR_NUMBER, PR_TITLE, BREAKING, ADDITIVE, SEMVER, PR_URL)
        self.assertEqual(payload["event"], "breaking_changes_detected")
        self.assertEqual(payload["breaking_changes"], 3)


if __name__ == "__main__":
    unittest.main()
