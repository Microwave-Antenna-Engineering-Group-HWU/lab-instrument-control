"""
pytest session fixtures — instrument connections and chamber conditioning.

Fixtures are session-scoped so the chamber soak and instrument handshakes
happen once per test run, not once per test function.
"""

import sys
import os
import pytest

# Make Python_Drivers importable from anywhere pytest is invoked
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python_Drivers'))

import config
from mk53_driver import MK53
from dmm34465a_driver import DMM34465A
from e36441a_driver import E36441A


@pytest.fixture(scope='session')
def chamber():
    """Open connection to Binder MK53 for the entire test session."""
    with MK53(
        config.MK53_RESOURCE,
        slave_address=config.MK53_SLAVE_ADDR,
        min_temp=config.MK53_MIN_TEMP_C,
        max_temp=config.MK53_MAX_TEMP_C,
    ) as ch:
        yield ch


@pytest.fixture(scope='session')
def dmm():
    """Open connection to Keysight 34465A for the entire test session."""
    with DMM34465A(config.DMM_RESOURCE) as d:
        d.reset()
        d.set_nplc_vdc(config.DMM_NPLC)
        yield d


@pytest.fixture(scope='session')
def psu():
    """
    Open connection to Keysight E36441A, set DUT supply voltage, and enable output.
    Output is disabled automatically when the session ends.
    """
    with E36441A(config.PSU_RESOURCE) as p:
        p.reset()
        p.apply(config.PSU_CHANNEL, config.PSU_VOLTAGE_V, config.PSU_CURRENT_LIM_A)
        p.enable_output(config.PSU_CHANNEL)
        print(
            f'\n[fixture] PSU CH{config.PSU_CHANNEL} enabled: '
            f'{config.PSU_VOLTAGE_V} V / {config.PSU_CURRENT_LIM_A} A limit'
        )
        yield p
        p.disable_output(config.PSU_CHANNEL)
        print(f'\n[fixture] PSU CH{config.PSU_CHANNEL} disabled')


@pytest.fixture(scope='session')
def chamber_at_target(chamber):
    """
    Set chamber to TARGET_TEMP_C and block until the temperature is stable.
    Fails the entire session immediately if the soak times out.
    """
    print(
        f'\n[fixture] Setting chamber to {config.TARGET_TEMP_C}°C '
        f'(timeout {config.TEMP_TIMEOUT_SEC}s) ...'
    )
    chamber.set_temperature(config.TARGET_TEMP_C)
    stable = chamber.wait_for_stability(
        setpoint_c=config.TARGET_TEMP_C,
        tolerance_c=config.TEMP_TOLERANCE_C,
        stable_seconds=config.TEMP_STABLE_SEC,
        timeout_seconds=config.TEMP_TIMEOUT_SEC,
    )
    if not stable:
        pytest.fail(
            f'Chamber did not stabilise at {config.TARGET_TEMP_C}°C '
            f'within {config.TEMP_TIMEOUT_SEC} s — aborting test session.'
        )
    actual = chamber.get_temperature()
    print(f'[fixture] Chamber stable at {actual:.2f}°C')
    return chamber
