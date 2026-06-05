# pgntui JSON library

Ready-made signal + container definitions for one dashboard tab per NMEA
Simulator page. Each page folder is a drop-in set:

    library/<page>/
      signals/*.json       one file per signal
      containers/<page>.json   the tab layout

## Usage

Copy the pieces you want into your workspace:

    cp library/gps/signals/*.json      <workspace>/signals/
    cp library/gps/containers/*.json   <workspace>/containers/

Tabs appear in container-filename order — prefix with digits to control
ordering (e.g. `1-gps.json`, `2-engines.json`).

## Pages

| Page                          | PGNs                       | Contents |
|-------------------------------|----------------------------|----------|
| `gps`                         | 129029, 129539, 129284     | satellites, altitude, lat/lon, HDOP/VDOP/TDOP/PDOP, waypoint lat/lon |
| `environmental`               | 130310, 130311, 130312     | water/outside temp, humidity, pressure, cabin + ext temps |
| `boat`                        | 127257, 127252, 130576     | yaw/pitch/roll, heave, trim tabs |
| `batteries`                   | 127508                     | V/A/temp for instances 0–7, grouped Set 1 / Set 2 |
| `engine-{main,stbd,gen1,gen2}`| 127488, 127489             | rpm, boost, tilt/trim, oil, temps, alternator, fuel, hours, load, torque (instances 0/1/2/3) |
| `engine-*-status`             | 127489 Discrete Status 1/2 | 24 status lamps per engine (canboat ENGINE_STATUS_1/2 bit order) |
| `engine-*-transmission`       | 127493                     | gear oil temp/pressure + 5 status lamps per engine |
| `tanks`                       | 127505                     | level % for instances 0–7 |
| `binary`                      | 127501                     | 28 switch lamps, bank instance 1 |
| `binary-bank2`                | 127501                     | 28 switch lamps, bank instance 2 |
| `dc-charge`                   | 127506, 127507             | SOC, SOH, time remaining, ripple, capacity, charger |
| `ac`                          | 127503                     | voltage, current, frequency, breaker size (phase A) |
| `windlass`                    | 128777                     | rode count, line speed |
| `thruster`                    | 128006, 128007, 128008     | speed, power enable, ratings, current, temp, run time |

The four engine instances map to the NMEA Simulator tabs: `main` = Main/port
(instance 0), `stbd` = Stbd (1), `gen1`/`gen2` = Generator 1/2 (2/3). Each has
a readout page plus `-status` and `-transmission` companions.

## Group separators

Container JSON may declare `groups` — full-width rule lines rendered as
`├── Title ──────┤` between signal rows:

    "groups": [{"title": "Oil & temperature", "row": 3}],

A group claims its whole row, so place signals on other rows.

## Not included (not decodable from the bus)

These appear in the simulator but are settings or lookup/enum fields the flat
decoder doesn't surface, so they are intentionally omitted:

- GPS GDOP (not carried in 129029/129539), GNSS system type / method (lookups),
  SNR & elevation masks (transmit-side settings).
- AC phases B and C (127503 repeats per line; the flat decoder reads line A).
- Lookup/enum fields: gear position, charger operating state/mode, thruster
  direction control, windlass motion/rode-type status, fluid/tank type.
- Capacity and "type" fields on tanks (simulator configuration, not telemetry).

## Conventions

- Values decode in canboat SI units (rad, m/s, Pa, K, s); each signal's
  `scale`/`offset` converts to display units (deg, kn, Bar, mBar, h).
  `min`/`max` and warn/alarm thresholds are in display units.
- Temperatures display Kelvin to match the NMEA Simulator panels. For
  Celsius add `"offset": -273.15` and adjust `min`/`max`.
- Engine/transmission pages pin `"instance": 0` (main/port). For the
  starboard engine or generators, copy the files, change `instance`
  (stbd = 1, generators typically 2/3) and give the copies new `id`s.
- Tank and battery instance numbering follows the NMEA Simulator defaults;
  match them to your network's actual instances.
- `binary` pins bank `"instance": 1` (simulator Bank 1).
- Transmission status lamp bit order (Check, Over Temperature, Low Oil
  Pressure, Low Oil Level, Sail Drive) follows the simulator's display
  order — canboat does not name these bits.
- GPS GDOP is not in PGN 129029/129539 and is omitted. SNR/elevation masks
  are simulator transmit settings, not bus data.

Every page is covered by `tests/test_library.py`, which verifies all
signals load, all container refs resolve, and every PGN/field pair is
decodable by the bundled canboat database.
