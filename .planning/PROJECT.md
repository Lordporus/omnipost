# OmniPost: Multi-Platform Autonomous Publishing Pipeline

## What This Project Is

OmniPost is an autonomous multi-platform content publishing and verification engine for AI agents. It researches raw discussions across free open feeds (Hacker News, RSS/Atom, Reddit, X), reformulates insights according to empirical channel voice profiles, and publishes/verifies them across social networks (X, Bluesky, LinkedIn, Threads) without recurring SaaS or predatory API subscriptions.

## Core Problem It Solves

- **Predatory API Fees:** X charges \$215+/month for basic developer read access; LinkedIn has restrictive enterprise partner walls; traditional tools incur high recurring API fees.
- **Generic Bot Detection:** Naive automation uses uncalibrated spam patterns, leading to bans and account penalties.
- **Unverified Deliveries:** Systems trust API return codes or UI toast notifications, leading to silent failures.
- **Partial Failure Cascade:** Multi-platform broadcasters often fail atomically—retrying a failed post causes duplicate content on already-published channels.

## Key Principles & Architectural Invariants

1. **Zero-Cost Open Intelligence:** Research relies on open endpoints (Algolia HN, RSS XML, Reddit rendered DOM, X search).
2. **Direct Browser Control via CDP:** Chrome DevTools Protocol over WebSockets with standard Python (`websockets>=12.0`). Zero heavy frameworks.
3. **Closed-Loop Verification:** Refuses to trust toasts; reads back public profile feeds and captures viewport screenshots before closing slots.
4. **Deterministic Idle Gate:** Evaluates schedules with lightweight Python scripts; emits byte-identical `IDLE` strings during downtime to ensure zero LLM token costs when idle.
5. **Atomic Multi-Platform Ledger:** Each channel operates independently with per-platform status tracking in `state.json` to prevent double-posting during retries.
6. **Zero-Dependency Visuals:** Generates dark-mode 16:9 infocards with Pillow and vector PDF carousels using CDP `Page.printToPDF` (no `weasyprint` or native C-library headaches).

## Current State

- **OmniPost V1.0.1:** Released and verified for autonomous X publishing.
- **OmniPost V2:** Multi-platform expansion defined in `docs/EXPANSION_BLUEPRINT_MULTI_PLATFORM.md`.
