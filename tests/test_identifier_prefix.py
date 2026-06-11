import unittest

import quark_auto_save


class IdentifierPrefixTest(unittest.TestCase):
    def test_identifier_prefix_accepts_numeric_identifiers_without_crashing(self):
        self.assertFalse(quark_auto_save.identifier_startswith(123, "extracted_"))
        self.assertTrue(quark_auto_save.identifier_startswith("extracted_dir_123", "extracted_"))


if __name__ == "__main__":
    unittest.main()
