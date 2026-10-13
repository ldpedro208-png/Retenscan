# biblioteca/tests/test_sanitizer.py
from django.test import TestCase
from biblioteca.utils.sanitizer import sanitizar_html, contiene_html_peligroso


class SanitizerTests(TestCase):

    def test_elimina_script(self):
        result = sanitizar_html('<script>alert(1)</script>Hola')
        self.assertNotIn('<script', result)
        self.assertIn('Hola', result)

    def test_elimina_onerror(self):
        result = sanitizar_html('<img src="x" onerror="alert(1)">')
        self.assertNotIn('onerror', result)
        self.assertIn('<img', result)

    def test_elimina_javascript_href(self):
        result = sanitizar_html('<a href="javascript:alert(1)">X</a>')
        self.assertNotIn('javascript:', result)

    def test_elimina_iframe(self):
        result = sanitizar_html('<iframe src="https://malo.com"></iframe>')
        self.assertNotIn('<iframe', result)

    def test_mantiene_html_legitimo(self):
        html = '<h2>Título</h2><p>Texto <strong>importante</strong></p>'
        result = sanitizar_html(html)
        self.assertIn('<h2>', result)
        self.assertIn('<strong>', result)

    def test_detecta_peligro(self):
        self.assertTrue(contiene_html_peligroso('<script>x</script>'))
        self.assertFalse(contiene_html_peligroso('<p>ok</p>'))