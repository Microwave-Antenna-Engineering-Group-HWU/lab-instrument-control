"""
Offline unit tests for the SCPI drivers. A fake instrument answers queries, so
no hardware is needed.

Run from the repository root:
    python -m pytest unit_tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))

from dmm34465a_driver import DMM34465A
from e36441a_driver import E36441A
from hmp4040_driver import HMP4040


class FakeSCPI:
    """Records writes; answers queries from a dict of command -> reply."""

    def __init__(self, replies=None):
        self.replies = dict(replies or {})
        self.log = []

    def write(self, cmd):
        self.log.append(cmd)

    def query(self, cmd):
        self.log.append(cmd)
        return self.replies[cmd]

    def close(self):
        pass


def make(cls, replies=None):
    obj = cls.__new__(cls)
    obj._instr = FakeSCPI(replies)
    return obj


class DMMLimits(unittest.TestCase):
    """34465A Questionable Data register: bit 11 lower fail, bit 12 upper fail."""

    def check(self, register):
        return make(DMM34465A, {'STAT:QUES?': str(register)}).check_limits()

    def test_pass(self):
        self.assertEqual(self.check(0), {'pass': True, 'low': False, 'high': False})

    def test_lower_limit_failed(self):
        self.assertEqual(self.check(1 << 11), {'pass': False, 'low': True, 'high': False})

    def test_upper_limit_failed(self):
        self.assertEqual(self.check(1 << 12), {'pass': False, 'low': False, 'high': True})

    def test_overload_bits_are_not_limit_failures(self):
        # bit 9 (resistance overload) used to be read as a lower-limit failure
        self.assertTrue(self.check((1 << 9) | (1 << 10))['pass'])


class DMMReadMulti(unittest.TestCase):
    def test_restores_trigger_state(self):
        dmm = make(DMM34465A, {'*OPC?': '1', 'FETC?': '+1.0E+00,+2.0E+00'})
        self.assertEqual(dmm.read_multi(2), [1.0, 2.0])
        self.assertEqual(dmm._instr.log[-2:], ['TRIG:SOUR IMM', 'SAMP:COUN 1'])

    def test_restores_trigger_state_after_an_error(self):
        dmm = make(DMM34465A, {})                   # *OPC? is not answered
        with self.assertRaises(KeyError):
            dmm.read_multi(2)
        self.assertEqual(dmm._instr.log[-2:], ['TRIG:SOUR IMM', 'SAMP:COUN 1'])


class E36441ARegulation(unittest.TestCase):
    def psu(self, v_set, i_set, v, i, out='1'):
        return make(E36441A, {
            'OUTP? (@1)': out, 'VOLT? (@1)': str(v_set), 'CURR? (@1)': str(i_set),
            'MEAS:VOLT? CH1': str(v), 'MEAS:CURR? CH1': str(i),
        })

    def test_no_load_is_cv(self):
        self.assertEqual(self.psu(5.0, 0.5, 5.0003, 0.0001).get_regulation_mode(1), 'CV')

    def test_loaded_below_limit_is_cv(self):
        self.assertEqual(self.psu(5.0, 0.5, 4.999, 0.30).get_regulation_mode(1), 'CV')

    def test_at_limit_with_sagging_voltage_is_cc(self):
        self.assertEqual(self.psu(5.0, 0.5, 2.1, 0.4995).get_regulation_mode(1), 'CC')

    def test_output_off(self):
        self.assertEqual(self.psu(5.0, 0.5, 0.0, 0.0, out='0').get_regulation_mode(1), 'OFF')

    def test_preferred_mode_is_no_longer_used(self):
        psu = self.psu(5.0, 0.5, 5.0, 0.0)
        psu.get_regulation_mode(1)
        self.assertFalse(any('PMOD' in c for c in psu._instr.log))

    def test_bad_channel(self):
        with self.assertRaises(ValueError):
            self.psu(5, 1, 5, 0).get_regulation_mode(5)


class SelfTest(unittest.TestCase):
    def test_plus_zero_counts_as_pass(self):
        for cls in (E36441A, HMP4040):
            for reply, ok in (('0', True), ('+0', True), ('1', False), ('+1', False)):
                self.assertEqual(make(cls, {'*TST?': reply}).self_test(), ok, (cls, reply))


class HMP4040Regulation(unittest.TestCase):
    def test_modes(self):
        for cond, mode in (('1', 'CC'), ('2', 'CV'), ('0', 'UNKNOWN')):
            psu = make(HMP4040, {'STAT:QUES:INST:ISUM1:COND?': cond})
            self.assertEqual(psu.get_regulation_mode(1), mode)

    def test_bad_channel_is_rejected_before_any_query(self):
        psu = make(HMP4040, {})
        with self.assertRaises(ValueError):
            psu.get_regulation_mode(9)
        self.assertEqual(psu._instr.log, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
