"""
Webhook notification support for Slack, Discord, and generic endpoints.

Sends formatted breaking change notifications when a webhook URL is configured.
"""

import json
import urllib.request
import urllib.error


def build_slack_payload(repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url):
    """Build a Slack Block Kit payload."""
    lines = [
        "*:red_circle: Breaking API Changes Detected*",
        f"*Repo:* {repo}",
        f"*PR:* #{pr_number} — {pr_title}",
        f"*Changes:* {breaking_count} breaking, {additive_count} additive",
        f"*Semver:* {semver}",
        f"<{pr_url}|View PR>",
    ]
    return {
        "text": "Breaking API Changes Detected",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(lines),
                },
            }
        ],
    }


def build_discord_payload(repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url):
    """Build a Discord embed payload."""
    return {
        "embeds": [
            {
                "title": "\U0001f534 Breaking API Changes Detected",
                "color": 15158332,
                "fields": [
                    {"name": "Repo", "value": repo, "inline": True},
                    {"name": "PR", "value": f"#{pr_number} — {pr_title}", "inline": True},
                    {"name": "Changes", "value": f"{breaking_count} breaking, {additive_count} additive", "inline": True},
                    {"name": "Semver", "value": semver, "inline": True},
                ],
                "url": pr_url,
            }
        ],
    }


def build_generic_payload(repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url):
    """Build a generic JSON payload."""
    return {
        "event": "breaking_changes_detected",
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "breaking_changes": breaking_count,
        "additive_changes": additive_count,
        "semver": semver,
        "pr_url": pr_url,
    }


def detect_webhook_type(url):
    """Detect the webhook platform from the URL.

    Returns one of: 'slack', 'discord', 'generic'.
    """
    if "hooks.slack.com" in url:
        return "slack"
    elif "discord.com/api/webhooks" in url:
        return "discord"
    else:
        return "generic"


def build_payload(webhook_type, repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url):
    """Build the appropriate payload for the detected webhook type."""
    builders = {
        "slack": build_slack_payload,
        "discord": build_discord_payload,
        "generic": build_generic_payload,
    }
    builder = builders.get(webhook_type, build_generic_payload)
    return builder(repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url)


def send_webhook(url, repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url, timeout=10):
    """Send a webhook notification for breaking API changes.

    Args:
        url: The webhook endpoint URL.
        repo: Repository name (e.g., 'org/repo').
        pr_number: Pull request number.
        pr_title: Pull request title.
        breaking_count: Number of breaking changes.
        additive_count: Number of additive (non-breaking) changes.
        semver: Semver bump level (e.g., 'MAJOR').
        pr_url: Full URL to the pull request.
        timeout: HTTP request timeout in seconds.

    Returns:
        True if the webhook was sent successfully, False otherwise.
    """
    if not url or not url.strip():
        return False

    webhook_type = detect_webhook_type(url)
    payload = build_payload(webhook_type, repo, pr_number, pr_title, breaking_count, additive_count, semver, pr_url)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        # Log but never fail the action due to a webhook error
        print(f"::warning::Delimit webhook notification failed: {e}")
        return False
