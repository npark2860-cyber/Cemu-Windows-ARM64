"""Asset/config regression test; no game files or controller required."""
import configparser
import hashlib
from pathlib import Path
import json
import struct
import unittest

PACK = Path(__file__).resolve().parents[2] / 'enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified'


class UnifiedPackTests(unittest.TestCase):
    def setUp(self):
        self.routes = configparser.ConfigParser(interpolation=None)
        self.routes.read(PACK / 'sound_routes.ini', encoding='utf-8')
        self.original = json.loads((PACK / 'upstream-v3-provenance.json').read_text(encoding='utf-8'))

    def test_original_settings_and_assets_preserved(self):
        names = self.routes.sections()
        self.assertEqual(len(names), 71)
        self.assertEqual(names[8:], list(self.original['original_routes']))
        for name, settings in self.original['original_routes'].items():
            self.assertEqual(dict(self.routes[name]), settings, name)
        for name, digest in self.original['original_asset_sha256'].items():
            self.assertEqual(hashlib.sha256((PACK / 'haptics' / name).read_bytes()).hexdigest(), digest)

    def test_motorcycle_precedence_and_opt_in(self):
        names = self.routes.sections()
        for name in names[:8]:
            rule = self.routes[name]
            self.assertEqual(rule['mode'], 'spatial_drc')
            self.assertEqual(rule['haptic_follow_tv'], 'true')
            self.assertNotIn('*', rule['track'])
            fallback = 'Route.MasterCycleEngine' if rule['source'].startswith('D_') else 'Route.MasterCycleMain'
            self.assertLess(names.index(name), names.index(fallback))
        for name in names[8:]:
            self.assertNotIn('haptic_follow_tv', self.routes[name])

    def test_all_referenced_bnvib_assets(self):
        used = set()
        for name in self.routes.sections():
            rule = self.routes[name]
            if 'haptic' not in rule:
                continue
            path = (PACK / 'haptics' / rule['haptic']).resolve()
            self.assertEqual(path.parent, (PACK / 'haptics').resolve())
            used.add(path)
            data = path.read_bytes()
            meta, version, rate = struct.unpack_from('<IHH', data)
            self.assertIn(meta, (4, 12, 16))
            self.assertEqual(version, 3)
            self.assertGreater(rate, 0)
            length = struct.unpack_from('<I', data, meta + 4)[0]
            self.assertEqual(length % 4, 0)
            self.assertEqual(len(data), meta + 8 + length)
            if rule.getboolean('haptic_loop', fallback=False):
                self.assertIn(meta, (12, 16))
                start, end = struct.unpack_from('<II', data, 8)
                self.assertLess(start, end)
                self.assertLessEqual(end, length // 4)
        self.assertEqual(len(used), 11)
        self.assertEqual(used, set((PACK / 'haptics').glob('*.bnvib')))


if __name__ == '__main__':
    unittest.main()
