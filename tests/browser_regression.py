"""Optional browser checks: pip install playwright; playwright install chromium.

Run: python tests/browser_regression.py
Set CHROMIUM_PATH to use a system Chromium instead of Playwright's browser.
No test dependencies are required to run the static app.
"""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
KEY = 'immersive-message-maker-v4'


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith('/test-image.svg'):
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.end_headers()
            self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="#745668"/><circle cx="200" cy="100" r="80" fill="#f2e9ef"/></svg>')
        else:
            super().do_GET()


class AssetsRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'
        cls.image = cls.origin + '/test-image.svg?one=1&two=2'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, permissions=['clipboard-read', 'clipboard-write'])
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.origin)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def preset(self, name):
        self.page.locator('#preset').select_option(name)

    def html(self):
        return self.page.locator('#htmlOutput').input_value()

    def saved(self):
        return self.page.evaluate('(key) => JSON.parse(localStorage.getItem(key))', KEY)

    def image_control(self, selector, index=0):
        return self.page.locator(selector + ' .image-input').nth(index)

    def set_image(self, control):
        control.locator('input').fill(self.image)
        expect(control.locator('.image-status')).to_have_text('Image ready.')
        expect(control.locator('img')).to_be_visible()

    def check_copy(self):
        expected = self.html()
        self.page.locator('#copyHtmlBtn').click()
        expect(self.page.locator('#status')).to_contain_text('HTML copied')
        self.assertEqual(self.page.evaluate('navigator.clipboard.readText()'), expected)
        self.assertNotIn('<script', expected)
        self.assertNotIn('onerror=', expected)
        return expected

    def test_presets_copy_and_old_draft(self):
        # Existing v4 drafts have no avatar fields and retain the same storage key.
        self.page.locator('#chatTitle').fill('Old draft')
        old = self.saved()
        self.assertNotIn('avatarUrl', old['xpost']['items'][0])
        for preset, text in [('imessage', 'Delivered'), ('stream', '$20.00'), ('xpost', 'irrelevant'), ('wechat', 'Old draft')]:
            self.preset(preset)
            expect(self.page.locator('#preview')).to_contain_text(text)
            self.check_copy()
        self.page.reload()
        expect(self.page.locator('#chatTitle')).to_have_value('Old draft')
        self.assertEqual(self.saved()['chat'], old['chat'])

    def test_x_thread_avatar_edit_reorder_and_autosave(self):
        self.preset('xpost')
        self.set_image(self.image_control('#xList'))
        self.page.locator('#xList .verified-input').first.check()
        self.page.locator('#xList .likes-input').first.fill('1234')
        expect(self.page.locator('#preview img')).to_have_count(1)
        self.assertEqual(self.page.locator('#preview img').evaluate('(el) => [el.width, el.height]'), [42, 42])
        expect(self.page.locator('#preview')).to_contain_text('1.2K')
        self.page.locator('#xList .duplicate-item').first.click()
        expect(self.page.locator('#preview img')).to_have_count(2)
        self.page.locator('#xList .move-down').nth(1).click()
        self.assertEqual([i.get('avatarUrl', '') for i in self.saved()['xpost']['items']], [self.image, '', self.image, ''])
        self.preset('stream')
        self.preset('xpost')
        self.page.reload()
        expect(self.image_control('#xList', 2).locator('input')).to_have_value(self.image)
        exported = self.check_copy()
        self.assertIn('&amp;two=2', exported)
        self.page.locator('#copyJsonBtn').click()
        expect(self.page.locator('#status')).to_have_text('JSON copied.')
        copied = json.loads(self.page.evaluate('navigator.clipboard.readText()'))
        self.assertEqual(copied['content']['items'][2]['avatarUrl'], self.image)
        self.image_control('#xList').locator('button').click()
        expect(self.page.locator('#preview img')).to_have_count(1)
        self.page.locator('#xList .delete-item').nth(2).click()
        expect(self.page.locator('#preview img')).to_have_count(0)
        self.assertIn('>W</div>', self.html())

    def test_stream_donation_and_notice(self):
        self.preset('stream')
        self.set_image(self.image_control('#streamList'))
        self.set_image(self.image_control('#streamList', 2))
        self.page.locator('#streamList .amount-input').fill('$123.45')
        expect(self.page.locator('#preview')).to_contain_text('$123.45')
        expect(self.page.locator('#preview')).to_contain_text('SUB')
        expect(self.page.locator('#preview')).to_contain_text('MOD')
        expect(self.page.locator('#preview img')).to_have_count(2)
        self.assertEqual(self.page.locator('#preview img').first.evaluate('(el) => [el.width, el.height]'), [24, 24])
        self.page.locator('#addStreamNoticeBtn').click()
        expect(self.page.locator('#preview')).to_contain_text('Chat resumed')
        self.page.reload()
        self.assertEqual(self.saved()['stream']['items'][2]['avatarUrl'], self.image)
        self.check_copy()
        self.image_control('#streamList', 2).locator('button').click()
        expect(self.page.locator('#preview')).to_contain_text('$123.45')

    def test_sticker_voice_and_script_free_paste(self):
        control = self.image_control('#messageList')
        self.set_image(control)
        img = self.page.locator('#preview img')
        expect(img).to_be_visible()
        self.page.wait_for_function('document.querySelector("#preview img").naturalWidth > 0')
        self.assertEqual(img.evaluate('(el) => [el.width, el.height]'), [128, 64])
        self.assertEqual(img.get_attribute('alt'), 'saluting / understood')
        self.page.locator('#preview summary').click()
        expect(self.page.locator('#preview details')).to_have_attribute('open', '')
        expect(self.page.locator('#preview details')).to_contain_text('Eat something before you leave.')
        html = self.check_copy()
        # Paste into a script-disabled document with intrusive host theme styles.
        pasted_context = self.browser.new_context(java_script_enabled=False)
        pasted = pasted_context.new_page()
        pasted.set_content('<style>img{width:100%;height:300px;display:block}summary{padding:30px;background:red;border:10px solid red}</style>' + html)
        pasted.locator('summary').click()
        expect(pasted.locator('details')).to_have_attribute('open', '')
        expect(pasted.locator('details')).to_contain_text('Eat something before you leave.')
        self.assertLessEqual(pasted.locator('img').bounding_box()['height'], 128)
        pasted_context.close()
        self.preset('imessage')
        expect(self.page.locator('#preview')).to_contain_text('Sticker — saluting / understood')
        expect(self.page.locator('#preview img')).to_have_count(0)
        self.preset('wechat')
        self.page.reload()
        expect(self.image_control('#messageList').locator('input')).to_have_value(self.image)
        self.image_control('#messageList').locator('input').fill('😤')
        expect(self.page.locator('#preview')).to_contain_text('😤')
        expect(self.page.locator('#preview img')).to_have_count(0)

    def test_invalid_broken_and_escaped_images(self):
        self.preset('xpost')
        control = self.image_control('#xList')
        for invalid in ['javascript:alert(1)', 'data:image/svg+xml,<svg/>', 'blob:temporary', '/relative.png', 'https://']:
            control.locator('input').fill(invalid)
            expect(control.locator('input')).to_have_attribute('aria-invalid', 'true')
            expect(self.page.locator('#preview img')).to_have_count(0)
        control.locator('input').fill(self.origin + '/missing-image.png')
        expect(control.locator('.image-status')).to_contain_text('could not load')
        expect(control.locator('img')).to_be_hidden()
        self.set_image(control)
        self.page.locator('#xList .author-input').first.fill('\"><svg onload=alert(1)>')
        expect(self.page.locator('#preview svg')).to_have_count(0)
        control.locator('button').click()
        expect(control.locator('img')).to_be_hidden()
        self.assertEqual(self.saved()['xpost']['items'][0]['avatarUrl'], '')

    def test_mobile_and_desktop_layout(self):
        for width in [320, 390, 768, 1280]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            for preset, selector in [('wechat', '#messageList'), ('imessage', '#messageList'), ('stream', '#streamList'), ('xpost', '#xList')]:
                self.preset(preset)
                self.set_image(self.image_control(selector))
                if preset == 'stream':
                    self.set_image(self.image_control(selector, 2))
                    self.page.locator('#streamList .amount-input').fill('$' + '9' * 39)
                if preset == 'xpost':
                    self.page.locator('#xList .author-input').first.fill('A' * 80)
                    self.page.locator('#xList .handle-input').first.fill('@' + 'a' * 79)
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, preset))
                self.assertTrue(self.page.locator('#preview').evaluate('(el) => el.scrollWidth <= el.clientWidth'), (width, preset))
                self.assertTrue(self.image_control(selector).evaluate('(el) => el.scrollWidth <= el.clientWidth'), (width, preset))

    def test_standalone_parity(self):
        self.assertEqual((ROOT / 'index.html').read_bytes(), (ROOT / 'immersive-message-maker-standalone.html').read_bytes())
        self.page.goto(self.origin + '/immersive-message-maker-standalone.html')
        self.preset('xpost')
        self.set_image(self.image_control('#xList'))
        self.check_copy()


if __name__ == '__main__':
    unittest.main(verbosity=2)
