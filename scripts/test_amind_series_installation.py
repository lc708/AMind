"""All-package installation preserves originals and rejects invalid knowledge."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('series_installer',ROOT/'scripts/install_amind_series.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class AllPackageInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.destination=self.root/'skills'
        for name in ['amind','amind-engineering','eval-improve']:
            p=self.source/name;p.mkdir(parents=True)
            (p/'SKILL.md').write_text('new '+name)
        verifier=self.source/'amind/scripts/verify.py';verifier.parent.mkdir();verifier.write_text('raise SystemExit(0)\n')
        self.source_patch=patch.object(installer,'SOURCE',self.source);self.source_patch.start();self.addCleanup(self.source_patch.stop)

    def test_all_three_are_staged_verified_and_idempotent(self):
        plan=installer.install(self.destination,with_knowledge=True)
        self.assertEqual([x['name'] for x in plan['skills']],['amind','amind-engineering','eval-improve'])
        self.assertFalse(self.destination.exists())
        result=installer.install(self.destination,apply=True,with_knowledge=True)
        self.assertTrue(result['verified'])
        for name in ['amind','amind-engineering','eval-improve']:
            self.assertEqual(installer.inventory(self.destination/name),installer.inventory(self.source/name))
        again=installer.install(self.destination,apply=True,with_knowledge=True)
        self.assertTrue(all(x['action']=='unchanged' for x in again['skills']))

    def test_invalid_knowledge_blocks_every_write(self):
        (self.source/'amind/scripts/verify.py').write_text('raise SystemExit(2)\n')
        with self.assertRaisesRegex(ValueError,'knowledge package validation failed'):
            installer.install(self.destination,apply=True,replace=True,with_knowledge=True)
        self.assertFalse(self.destination.exists());self.assertFalse((self.root/'skill-backups').exists())

    def test_replace_preserves_all_previous_packages(self):
        for name in ['amind','amind-engineering','eval-improve']:
            p=self.destination/name;p.mkdir(parents=True);(p/'SKILL.md').write_text('old '+name)
        result=installer.install(self.destination,apply=True,replace=True,with_knowledge=True)
        backup=Path(result['backup'])
        for name in ['amind','amind-engineering','eval-improve']:
            self.assertEqual((backup/name/'SKILL.md').read_text(),'old '+name)

    def test_late_publish_failure_rolls_back_every_previous_package(self):
        for name in ['amind','amind-engineering','eval-improve']:
            p=self.destination/name;p.mkdir(parents=True);(p/'SKILL.md').write_text('old '+name)
        rename=Path.rename
        def fail_once(path,target):
            if path.name=='eval-improve' and path.parent.name=='.amind-stage-trigger':raise OSError('late publication failure')
            # Stage directory is randomized; identify its parent by prefix.
            if path.name=='eval-improve' and path.parent.name.startswith('.amind-stage-'):
                raise OSError('late publication failure')
            return rename(path,target)
        with patch.object(Path,'rename',fail_once),self.assertRaisesRegex(OSError,'late publication'):
            installer.install(self.destination,apply=True,replace=True,with_knowledge=True)
        for name in ['amind','amind-engineering','eval-improve']:
            self.assertEqual((self.destination/name/'SKILL.md').read_text(),'old '+name)


if __name__=='__main__':unittest.main()
