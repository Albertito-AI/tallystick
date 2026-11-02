import tempfile
import unittest
from pathlib import Path
from publish_wiki import merge_pages, MARKER, START


class WikiPublicationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        self.wiki = self.root / 'wiki'
        self.source.mkdir()
        self.wiki.mkdir()
        (self.source / 'Whitepaper.md').write_text(MARKER + '\n# Paper\n')
        (self.source / 'Home.md').write_text('## Whitepaper\n[Read](Whitepaper)\n')

    def test_preserves_existing_home_and_other_pages(self):
        (self.wiki / 'Home.md').write_text('# Existing welcome\nPersonal text.\n')
        (self.wiki / 'History.md').write_text('Retained history')
        merge_pages(self.source, self.wiki)
        self.assertTrue((self.wiki / 'Home.md').read_text().startswith('# Existing welcome\nPersonal text.'))
        self.assertEqual((self.wiki / 'History.md').read_text(), 'Retained history')

    def test_repeated_update_is_idempotent_and_replaces_only_owned_block(self):
        merge_pages(self.source, self.wiki)
        original = (self.wiki / 'Home.md').read_text()
        merge_pages(self.source, self.wiki)
        self.assertEqual((self.wiki / 'Home.md').read_text(), original)
        (self.wiki / 'Home.md').write_text(original + '\nMaintainer addition\n')
        (self.source / 'Home.md').write_text('Updated link\n')
        merge_pages(self.source, self.wiki)
        result = (self.wiki / 'Home.md').read_text()
        self.assertIn('Maintainer addition', result)
        self.assertIn('Updated link', result)
        self.assertEqual(result.count(START), 1)

    def test_refuses_unmanaged_paper_without_overwriting(self):
        (self.wiki / 'Whitepaper.md').write_text('Original author text')
        with self.assertRaises(ValueError):
            merge_pages(self.source, self.wiki)
        self.assertEqual((self.wiki / 'Whitepaper.md').read_text(), 'Original author text')

    def test_refuses_ambiguous_home_markers(self):
        (self.wiki / 'Home.md').write_text(START + '\nUnclosed section')
        with self.assertRaises(ValueError):
            merge_pages(self.source, self.wiki)
        self.assertFalse((self.wiki / 'Whitepaper.md').exists())

    def test_refuses_symlink_destination(self):
        outside = self.root / 'outside'
        outside.write_text('Do not replace')
        (self.wiki / 'Home.md').symlink_to(outside)
        with self.assertRaises(ValueError):
            merge_pages(self.source, self.wiki)
        self.assertEqual(outside.read_text(), 'Do not replace')

    def test_refuses_unmarked_source(self):
        (self.source / 'Whitepaper.md').write_text('# Unmarked')
        with self.assertRaises(ValueError):
            merge_pages(self.source, self.wiki)


if __name__ == '__main__':
    unittest.main()
