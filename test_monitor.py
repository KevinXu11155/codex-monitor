import argparse
import asyncio
import contextlib
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest

from codex_monitor import Client, Monitors, clean, duration, output_lines


class CoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        async def emit(event):
            self.events.append(event)
        self.monitors = Monitors(os.getcwd(), emit)

    async def asyncTearDown(self):
        await self.monitors.close()

    def timer(self, repeat=False):
        return self.monitors.start({'name': 'test', 'message': 'check', 'mode': 'timer', 'seconds': 1, 'repeat': repeat})

    async def test_timer_once(self):
        job = self.timer()
        await self.monitors.jobs[job['id']]['_task']
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.monitors.jobs[job['id']]['state'], 'completed')

    async def test_repeat_cancellation(self):
        job = self.timer(True)
        await asyncio.sleep(1.1)
        await self.monitors.stop(job['id'])
        count = len(self.events)
        await asyncio.sleep(1.1)
        self.assertEqual(count, 1)
        self.assertEqual(len(self.events), count)

    async def test_stdout_and_failure(self):
        job = self.monitors.start({'name': 'script', 'message': 'test', 'mode': 'command',
                                  'command': "printf 'first\\nsecond\\n'; printf 'bad\\n' >&2; exit 3"})
        await self.monitors.jobs[job['id']]['_task']
        self.assertEqual([e['output'] for e in self.events[:2]], ['first', 'second'])
        self.assertIn('code 3', self.events[2]['output'])
        self.assertEqual(self.monitors.jobs[job['id']]['state'], 'failed')

    async def test_child_process_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'child.pid'
            job = self.monitors.start({'name': 'child', 'message': 'test', 'mode': 'command',
                                      'command': f'sleep 100 & echo $! > "{pidfile}"; wait'})
            for _ in range(100):
                if pidfile.exists():
                    break
                await asyncio.sleep(.01)
            pid = int(pidfile.read_text())
            await self.monitors.stop(job['id'])
            for _ in range(100):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                await asyncio.sleep(.01)
            else:
                self.fail('child process still alive')

    async def test_bounded_lines(self):
        r = asyncio.StreamReader()
        r.feed_data(b'x' * 200000 + b'\nvalid\nend')
        r.feed_eof()
        lines = [line async for line in output_lines(r)]
        self.assertLess(len(lines[0]), 8300)
        self.assertEqual(lines[1:], ['valid', 'end'])

    async def test_validation_and_terminal_escapes(self):
        for bad in (0, -1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                self.monitors.start({'name': 'x', 'message': 'x', 'mode': 'timer', 'seconds': bad})
        self.assertEqual(duration('5m'), 300)
        self.assertNotIn('\x1b', clean('\x1b[2J'))


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        args = argparse.Namespace(cwd=os.getcwd(), max_wakeups=3)
        self.c = Client(args)
        self.c.thread_id = 'same-thread'
        self.calls = []
        self.called = asyncio.Event()
        async def call(method, params):
            self.calls.append((method, params))
            self.called.set()
            return {'turn': {'id': str(len(self.calls))}}
        self.c.rpc.call = call
        self.worker = asyncio.create_task(self.c.dispatch())

    async def asyncTearDown(self):
        self.worker.cancel()
        await asyncio.gather(self.worker, return_exceptions=True)
        await self.c.monitors.close()

    async def test_same_thread_and_no_concurrent_turns(self):
        await self.c.command('hello')
        await asyncio.wait_for(self.called.wait(), 1)
        self.called.clear()
        job = self.c.monitors.start({'name': 'timer', 'message': 'check', 'mode': 'timer', 'seconds': 100})
        await self.c.emit({'monitor_id': job['id'], 'name': 'timer', 'purpose': 'check', 'output': 'done'})
        await asyncio.sleep(.02)
        self.assertEqual(len(self.calls), 1)
        await self.c.handle({'method': 'turn/completed', 'params': {'threadId': 'same-thread', 'turn': {}}})
        await asyncio.wait_for(self.called.wait(), 1)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(p['threadId'] == 'same-thread' for _, p in self.calls))

    async def test_cancel_discards_pending_event(self):
        self.c.turn_done.clear()
        job = self.c.monitors.start({'name': 't', 'message': 'm', 'mode': 'timer', 'seconds': 100})
        await self.c.emit({'monitor_id': job['id'], 'name': 't', 'output': 'late'})
        await self.c.monitors.stop(job['id'])
        self.c.turn_done.set()
        await asyncio.wait_for(self.c.queue.join(), 1)
        self.assertEqual(self.calls, [])

    async def test_failed_turn_stops_monitors(self):
        job = self.c.monitors.start({'name': 't', 'message': 'm', 'mode': 'timer', 'seconds': 100})
        await self.c.handle({'method': 'turn/completed', 'params': {'threadId': 'same-thread',
                            'turn': {'error': {'message': 'model unavailable'}}}})
        self.assertEqual(self.c.monitors.jobs[job['id']]['state'], 'cancelled')
        self.assertTrue(self.c.turn_done.is_set())

    async def test_other_thread_completion_does_not_release_turn(self):
        self.c.turn_done.clear()
        await self.c.handle({'method': 'turn/completed', 'params': {'threadId': 'other', 'turn': {}}})
        self.assertFalse(self.c.turn_done.is_set())

    async def test_command_tool_requires_approval(self):
        requested = []
        async def decline(prompt):
            requested.append(prompt)
            return False
        self.c.approval = decline
        with self.assertRaises(ValueError):
            await self.c.tool('monitor_start', {'mode': 'command', 'command': 'echo no'})
        self.assertEqual(len(requested), 1)
        self.assertEqual(self.c.monitors.jobs, {})


if __name__ == '__main__':
    unittest.main()
