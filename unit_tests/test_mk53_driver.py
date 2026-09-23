"""
Offline unit tests for Python_Drivers/mk53_driver.py. No chamber needed.

A fake serial resource replays scripted chamber replies, so framing, retries,
error handling and the safety checks can be verified on any PC.

Run from the repository root:
    python -m pytest unit_tests

If pyvisa is not installed a minimal stand-in is used so the tests still run.
"""

import math
import struct
import sys
import types
import unittest
from unittest import mock

try:
    import pyvisa
except ImportError:                              # minimal stand-in
    class _VisaIOError(Exception):
        pass

    pyvisa = types.ModuleType('pyvisa')
    pyvisa.errors = types.SimpleNamespace(VisaIOError=_VisaIOError)
    pyvisa.constants = types.SimpleNamespace(
        StopBits=types.SimpleNamespace(one=1),
        Parity=types.SimpleNamespace(none=0),
        ControlFlow=types.SimpleNamespace(none=0),
        BufferOperation=types.SimpleNamespace(discard_read_buffer=4),
        StatusCode=types.SimpleNamespace(error_timeout=-1073807339),
    )
    pyvisa.ResourceManager = lambda *_a, **_k: None
    sys.modules['pyvisa'] = pyvisa

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))

import mk53_driver
from mk53_driver import MK53, MK53CommError, MK53Error, MK53ModbusError

SLAVE = 1


def crc(data: bytes) -> bytes:
    return struct.pack('<H', MK53._crc16(data))


def read_reply(words, slave=SLAVE, func=0x03):
    body = struct.pack('>BBB', slave, func, len(words) * 2)
    body += b''.join(struct.pack('>H', w) for w in words)
    return body + crc(body)


def float_reply(value, **kw):
    return read_reply(MK53._encode_float(value), **kw)


def write_echo(addr, n_words=2, slave=SLAVE):
    body = struct.pack('>BBHH', slave, 0x10, addr, n_words)
    return body + crc(body)


def exception_reply(code, func=0x03, slave=SLAVE):
    body = struct.pack('>BBB', slave, func | 0x80, code)
    return body + crc(body)


