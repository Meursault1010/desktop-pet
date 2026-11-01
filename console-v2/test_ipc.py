"""使用真实 Python 子进程验证桌面通信，不读写个人配置。"""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xiaoju-ipc-')
        self.settings = str(Path(self.temp.name) / 'settings.ini')
        self.start_backend()

    def start_backend(self):
        self.messages = queue.Queue()
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONIOENCODING='utf-8')
        self.process = subprocess.Popen([sys.executable, '-u', '-B', 'pet_backend.py',
                                         '--settings-file', self.settings],
                                        cwd=Path(__file__).parent, env=environment,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8')
        def read():
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        self.wait_for(lambda message: message['type'] == 'ready')
        # Protocol readiness precedes the visible arrival animation. Commands
        # below assert the steady status, so wait for the arrival to finish.
        self.wait_for(lambda message: message.get('name') == 'state_changed'
                      and message['state']['visible']
                      and not message['state']['status'].startswith(('星光 ·', '探头 ·', '回望 ·')))

    def wait_for(self, predicate):
        for _ in range(100):
            message = self.messages.get(timeout=8)
            if predicate(message):
                return message
        self.fail('No matching response')

    def request(self, name, payload=None):
        self.process.stdin.write(json.dumps({'id': 'test', 'name': name, 'payload': payload or {}}) + '\n')
        self.process.stdin.flush()
        return self.wait_for(lambda message: message.get('type') == 'response' and message.get('id') == 'test')

    def stop_backend(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=8)
        if not self.process.stdin.closed:
            self.process.stdin.close()
        self.reader.join(timeout=2)
        self.process.stdout.close()
        error = self.process.stderr.read()
        self.process.stderr.close()
        return error

    def tearDown(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if not stream.closed:
                stream.close()
        self.temp.cleanup()

    def test_commands_validation_and_state(self):
        state = self.request('get_state')
        self.assertTrue(state['ok'])
        self.assertTrue(state['preview'].startswith('data:image/png;base64,'))
        self.assertTrue(state['state']['visible'])
        activity = state['state']['activity']
        self.assertEqual(activity['label'], state['state']['status'])
        self.assertIsInstance(activity['key'], str)
        self.assertIn(activity['posture'], (None, 'stand', 'sit', 'prone', 'sleep'))
        updated = self.request('set_preference', {'key': 'speed', 'value': 87})
        self.assertEqual(updated['state']['preferences']['speed'], 87)
        self.assertFalse(self.request('set_preference', {'key': 'speed', 'value': 999})['ok'])
        self.assertFalse(self.request('not_a_command')['ok'])
        edge=self.request('configure_edge_attachment',{'enabled':True,'delay':2})
        self.assertTrue(edge['ok']);self.assertTrue(edge['state']['edge_attachment']['options']['enabled'])
        self.assertFalse(self.request('configure_edge_attachment',{'delay':True})['ok'])
        self.assertTrue(self.request('stop_edge_attachment')['ok'])
        self.assertTrue(self.request('configure_edge_attachment',{'enabled':False})['ok'])
        quiet = self.request('set_preference', {'key': 'quiet', 'value': True})
        self.assertIn(quiet['state']['status'], ('安静模式', '熟睡中 · z z z'))
        hidden = self.request('set_visible', {'visible': False})
        self.assertFalse(hidden['state']['visible'])
        self.wait_for(lambda message: message.get('name') == 'state_changed'
                      and message['state']['status'] == '已隐藏')
        self.assertEqual(self.request('get_state')['state']['activity']['key'], 'hidden')
        self.assertFalse(self.request('jump')['ok'])
        self.request('set_visible', {'visible': True})
        self.assertTrue(self.request('jump')['ok'])
        reset = self.request('reset_defaults')
        self.assertEqual(reset['state']['preferences']['speed'], 48)
        self.assertFalse(reset['state']['preferences']['quiet'])

    def test_shutdown_and_restart_persistence(self):
        self.request('set_preference', {'key': 'size', 'value': 125})
        self.request('set_preference', {'key': 'quiet', 'value': True})
        self.assertTrue(self.request('shutdown')['ok'])
        self.process.wait(timeout=12)
        self.assertEqual(self.process.returncode, 0)
        self.stop_backend()
        self.start_backend()
        state = self.request('get_state')['state']
        self.assertEqual(state['preferences']['size'], 125)
        self.assertTrue(state['preferences']['quiet'])

    def test_parent_pipe_close_exits_pet(self):
        error = self.stop_backend()
        self.assertEqual(self.process.returncode, 0, error)

    def test_tool_status_performances_and_companion_commands(self):
        thinking = self.request('desktop_event', {'kind': 'thinking', 'text': '工具状态'})
        self.assertTrue(thinking['ok'])
        self.assertIn('工具状态', thinking['state']['status'])
        time.sleep(.9)
        done = self.request('desktop_event', {'kind': 'done', 'text': '工具状态'})
        self.assertTrue(done['ok'])
        self.assertIn('完成了', done['state']['status'])
        self.assertFalse(self.request('desktop_event', {'kind': 'thinking'})['ok'])
        self.assertFalse(self.request('desktop_event', {'kind': 'thinking', 'text': 'x', 'extra': 1})['ok'])
        self.assertFalse(self.request('desktop_event', {'kind': 'unknown', 'text': 'x'})['ok'])
        self.assertTrue(self.request('reset_companion_memory', {})['ok'])
        self.assertTrue(self.request('stop_window_perch', {})['ok'])
        self.assertIn('ok', self.request('perch_window', {}))
        for name in ('reset_companion_memory', 'perch_window', 'stop_window_perch'):
            self.assertFalse(self.request(name, {'extra': 1})['ok'])

    def test_focus_protocol_phases_and_validation(self):
        focus = self.request('set_focus', {'enabled': True, 'phase': 'focus', 'remaining': 60})
        self.assertTrue(focus['ok'])
        self.assertTrue(focus['state']['focus']['active'])
        self.assertEqual(focus['state']['focus']['phase'], 'focus')
        self.assertIn('专注', focus['state']['status'])
        broken = self.request('set_focus', {'enabled': True, 'phase': 'break', 'remaining': 300})
        self.assertTrue(broken['ok'])
        self.assertEqual(broken['state']['focus']['phase'], 'break')
        self.assertFalse(self.request('set_focus', {'enabled': True, 'phase': 'idle'})['ok'])
        self.assertFalse(self.request('set_focus', {'enabled': True, 'remaining': 86401})['ok'])
        self.assertFalse(self.request('set_focus', {'enabled': 'true'})['ok'])
        ended = self.request('set_focus', {'enabled': False})
        self.assertTrue(ended['ok'])
        self.assertFalse(ended['state']['focus']['active'])

    def test_action_commands(self):
        self.request('wake_sleep')
        time.sleep(.2)
        standing = self.request('get_state')['preview']
        self.assertFalse(self.request('play_action', {'action_id':'../../bad'})['ok'])
        played=self.request('play_action', {'action_id':'sleep','loop':True,'speed':1})
        self.assertTrue(played['ok'])
        self.assertIn('睡觉',played['state']['status'])
        self.assertNotEqual(self.request('get_state')['preview'], standing)
        self.assertFalse(self.request('play_action', {'action_id':'sleep','speed':99})['ok'])
        self.assertTrue(self.request('stop_action')['ok'])
        self.assertNotIn('动作',self.request('get_state')['state']['status'])
        self.request('set_visible',{'visible':False})
        self.wait_for(lambda message: message.get('name') == 'state_changed'
                      and message['state']['status'] == '已隐藏')
        self.assertFalse(self.request('play_action',{'action_id':'sleep'})['ok'])

    def test_icon_sleep_configuration_and_validation(self):
        initial=self.request('get_state')['state']['icon_sleep']
        self.assertEqual(initial['phase'],'idle')
        configured=self.request('configure_icon_sleep',{'direction':'right','breath':66,'duration':5})
        self.assertTrue(configured['ok'])
        self.assertEqual(configured['state']['icon_sleep']['options']['breath'],66)
        self.assertFalse(self.request('configure_icon_sleep',{'offset_x':999})['ok'])
        self.assertFalse(self.request('configure_icon_sleep',{'auto_snap':'yes'})['ok'])
        self.assertFalse(self.request('start_icon_sleep',{'icon_id':'unknown'})['ok'])
        self.assertTrue(self.request('stop_icon_sleep')['ok'])

    @unittest.skipUnless(os.name=='nt','Windows desktop integration')
    def test_real_desktop_scan_and_sleep_round_trip(self):
        self.assertTrue(self.request('refresh_desktop_icons')['ok'])
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            sleep=self.request('get_state')['state']['icon_sleep']
            if not sleep['scanning']: break
            time.sleep(.05)
        self.assertFalse(sleep['scanning'])
        # Locked/hidden Explorer is a supported, explicitly reported condition.
        if sleep['error']:
            self.assertIsInstance(sleep['error'],str)
            return
        self.assertIsInstance(sleep['icons'],list)
        available=next((i for i in sleep['icons'] if i.get('available')),None)
        if available:
            result=self.request('start_icon_sleep',{'icon_id':available['id']})
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['state']['icon_sleep']['phase'],'approaching')
            self.assertTrue(self.request('stop_icon_sleep')['ok'])
            self.assertEqual(self.request('get_state')['state']['icon_sleep']['phase'],'idle')


if __name__ == '__main__':
    unittest.main(verbosity=2)
