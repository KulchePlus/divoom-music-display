"""Update selection, integrity checks, UI and real Windows replacement helper."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import warnings
import tkinter as tk
import updater
from minitoo_app import App

ROOT=Path(__file__).resolve().parent

def release(tag='v99.0.0'):
    prefix=f'https://github.com/{updater.REPOSITORY}/releases/download/{tag}/'
    return {'tag_name':tag,'draft':False,'prerelease':False,'assets':[
        {'name':name,'browser_download_url':prefix+name}
        for name in (f'Divoom-{tag}-windows-x64.zip','SHA256SUMS.txt')]}

def archive(entries):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,data in entries: z.writestr(name,data)
    return stream.getvalue()

class Updates(unittest.TestCase):
    def test_auto_check_preference_and_startup_only(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='update-test-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(ROOT))
            self.assertTrue(updater.load_auto_check(folder))
            updater.save_auto_check(folder,False)
            self.assertFalse(updater.load_auto_check(folder))
            updater.save_auto_check(folder,True)
            self.assertTrue(updater.load_auto_check(folder))
            root=tk.Tk()
            with patch('now_playing.ROOT',Path(folder)):
                app=App(root,start_worker=False)
                try:
                    root.update()
                    for widget in (app.auto_update_switch, app.update_button, app.update_status):
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), root.winfo_rooty()+root.winfo_height())
                    with patch.object(app,'check_updates') as check:
                        app.auto_check.set(False)
                        app.save_auto_check()
                        app.check_updates_at_startup()
                        check.assert_not_called()
                        self.assertFalse(updater.load_auto_check(folder))
                        app.auto_check.set(True)
                        app.save_auto_check()
                        app.check_updates_at_startup()
                        check.assert_not_called()
                        app.startup_check_done=False
                        app.check_updates_at_startup()
                        app.check_updates_at_startup()
                        check.assert_called_once()
                    with patch.object(app,'check_updates') as check:
                        app.auto_check.set(False)
                        app.update_action()
                        check.assert_called_once()
                finally: app.close()

    def test_release_selection(self):
        self.assertIsNone(updater.parse_release(release('v'+updater.VERSION)))
        self.assertIsNone(updater.parse_release(release('v1.2.9')))
        self.assertEqual(updater.parse_release(release())['tag'],'v99.0.0')
        modern=release()
        modern['assets'].append({'name':'Divoom.zip','browser_download_url':
            f'https://github.com/{updater.REPOSITORY}/releases/download/v99.0.0/Divoom.zip'})
        self.assertEqual(updater.parse_release(modern)['name'],'Divoom.zip')
        modern['assets']=[asset for asset in modern['assets'] if asset['name']!='Divoom-v99.0.0-windows-x64.zip']
        self.assertEqual(updater.parse_release(modern)['name'],'Divoom.zip')
        pre=release();pre['prerelease']=True
        self.assertIsNone(updater.parse_release(pre))
        bad=release();bad['assets'][0]['browser_download_url']='https://example.com/evil.zip'
        with self.assertRaises(ValueError): updater.parse_release(bad)
        bad=release();bad['assets']=[]
        with self.assertRaises(ValueError): updater.parse_release(bad)
        with self.assertRaises(ValueError): updater.version('v99.0.0-beta')

    def test_verified_download_and_settings_preservation(self):
        selected=updater.parse_release(release())
        blob=archive([('Divoom.exe',b'MZnew-app'),('../settings.json',b'bad')])
        digest=hashlib.sha256(blob).hexdigest()
        def read(url,limit):
            return (digest+'  '+selected['name']).encode() if url.endswith('.txt') else blob
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='update-test-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(ROOT))
            settings=Path(folder)/'settings.json';settings.write_text('keep')
            with patch('updater.read_url',side_effect=read):
                staging=updater.prepare(selected,folder)
            self.assertEqual((staging/'Divoom.exe').read_bytes(),b'MZnew-app')
            self.assertEqual(settings.read_text(),'keep')
            self.assertEqual(list(staging.iterdir()),[staging/'Divoom.exe'])
            with patch('updater.read_url',side_effect=[('0'*64+'  '+selected['name']).encode(),blob]):
                with self.assertRaisesRegex(ValueError,'SHA-256'): updater.prepare(selected,folder)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                duplicate=archive([('Divoom.exe',b'MZa'),('Divoom.exe',b'MZb')])
            with patch('updater.read_url',side_effect=[(hashlib.sha256(duplicate).hexdigest()+'  '+selected['name']).encode(),duplicate]):
                with self.assertRaises(ValueError): updater.prepare(selected,folder)

    def test_ui_states_and_language(self):
        root=tk.Tk();root.withdraw();app=App(root,start_worker=False)
        try:
            app.events.put(('update_checked',updater.parse_release(release())))
            app.pump()
            self.assertIn('v99.0.0',app.update_button.cget('text'))
            app.update_action()
            self.assertIn('EXE',app.update_status.cget('text'))
            app.set_language('en',save=False)
            self.assertIn('Install',app.update_button.cget('text'))
            app.events.put(('update_checked',None));app.pump()
            self.assertEqual(app.update_status.cget('text'),'You are up to date.')
            app.events.put(('update_error','Проверка недоступна. Попробуйте позже.'));app.pump()
            self.assertEqual(str(app.update_button.cget('state')),'normal')
        finally: app.close()

    def test_helper_replace_and_rollback(self):
        for valid in (True,False):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory(dir=ROOT,prefix='update-test-') as folder:
                self.assertTrue(Path(folder).resolve().is_relative_to(ROOT))
                target=Path(folder)/'Divoom.exe';target.write_bytes(b'old')
                settings=Path(folder)/'settings.json';settings.write_text('keep')
                staging=Path(folder)/'.divoom-update-test';staging.mkdir()
                if valid: (staging/'Divoom.exe').write_bytes(b'new')
                child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(.2)'],creationflags=subprocess.CREATE_NO_WINDOW)
                result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'Update-App.ps1'),'-AppProcessId',str(child.pid),'-Target',str(target),'-Staging',str(staging),'-NoRestart'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                child.wait(timeout=5)
                self.assertEqual(result.returncode,0 if valid else 1,result.stderr)
                self.assertEqual(target.read_bytes(),b'new' if valid else b'old')
                self.assertEqual(settings.read_text(),'keep')
                if valid: self.assertEqual((Path(folder)/'Divoom.previous.exe').read_bytes(),b'old')

if __name__=='__main__': unittest.main()
