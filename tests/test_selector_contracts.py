"""Selector-contract tests against frozen DOM fixtures.

The fixtures mirror the structures the adapters target. A selector rename or a
wrong-element match fails here instead of only in a live browser, without
requiring Chrome or a logged-in session.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from adapters.linkedin import LINKEDIN_COMPOSER_SELECTORS
from scripts.errors import SelectorError
from scripts.post import EDITOR, FILE_INPUT, POST_BTN

FIXTURES = Path(__file__).parent / "fixtures" / "dom"


def _soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


def test_linkedin_share_box_selector_finds_exactly_one_trigger():
    soup = _soup("linkedin_feed.html")

    triggers = soup.select('button[id*="share-box"]')
    assert len(triggers) == 1
    assert "start a post" in triggers[0].get_text(" ", strip=True).lower()

    matches = [sel for sel in LINKEDIN_COMPOSER_SELECTORS if soup.select_one(sel)]
    assert matches, f"no composer selector matched; tried {LINKEDIN_COMPOSER_SELECTORS}"


def test_generic_tertiary_button_is_not_used_as_fallback():
    soup = _soup("linkedin_feed.html")

    tertiary = soup.select(".artdeco-button--tertiary")
    assert tertiary, "fixture must include a tertiary Like/Comment button"

    assert all("artdeco-button--tertiary" not in sel for sel in LINKEDIN_COMPOSER_SELECTORS)
    for decoy in tertiary:
        for sel in LINKEDIN_COMPOSER_SELECTORS:
            assert soup.select_one(sel) is not decoy


def test_linkedin_dialog_and_editor_selectors_find_editor():
    soup = _soup("linkedin_feed.html")

    dialog = soup.select_one('div[role="dialog"]')
    assert dialog is not None
    assert dialog.select_one('div[contenteditable="true"]') is not None

    submit = soup.select_one("button.share-actions__primary-action")
    assert submit is not None
    assert submit.get_text(strip=True).lower() == "post"

    assert soup.select_one('input[type="file"][accept*="image"]') is not None


def test_threads_permalink_selector_finds_post_anchor():
    soup = _soup("threads_composer.html")

    trigger = soup.select_one('div[role="button"][aria-label*="Create" i]')
    assert trigger is not None
    editor = soup.select_one('div[contenteditable="true"][role="textbox"]')
    assert editor is not None
    assert editor.get("data-lexical-editor") == "true"

    permalink = soup.select_one('div[role="alert"] a[href*="/post/"]')
    assert permalink is not None
    assert "/post/" in permalink.get("href", "")


def test_x_submit_and_media_selectors_find_targets():
    soup = _soup("x_composer.html")

    editor = soup.select_one(EDITOR)
    assert editor is not None
    assert editor.get("data-testid") == "tweetTextarea_0"

    submit = soup.select_one(POST_BTN)
    assert submit is not None
    assert submit.get("data-testid") == "tweetButton"

    media = soup.select_one(FILE_INPUT)
    assert media is not None
    assert media.get("data-testid") == "fileInput"

    decoy = soup.select_one('[data-testid="likeButton"]')
    assert decoy is not None
    assert decoy.get("data-testid") != "tweetButton"


def test_missing_selector_raises_selector_error_with_context():
    soup = _soup("linkedin_feed.html")
    missing = 'button[data-testid="missing-composer-trigger"]'
    assert soup.select_one(missing) is None

    with pytest.raises(SelectorError) as excinfo:
        raise SelectorError(
            f"linkedin selector miss: {missing}",
            platform="linkedin",
            stage="composer_open",
            selector=missing,
            context={"candidates": 0},
        )

    error = excinfo.value
    assert missing in str(error)
    assert error.platform == "linkedin"
    assert error.stage == "composer_open"
    assert error.selector == missing
    assert error.context["candidates"] == 0
