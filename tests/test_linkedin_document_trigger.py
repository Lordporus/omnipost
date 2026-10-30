"""Regression tests for the LinkedIn document trigger.

Measured live on 2026-10-29. The 2026-10-27 failure came from the trigger falling
back to the composer header's ``aria-label="More"`` button, which opens
Groups/Events/Newsletters and can never reach a document picker.

The working path is: expand the content-type row, click the "Document" anchor
(which navigates to the document composer), capture the on-demand PDF input
created by "Choose file", set the title, then Done.
"""
import inspect
import unittest

from adapters.linkedin import (
    CAPTURE_FILE_INPUT_JS,
    CHOOSE_FILE_JS,
    CLICK_DOCUMENT_ITEM_JS,
    DOCUMENT_TITLE_JS,
    EXPAND_CONTENT_TYPES_JS,
    POINTER_CLICK_JS,
    LinkedInAdapter,
)

DOCUMENT_JS = (
    POINTER_CLICK_JS
    + EXPAND_CONTENT_TYPES_JS
    + CLICK_DOCUMENT_ITEM_JS
    + CAPTURE_FILE_INPUT_JS
    + CHOOSE_FILE_JS
    + DOCUMENT_TITLE_JS
)


class TestDocumentTrigger(unittest.TestCase):
    def test_never_targets_the_header_more_menu(self):
        self.assertNotIn('aria-label*="More"', DOCUMENT_JS)
        self.assertNotIn("overflow", DOCUMENT_JS.lower())

    def test_expand_targets_the_content_type_button(self):
        self.assertIn('button[aria-label="Expand content types"]', EXPAND_CONTENT_TYPES_JS)

    def test_document_control_is_an_anchor(self):
        # It is an <a>, not a <button>; every button-only query missed it.
        self.assertIn('a[aria-label="Document"]', CLICK_DOCUMENT_ITEM_JS)

    def test_clicks_dispatch_a_full_pointer_sequence(self):
        # Input.dispatchMouseEvent is dropped when the tab is hidden.
        for event in ("PointerEvent('pointerdown'", "MouseEvent('mousedown'",
                      "PointerEvent('pointerup'", "MouseEvent('mouseup'",
                      "MouseEvent('click'"):
            self.assertIn(event, POINTER_CLICK_JS)

    def test_file_input_is_captured_instead_of_opening_the_os_dialog(self):
        self.assertIn("__fileInput", CAPTURE_FILE_INPUT_JS)
        self.assertIn("this.type === 'file'", CAPTURE_FILE_INPUT_JS)

    def test_title_uses_the_native_setter(self):
        # React ignores a plain `input.value = ...`, leaving Done disabled.
        self.assertIn("HTMLInputElement.prototype, 'value'", DOCUMENT_TITLE_JS)
        self.assertIn("_valueTracker", DOCUMENT_TITLE_JS)
        self.assertIn("doneBtn.disabled", DOCUMENT_TITLE_JS)

    def test_fast_path_only_accepts_pdf_inputs(self):
        src = inspect.getsource(LinkedInAdapter._attach_document)
        self.assertIn('input[type="file"][accept*="pdf"]', src)
        self.assertNotIn("overflow_clicked", src)
        self.assertNotIn("dispatchMouseEvent", src)

    def test_uploads_by_object_id_when_the_input_is_captured(self):
        src = inspect.getsource(LinkedInAdapter._attach_document)
        self.assertIn("objectId=object_id", src)
        self.assertIn("window.__fileInput", src)


if __name__ == "__main__":
    unittest.main()