class FakeInstr:
    """Serial stand-in: each write_raw() consumes the next scripted reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.rx = bytearray()
        self.sent = []
        self.flushes = 0
        self.closed = False

    def write_raw(self, data):
        self.sent.append(bytes(data))
        if self.replies:
            self.rx += self.replies.pop(0)

    def read_bytes(self, n):
        if len(self.rx) < n:                     # mimic a VISA read timeout
            self.rx.clear()
            raise pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout)
        out, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return out

    def flush(self, _mask):
        self.flushes += 1
        self.rx.clear()

    def close(self):
        self.closed = True


def make(replies=(), retries=3, min_temp=-40.0, max_temp=180.0):
    """Build an MK53 wired to a FakeInstr without opening any port."""
    m = MK53.__new__(MK53)
    m.slave_address, m.retries = SLAVE, retries
    m.min_temp, m.max_temp = min_temp, max_temp
    m._instr = FakeInstr(replies)
    return m


class Basics(unittest.TestCase):
    def test_crc_known_vector(self):
        self.assertEqual(MK53._crc16(bytes([1, 3, 0, 0, 0, 10])), 0xCDC5)

    def test_float_round_trip(self):
        for v in (85.0, -40.0, 180.0, 23.456):
            self.assertAlmostEqual(MK53._decode_float(list(MK53._encode_float(v))), v, 3)

    def test_read_temperature(self):
        m = make([float_reply(23.5)])
        self.assertAlmostEqual(m.get_temperature(), 23.5, 3)

    def test_get_mode(self):
        m = make([read_reply([0x0800])])
        self.assertEqual(m.get_mode(), ['manual'])


class ErrorHandling(unittest.TestCase):
    def test_exception_frame_is_parsed_not_timed_out(self):
        # 5-byte exception reply; the old code waited for 9 bytes and timed out
        m = make([exception_reply(2)])
        with self.assertRaises(MK53ModbusError) as cm:
            m.get_temperature()
        self.assertIn('Invalid parameter address', str(cm.exception))
        self.assertEqual(len(m._instr.sent), 1)          # not retried

    def test_exception_frame_on_write(self):
        m = make([exception_reply(5, func=0x10)])
        with self.assertRaises(MK53ModbusError):
            m.set_temperature(50.0)

    def test_crc_glitch_is_retried(self):
        bad = bytearray(float_reply(21.0))
        bad[-1] ^= 0xFF
        m = make([bytes(bad), float_reply(21.0)])
        self.assertAlmostEqual(m.get_temperature(), 21.0, 3)
        self.assertEqual(len(m._instr.sent), 2)

    def test_persistent_crc_error_gives_up(self):
        bad = bytearray(float_reply(21.0))
        bad[-1] ^= 0xFF
        m = make([bytes(bad)] * 3, retries=3)
        with self.assertRaises(MK53CommError):
            m.get_temperature()
        self.assertEqual(len(m._instr.sent), 3)

    def test_setpoint_and_mode_reads_also_retry(self):
        m = make([b'', float_reply(50.0)])               # first attempt: silence
        self.assertAlmostEqual(m.get_temperature_setpoint(), 50.0, 3)

    def test_no_reply_is_comm_error(self):
        m = make([b''] * 3)
        with self.assertRaises(MK53CommError):
            m.get_temperature()

    def test_wrong_slave_rejected(self):
        m = make([float_reply(20.0, slave=7)] * 3)
        with self.assertRaises(MK53CommError):
            m.get_temperature()

    def test_stale_bytes_are_flushed_before_each_request(self):
        m = make([float_reply(30.0)])
        m._instr.rx += b'\xde\xad\xbe\xef'
        self.assertAlmostEqual(m.get_temperature(), 30.0, 3)
        self.assertGreaterEqual(m._instr.flushes, 1)

    def test_bad_byte_count_rejected(self):
        m = make([read_reply([1, 2, 3])] * 3)            # 6 bytes, expected 4
        with self.assertRaises(MK53CommError):
            m.get_temperature()


class Writes(unittest.TestCase):
    def test_set_temperature_writes_both_registers(self):
        m = make([write_echo(MK53.ADDR_MANSETPT), write_echo(MK53.ADDR_BASICSETPT)])
        m.set_temperature(85.0)
        self.assertEqual(len(m._instr.sent), 2)

    def test_write_echo_mismatch_is_error(self):
        m = make([write_echo(0x1234)] * 3)
        with self.assertRaises(MK53CommError):
            m.set_temperature(85.0)


class SafetyLimits(unittest.TestCase):
    def test_nan_and_inf_never_reach_the_chamber(self):
        for bad in (float('nan'), float('inf'), float('-inf')):
            m = make()
            with self.assertRaises(ValueError):
                m.set_temperature(bad)
            self.assertEqual(m._instr.sent, [])

    def test_out_of_range_rejected(self):
        m = make()
        for bad in (-40.1, 180.1):
            with self.assertRaises(ValueError):
                m.set_temperature(bad)
        self.assertEqual(m._instr.sent, [])

    def test_constructor_rejects_bounds_beyond_hardware_range(self):
        for lo, hi in ((-40, 200), (-60, 100), (100, 100), (float('nan'), 100)):
            with self.assertRaises(ValueError):
                MK53('ASRL1::INSTR', min_temp=lo, max_temp=hi)

    def test_port_closed_if_configuration_fails(self):
        class Boom:
            closed = False

            def __setattr__(self, k, v):
                if k == 'baud_rate':
                    raise RuntimeError('unsupported')
                object.__setattr__(self, k, v)

            def close(self):
                Boom.closed = True

        rm = mock.Mock()
        rm.open_resource.return_value = Boom()
        with mock.patch.object(pyvisa, 'ResourceManager', return_value=rm):
            with self.assertRaises(RuntimeError):
                MK53('ASRL1::INSTR')
        self.assertTrue(Boom.closed)


class Ramp(unittest.TestCase):
    def _ramp_setup(self, start_sp, **kw):
        m = make(**kw)
        m.get_temperature_setpoint = lambda: start_sp
        sent = []
        m.set_temperature = sent.append
        return m, sent

    def test_zero_or_negative_rate_rejected_instead_of_looping(self):
        for rate in (0.0, -5.0, float('nan')):
            m, sent = self._ramp_setup(20.0)
            with self.assertRaises(ValueError):
                m.ramp_to(50.0, rate_c_per_min=rate)
            self.assertEqual(sent, [])

    def test_bad_step_interval_rejected(self):
        m, sent = self._ramp_setup(20.0)
        with self.assertRaises(ValueError):
            m.ramp_to(50.0, step_interval_s=0)

    def test_target_above_max_rejected_before_any_write(self):
        m, sent = self._ramp_setup(170.0)
        with self.assertRaises(ValueError):
            m.ramp_to(200.0)
        self.assertEqual(sent, [])

    def test_nan_target_rejected(self):
        m, sent = self._ramp_setup(20.0)
        with self.assertRaises(ValueError):
            m.ramp_to(float('nan'))

    def test_invalid_setpoint_readback_refused(self):
        m, sent = self._ramp_setup(float('nan'))
        with self.assertRaises(MK53Error):
            m.ramp_to(50.0)
        self.assertEqual(sent, [])

    def test_ramp_steps_and_no_sleep_after_final_step(self):
        m, sent = self._ramp_setup(20.0)
        with mock.patch.object(mk53_driver.time, 'sleep') as sleep:
            m.ramp_to(30.0, rate_c_per_min=10.0, step_interval_s=30.0)  # 5 °C/step
        self.assertEqual(sent, [25.0, 30.0])
        self.assertEqual(sleep.call_count, 1)

    def test_already_at_target_does_nothing(self):
        m, sent = self._ramp_setup(50.0)
        m.ramp_to(50.0)
        self.assertEqual(sent, [])


class Stability(unittest.TestCase):
    def _clock(self):
        now = [0.0]
        return now, (lambda: now[0]), (lambda s: now.__setitem__(0, now[0] + s))

    def test_stable_returns_true(self):
        m = make()
        m.get_temperature = lambda: 85.1
        now, mono, sleep = self._clock()
        with mock.patch.object(mk53_driver.time, 'monotonic', mono), \
             mock.patch.object(mk53_driver.time, 'sleep', sleep):
            self.assertTrue(m.wait_for_stability(85.0, stable_seconds=30,
                                                 poll_interval_s=5))

    def test_timeout_returns_false_without_overshooting(self):
        m = make()
        m.get_temperature = lambda: 20.0
        now, mono, sleep = self._clock()
        with mock.patch.object(mk53_driver.time, 'monotonic', mono), \
             mock.patch.object(mk53_driver.time, 'sleep', sleep):
            self.assertFalse(m.wait_for_stability(85.0, timeout_seconds=12,
                                                  poll_interval_s=5))
            self.assertLessEqual(now[0], 12.0)

    def test_invalid_arguments(self):
        m = make()
        with self.assertRaises(ValueError):
            m.wait_for_stability(float('nan'))
        with self.assertRaises(ValueError):
            m.wait_for_stability(85.0, poll_interval_s=0)


class PortAndReadback(unittest.TestCase):
    """Helpers added after the first real use of the chamber."""

    def test_resolve_port_names(self):
        self.assertEqual(mk53_driver.resolve_port('COM5'), 'ASRL5::INSTR')
        self.assertEqual(mk53_driver.resolve_port('com12'), 'ASRL12::INSTR')
        self.assertEqual(mk53_driver.resolve_port('ASRL3::INSTR'), 'ASRL3::INSTR')

    def _ports(self, *vid_pid_dev):
        return [types.SimpleNamespace(vid=v, pid=p, device=d) for v, p, d in vid_pid_dev]

    def test_auto_finds_the_ftdi_adapter(self):
        ports = self._ports((0x067B, 0x23A3, 'COM5'), (0x0403, 0x6001, 'COM12'))
        with mock.patch('serial.tools.list_ports.comports', return_value=ports):
            self.assertEqual(mk53_driver.resolve_port('auto'), 'ASRL12::INSTR')
            self.assertEqual(mk53_driver.resolve_port(None), 'ASRL12::INSTR')

    def test_auto_without_adapter_or_with_two_fails(self):
        with mock.patch('serial.tools.list_ports.comports',
                        return_value=self._ports((0x067B, 0x23A3, 'COM5'))):
            with self.assertRaises(MK53Error):
                mk53_driver.resolve_port('auto')
        two = self._ports((0x0403, 0x6001, 'COM12'), (0x0403, 0x6001, 'COM14'))
        with mock.patch('serial.tools.list_ports.comports', return_value=two):
            with self.assertRaises(MK53Error):
                mk53_driver.resolve_port('auto')

    def test_confirm_setpoint_waits_for_a_slow_controller(self):
        # first read after the write still shows the old value (seen on the real chamber)
        values = iter([22.0, 23.0])
        c = types.SimpleNamespace(get_temperature_setpoint=lambda: next(values))
        with mock.patch.object(mk53_driver.time, 'sleep'):
            self.assertEqual(mk53_driver.confirm_setpoint(c, 23.0), 23.0)

    def test_confirm_setpoint_gives_up_and_returns_last_value(self):
        c = types.SimpleNamespace(get_temperature_setpoint=lambda: 22.0)
        with mock.patch.object(mk53_driver.time, 'sleep'):
            self.assertEqual(mk53_driver.confirm_setpoint(c, 23.0, tries=3), 22.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
