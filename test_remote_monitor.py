import argparse
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from remote_monitor import AttachedMonitor, main, save_status, state_root


class RemoteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.args = argparse.Namespace(thread='original-thread', state_dir=self.temp.name,
            worker_id=None, poll=.2, max_wakeups=1, sock=None, check=False,
            name=None, message='check training', watch=None, after='1s', every=None)
        self.worker = AttachedMonitor(self.args)
        self.calls = []

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def test_event_has_stoppable_worker_id(self):
        await self.worker.emit({'monitor_id': 'internal', 'output': 'complete'})
        event = await self.worker.events.get()
        self.assertEqual(event['monitor_id'], self.worker.ident)
        self.assertEqual(len(event['monitor_id']), 12)

    async def test_busy_queue_and_no_configuration_override(self):
        states = iter(['active', 'idle', 'active', 'idle'])
        async def call(method, params):
            self.calls.append((method, params))
            if method == 'thread/read':
                return {'thread': {'id': 'original-thread', 'status': {'type': next(states)}, 'cwd': self.temp.name}}
            if method == 'turn/start':
                return {'turn': {'id': 'wakeup-turn'}}
            if method == 'thread/turns/list':
                return {'data': [{'id': 'wakeup-turn', 'status': 'completed'}]}
            self.fail('Unexpected mutating RPC: '+method)
        self.worker.rpc.call = call
        await self.worker.events.put({'output': 'done'})
        await asyncio.wait_for(self.worker.deliver(), 2)
        turns = [(m, p) for m,p in self.calls if m == 'turn/start']
        self.assertEqual(len(turns), 1)
        self.assertEqual(set(turns[0][1]), {'threadId', 'input'})
        self.assertEqual(turns[0][1]['threadId'], 'original-thread')
        self.assertEqual(self.worker.reason, 'limit_reached')

    async def test_not_loaded_is_never_resumed(self):
        async def call(method, params):
            self.calls.append(method)
            return {'thread': {'status': {'type': 'notLoaded'}}}
        self.worker.rpc.call = call
        with self.assertRaises(RuntimeError):
            await self.worker.thread()
        self.assertEqual(self.calls, ['thread/read'])

    async def test_failed_previous_turn_blocks_future_wakeup(self):
        self.worker.last_turn = 'bad'
        async def call(method, params):
            return {'data': [{'id': 'bad', 'status': 'failed'}]}
        self.worker.rpc.call = call
        with self.assertRaises(RuntimeError):
            await self.worker.check_last_turn()

    async def test_interruption_stops_monitor(self):
        self.worker.last_turn = 'interrupted'
        async def call(method, params):
            return {'data': [{'id': 'interrupted', 'status': 'interrupted'}]}
        self.worker.rpc.call = call
        await self.worker.check_last_turn()
        self.assertTrue(self.worker.stop_event.is_set())

    async def test_leave_primary_approvals_untouched(self):
        async def forbidden(*args, **kwargs):
            self.fail('Sidecar must not answer App approvals')
        self.worker.rpc.reply = forbidden
        await self.worker.notification({'id': 99, 'method': 'item/commandExecution/requestApproval'})


class StateTests(unittest.TestCase):
    def test_state_is_private(self):
        with tempfile.TemporaryDirectory() as t:
            root = state_root(Path(t)/'state')
            save_status(root, '012345abcdef', {'state': 'running'})
            self.assertEqual((root/'012345abcdef.json').stat().st_mode & 0o077, 0)

    def test_session_environment_is_used(self):
        captured = []
        async def run(worker):
            captured.append(worker.args.thread)
        with tempfile.TemporaryDirectory() as t, patch.dict('os.environ', {'CODEX_THREAD_ID': 'session-from-exec'}), patch.object(AttachedMonitor, 'run', run):
            result = main(['--check', '--state-dir', t])
        self.assertEqual(result, 0)
        self.assertEqual(captured, ['session-from-exec'])

    def test_missing_session_is_not_guessed(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(SystemExit) as exc:
            main(['--check'])
        self.assertEqual(exc.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
