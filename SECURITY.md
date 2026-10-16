# Security Policy

The OmniPost team takes security and sovereign credential management seriously. OmniPost interacts with user authentication cookies, local browser profiles, and API tokens; protecting your operating environment and personal credentials is our top priority.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability in OmniPost, **please do NOT disclose it publicly** via GitHub issues, discussions, or social channels.

Instead, please report it privately:

1. **GitHub Security Advisory (Recommended):** Submit an advisory through the repository's [Security Advisories](https://github.com/Lordporus/omnipost/security/advisories) tab.
2. **Direct Contact:** Email the maintainer directly at security disclosures / maintainer contact with:
   - A clear description of the vulnerability.
   - Step-by-step reproduction instructions or a minimal proof of concept (PoC).
   - The potential impact and attack vector.

### Response Timeline
- **Initial Acknowledgment:** Within 48 hours.
- **Triage & Status Update:** Within 5 business days.
- **Patch & Release:** High-severity issues will be prioritized and resolved with an emergency patch release.

---

## Sovereign Credential Hygiene & Best Practices

OmniPost is designed to operate locally without external telemetry. To maintain security on your host machine:

### 1. Guarding `.env` and `config.json`
- **Never commit `.env` or `config.json`** containing live credentials to any public or private repository. Both are included in `.gitignore`.
- Use `config.example.json` and `.env.example` as templates with mock placeholders.
- If you accidentally commit a secret, revoke and cycle the affected token immediately.

### 2. Browser Profile & Session Cookie Security
- OmniPost automates an authenticated browser profile located in `~/.omnipost/edge-profile` (or `~/.tweetytweets/edge-profile`).
- These profile directories contain persistent session cookies for your social accounts (X, LinkedIn, Threads).
- **Protect this directory:**
  - Ensure file permissions restrict access to your user account (`chmod 700 ~/.omnipost`).
  - Do not copy or sync your browser profile directory across unencrypted cloud backups.
  - Close the remote debugging port (`9444` / `9222`) or firewall it from external network interfaces when not in use (OmniPost binds to `127.0.0.1` by default).

### 3. Granular API & App Passwords
- **Bluesky:** Always use **App Passwords** (created via Bluesky Settings > App Passwords) rather than your master account password.
- **LLM Providers:** Assign API keys with minimal necessary scopes, usage caps, and rate limits.
- **Webhooks:** Store Telegram Bot Tokens and Discord Webhook URLs securely in `.env`.

### 4. VPS & Server Deployment
- When hosting on a VPS, run OmniPost under a dedicated, non-privileged system user (e.g., `omnipost`), never as root.
- Keep system packages, Edge/Chromium, and Python dependencies updated with security patches.
