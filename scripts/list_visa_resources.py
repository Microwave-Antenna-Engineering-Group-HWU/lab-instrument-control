"""
List all VISA resources visible to pyvisa and query *IDN? on each one.

Run:
    python scripts/list_visa_resources.py

Copy the address printed for your instrument and paste it into VISA_ADDR
at the top of the relevant test script.
"""

import pyvisa

rm = pyvisa.ResourceManager('@py')
resources = rm.list_resources()

if not resources:
    print('No VISA resources found.')
    print('  → Check USB/GPIB/LAN cables and that the instrument is powered on.')
    raise SystemExit(1)

print(f'Found {len(resources)} VISA resource(s):\n')

for addr in resources:
    idn = '<could not query>'
    try:
        with rm.open_resource(addr) as inst:
            inst.timeout = 2000
            idn = inst.query('*IDN?').strip()
    except Exception as exc:
        idn = f'<error: {exc}>'

    print(f'  {addr}')
    print(f'    IDN : {idn}')
    print()
