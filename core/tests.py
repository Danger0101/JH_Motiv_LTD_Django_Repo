from django.test import TestCase
from django.conf import settings
import os
import re
from .cheats import CHEAT_CODES

class CheatCodeIntegrityTest(TestCase):
    def test_cheats_py_matches_engine_js(self):
        """
        Verifies that every cheat ID defined in core/cheats.py exists in static/js/cheats/engine.js.
        This ensures we don't define a cheat on the server that is impossible to trigger on the client.
        """
        # 1. Get IDs from Python
        python_ids = set(CHEAT_CODES.keys())

        # 2. Get IDs from JavaScript
        # Construct path to engine.js relative to project root
        js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'cheats', 'engine.js')
        
        if not os.path.exists(js_path):
            self.fail(f"Could not find engine.js at {js_path}")

        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Regex to extract IDs mapped to SHA-256 hashes
        # Looks for: "hash": 123
        # Matches a 64-char hex string (SHA-256) in quotes, colon, whitespace, integer
        matches = re.findall(r'"[a-fA-F0-9]{64}"\s*:\s*(\d+)', js_content)
        js_ids = set(int(m) for m in matches)

        # 3. Assertions
        missing_in_js = python_ids - js_ids
        missing_in_python = js_ids - python_ids

        self.assertEqual(
            len(missing_in_js), 
            0, 
            f"Cheat IDs defined in core/cheats.py but missing in engine.js: {missing_in_js}"
        )
        
        self.assertEqual(
            len(missing_in_python), 
            0, 
            f"Cheat IDs found in engine.js but not defined in core/cheats.py: {missing_in_python}"
        )
