import io
import unittest
import tempfile
from pathlib import Path
import zipfile

from promo_finder.parser import parse_episode, parse_zip_bytes, parse_timestamp, format_timestamp, load_episodes


SCRIPT = '''EPISODE NUMBER: Episode 1
EPISODE LOGLINE: A fictional test scene.
CONTINUITY NOTES: Synthetic, not from the assignment pack.

--- SCRIPT START ---
SCENE 01
Scene heading: INT. HALL - DAY
Scene start: 00:00.00
Scene end: 00:30.00

**CAMERA:**
Start: (00:00.00) | End: (00:10.00)
A camera follows the messenger.

**MESSENGER (Urgent):**
Start: (00:02.00) | End: (00:06.50)
"The letter is missing."
"Who took it?"

**ACTION:**
Start: (00:06.50) | End: (00:30.00)
A shadow moves beyond the door.

--- SCRIPT END ---
'''


def archive(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as out:
        for name, content in entries:
            out.writestr(name, content)
    return result.getvalue()


class ParserTests(unittest.TestCase):
    def test_overlapping_events_do_not_inflate_duration(self):
        ep = parse_episode(SCRIPT, "synthetic.txt")
        self.assertEqual(ep.duration, 30.0)
        self.assertEqual(len(ep.events), 3)
        self.assertEqual(ep.events[1].id, "e002")
        self.assertEqual(ep.events[1].speaker, "MESSENGER")
        self.assertEqual(ep.events[1].kind, "dialogue")
        self.assertIn("Who took it?", ep.events[1].text)
        self.assertEqual(ep.warnings, [])

    def test_uppercase_scene_fields(self):
        ep = parse_episode(SCRIPT.replace("Scene start", "SCENE START").replace("Scene end", "SCENE END"))
        self.assertEqual(ep.duration, 30.0)
        self.assertEqual(ep.warnings, [])

    def test_two_scenes_do_not_leak_structure_into_event_text(self):
        second = '''SCENE 02
Scene start: 00:30.00
Scene end: 00:35.00

**SOUND FX:**
Start: (00:30.00) | End: (00:35.00)
A door bangs.

--- SCRIPT END ---'''
        ep = parse_episode(SCRIPT.replace("--- SCRIPT END ---", second))
        self.assertEqual(ep.duration, 35)
        self.assertNotIn("SCENE", ep.events[2].text)
        self.assertEqual(ep.events[3].kind, "sound")

    def test_invalid_timing_rejected(self):
        for invalid in ["00:77.00", "no time", "-1:00"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_episode(SCRIPT.replace("00:06.50", invalid))
        with self.assertRaises(ValueError):
            parse_episode(SCRIPT.replace("Start: (00:02.00)", "Start: 00:02.00"))
        with self.assertRaises(ValueError):
            parse_episode(SCRIPT.replace("End: (00:06.50)", "End: (00:01.00)"))

    def test_orphan_timestamp_rejected(self):
        orphan = "Start: (00:01.00) | End: (00:02.00)\nLost block\n"
        with self.assertRaises(ValueError):
            parse_episode(SCRIPT.replace("SCENE 01", orphan + "SCENE 01"))

    def test_duplicate_episode_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate episode"):
            parse_zip_bytes(archive([("a.txt", SCRIPT), ("b.txt", SCRIPT)]))

    def test_archive_paths_cannot_escape(self):
        for name in ["../episode.txt", "/episode.txt", "C:/episode.txt"]:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unsafe path"):
                parse_zip_bytes(archive([(name, SCRIPT)]))

    def test_zip_reads_nested_files_in_episode_order(self):
        eps = parse_zip_bytes(archive([("nested/two.txt", SCRIPT.replace("Episode 1", "Episode 2")), ("one.txt", SCRIPT)]))
        self.assertEqual([ep.number for ep in eps], [1, 2])

    def test_missing_scene_bounds_warns(self):
        ep = parse_episode(SCRIPT.replace("Scene start: 00:00.00\nScene end: 00:30.00\n", ""))
        self.assertEqual(ep.duration, 30)
        self.assertTrue(ep.warnings)

    def test_out_of_bounds_event_warns_without_changing_duration(self):
        ep = parse_episode(SCRIPT.replace("End: (00:30.00)", "End: (00:31.00)"))
        self.assertEqual(ep.duration, 30)
        self.assertTrue(ep.warnings)

    def test_directory_supports_uppercase_txt_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "episode.TXT").write_text(SCRIPT)
            self.assertEqual(len(load_episodes(directory)), 1)

    def test_timestamp_rounding_carry_and_hours(self):
        self.assertEqual(format_timestamp(59.999), "01:00.00")
        self.assertEqual(parse_timestamp("01:02:03.40"), 3723.4)
        self.assertEqual(parse_timestamp("62:03.40"), 3723.4)
        with self.assertRaises(ValueError):
            format_timestamp(float("nan"))


if __name__ == "__main__":
    unittest.main()
