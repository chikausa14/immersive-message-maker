"""Offline deployment tests; only Python's standard library and Git are needed."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / '.github/scripts/build_pages.py'
SPEC = importlib.util.spec_from_file_location('build_pages', SCRIPT)
pages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pages)


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.put('index.html', b'<h1>stable production</h1>\n')
        self.put('assets/image.png', bytes(range(256)))
        self.put('.well-known/example', b'hidden asset')
        self.put('.github/workflows/evil.yml', b'not public')
        self.put('.gitattributes', b'assets/image.png export-ignore\nindex.html export-subst\n')
        self.production = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def put(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def build(self, pulls, name='site', fetch=lambda sha: None):
        output = self.root / name
        report = pages.assemble(self.repo, self.production, pulls, output, fetch)
        return output, report

    def test_exact_bytes_isolated_previews_and_no_execution(self):
        self.put('index.html', b'<h1>PR one</h1>\n$Format:%H$')
        self.put('assets/a space & quote\'.bin', b'\0\xff\n')
        self.put('build.sh', b'#!/bin/sh\ntouch SHOULD_NOT_RUN\n')
        first = self.commit()
        self.put('index.html', b'<h1>PR two</h1>')
        second = self.commit()
        site, (published, skipped) = self.build([(1, first), (2, second)])
        self.assertEqual(published, [(1, first), (2, second)])
        self.assertEqual(skipped, [])
        self.assertEqual((site / 'index.html').read_bytes(), b'<h1>stable production</h1>\n')
        self.assertEqual((site / 'previews/pr-1/index.html').read_bytes(), b'<h1>PR one</h1>\n$Format:%H$')
        self.assertEqual((site / 'previews/pr-2/index.html').read_bytes(), b'<h1>PR two</h1>')
        for directory in [site, site / 'previews/pr-1', site / 'previews/pr-2']:
            self.assertEqual((directory / 'assets/image.png').read_bytes(), bytes(range(256)))
            self.assertEqual((directory / '.well-known/example').read_bytes(), b'hidden asset')
            self.assertFalse((directory / '.github').exists())
            self.assertFalse((directory / 'SHOULD_NOT_RUN').exists())
        self.assertEqual((site / "previews/pr-1/assets/a space & quote'.bin").read_bytes(), b'\0\xff\n')
        self.assertTrue((site / '.nojekyll').is_file())

    def test_update_and_close_rebuild_without_stale_directories(self):
        self.put('index.html', b'old preview')
        before = self.commit()
        self.put('index.html', b'updated preview')
        after = self.commit()
        first, _ = self.build([(1, before), (2, before)], 'first')
        second, _ = self.build([(1, after)], 'second')
        self.assertTrue((first / 'previews/pr-2').exists())
        self.assertFalse((second / 'previews/pr-2').exists())
        self.assertEqual((second / 'previews/pr-1/index.html').read_bytes(), b'updated preview')
        third, _ = self.build([], 'third')
        self.assertFalse((third / 'previews').exists())
        self.assertEqual((first / 'index.html').read_bytes(), (third / 'index.html').read_bytes())

    def test_symlink_pr_is_skipped_without_following_it(self):
        (self.repo / 'assets/escape').symlink_to('/etc/passwd')
        bad = self.commit()
        site, (published, skipped) = self.build([(1, bad), (2, self.production)])
        self.assertEqual(published, [(2, self.production)])
        self.assertEqual(skipped, [(1, 'Symlinks and submodules are not supported')])
        self.assertFalse((site / 'previews/pr-1').exists())
        self.assertTrue((site / 'index.html').exists())

    def test_submodule_pr_is_skipped(self):
        self.git('update-index', '--add', '--cacheinfo', f'160000,{self.production},module')
        self.git('commit', '-qm', 'gitlink')
        site, (_, skipped) = self.build([(1, self.git('rev-parse', 'HEAD'))])
        self.assertEqual(len(skipped), 1)
        self.assertFalse((site / 'previews/pr-1').exists())

    def test_missing_pr_index_is_skipped(self):
        (self.repo / 'index.html').unlink()
        bad = self.commit()
        site, (_, skipped) = self.build([(1, bad)])
        self.assertEqual(skipped, [(1, 'Missing root index.html')])
        self.assertTrue((site / 'index.html').exists())

    def test_invalid_production_fails_before_output(self):
        self.put('previews/pr-1/index.html', b'would conflict')
        self.production = self.commit()
        with self.assertRaisesRegex(pages.UnsafeTree, 'reserved'):
            self.build([])
        self.assertFalse((self.root / 'site').exists())

    def test_fetch_failure_never_publishes_partial_site(self):
        def fail(sha):
            raise RuntimeError('network unavailable')
        with self.assertRaisesRegex(RuntimeError, 'network unavailable'):
            self.build([(1, self.production)], fetch=fail)
        self.assertFalse((self.root / 'site').exists())

    def test_existing_output_is_not_deleted(self):
        site, _ = self.build([])
        with self.assertRaisesRegex(ValueError, 'new directory'):
            self.build([])
        self.assertEqual((site / 'index.html').read_bytes(), b'<h1>stable production</h1>\n')

    def test_only_open_same_repo_main_prs_are_eligible(self):
        def pr(number, repo='owner/site', state='open', base='main'):
            return {'number': number, 'state': state, 'base': {'ref': base},
                    'head': {'sha': self.production, 'repo': {'full_name': repo}}}
        pulls = [pr(1), pr(2, 'attacker/fork'), pr(3, state='closed'), pr(4, base='other')]
        deleted_fork = pr(5)
        deleted_fork['head']['repo'] = None
        pulls.append(deleted_fork)
        self.assertEqual(pages.eligible_pulls(pulls, 'owner/site'), [(1, self.production)])
        with self.assertRaisesRegex(ValueError, 'Invalid PR'):
            pages.eligible_pulls([pr('../escape')], 'owner/site')

    def test_api_pagination(self):
        batches = [list(range(100)), [100]]
        with patch.object(pages.urllib.request, 'urlopen', side_effect=[
            io.BytesIO(json.dumps(batch).encode()) for batch in batches
        ]) as request:
            self.assertEqual(pages.open_pulls('owner/site', 'temporary-token'), list(range(101)))
            self.assertIn('page=2', request.call_args_list[1].args[0].full_url)


if __name__ == '__main__':
    unittest.main()
