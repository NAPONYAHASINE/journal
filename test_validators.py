import unittest
from validators import sanitize_string, is_valid_email, MAX_STRING_LENGTH

class TestValidators(unittest.TestCase):
    def test_sanitize_string_normal(self):
        # Test cas normal
        is_valid, result = sanitize_string("Test normal")
        self.assertTrue(is_valid)
        self.assertEqual(result, "Test normal")

    def test_sanitize_string_empty(self):
        # Test chaîne vide
        is_valid, result = sanitize_string("")
        self.assertTrue(is_valid)  # car allow_empty est True par défaut
        self.assertEqual(result, "")
        
        # Test chaîne vide non autorisée
        is_valid, result = sanitize_string("", allow_empty=False)
        self.assertFalse(is_valid)

    def test_sanitize_string_length(self):
        # Test longueur minimum
        is_valid, result = sanitize_string("a", min_length=2)
        self.assertFalse(is_valid)
        
        # Test longueur maximum
        long_string = "a" * (MAX_STRING_LENGTH + 1)
        is_valid, result = sanitize_string(long_string)
        self.assertFalse(is_valid)

    def test_sanitize_string_whitespace(self):
        # Test nettoyage espaces
        is_valid, result = sanitize_string("  test  ")
        self.assertTrue(is_valid)
        self.assertEqual(result, "test")

    def test_valid_email(self):
        # Test emails valides
        self.assertTrue(is_valid_email("test@example.com"))
        self.assertTrue(is_valid_email("user.name+tag@example.co.uk"))
        
        # Test emails invalides
        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email("invalid.email"))
        self.assertFalse(is_valid_email("test@.com"))
        self.assertFalse(is_valid_email("test@com"))
        self.assertFalse(is_valid_email("test..test@example.com"))

if __name__ == '__main__':
    unittest.main()