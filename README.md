# Mass Properties Tracker

![CI](https://github.com/amatyaPratik/Mass-Property-Tracker/actions/workflows/ci.yml/badge.svg)

A small Python + SQLite tool to manage aircraft **mass properties**: mass, centre of gravity (CG) and moments of inertia. It covers a component → system → aircraft hierarchy, with validated data import and a full change history.

Built as a learning prototype to explore how engineering data can be kept consistent and traceable while a design keeps changing.

## Features

- **Hierarchical data model:** components stored in SQLite, grouped into systems and assemblies of any depth
- **Validated CSV import:** a file is rejected as a whole (nothing is written) if any row has a negative mass, a missing or non-numeric value, physically impossible inertia (violating the triangle inequality), an unknown parent, a duplicate ID or a cycle. Errors are reported with their CSV row number
- **Rollups at any level:** total mass, combined CG and the full inertia tensor about the combined CG, using the parallel axis (Steiner) theorem
- **Traceability:** every change is logged per field with old value, new value, timestamp and source (for example, which import file caused it)
- **Command-line interface:** `import`, `tree`, `rollup`, `history`
- **Quality:** pytest suite and a GitHub Actions workflow that also runs the CLI end to end

## Quick start

```bash
pip install -e ".[dev]"

mpt --db demo.db import examples/sample_aircraft.csv
mpt --db demo.db tree
mpt --db demo.db rollup AC
```

```
- AC  Generic trainer aircraft  (1485.00 kg)
  - PROP  Propulsion  (550.00 kg)
    - PROP-ENG  Engine  (310.00 kg)
    - PROP-FUEL  Fuel (full)  (240.00 kg)
  - STR  Structure  (795.00 kg)
  ...

Generic trainer aircraft (AC): 12 component(s)
  Mass [kg]         1485.0000
  CG [m]       x       3.7785   y       0.0000   z       0.1148
  Inertia about CG [kg m^2]
       4891.9741       0.0000    -275.1741
          0.0000    5038.6845       0.0000
       -275.1741       0.0000    9661.2104
```

### Tracking a design change

```bash
mpt --db demo.db import examples/design_update.csv
mpt --db demo.db history PROP-ENG
```

```
created            None -> Engine       (import:examples/sample_aircraft.csv)
mass              310.0 -> 325.0        (import:examples/design_update.csv)
cg_x                1.1 -> 1.05         (import:examples/design_update.csv)
...
```

### Rejecting bad data

```bash
mpt --db demo.db import examples/invalid.csv
```

```
Import rejected: 4 problem(s) found, nothing was written.
  - row 1 [BAD-1]: mass must not be negative (got -5.0)
  - row 2 [BAD-2]: missing value for 'cg_y'
  - row 3 [BAD-3]: izz exceeds the sum of the other two moments (not physically possible)
  - row 4 [BAD-4]: unknown parent_id 'NOPE'
```

## CSV format

| Column | Required | Unit | Notes |
|---|---|---|---|
| `id`, `name` | yes | | unique ID per component |
| `parent_id` | no | | empty for top-level items |
| `mass` | yes | kg | must be ≥ 0; assemblies can be 0 |
| `cg_x`, `cg_y`, `cg_z` | yes | m | CG position in aircraft axes |
| `ixx`, `iyy`, `izz`, `ixy`, `ixz`, `iyz` | no | kg·m² | inertia tensor about the component's own CG; empty = point mass |

Off-diagonal values follow the **tensor convention** (`ixy = −∫xy dm`). If your source uses positive products of inertia, negate them before import.

## How the rollup works

For components with mass *mᵢ*, CG *rᵢ* and inertia tensor *Iᵢ* about their own CG:

- **Total mass:** M = Σ mᵢ
- **Combined CG:** r_cg = Σ mᵢ rᵢ / M
- **Inertia about the combined CG:** I = Σ ( Iᵢ + mᵢ (|dᵢ|² E − dᵢ dᵢᵀ) ), with dᵢ = rᵢ − r_cg

The rollup is verified in the tests against hand-calculated cases (point masses, parallel axis shifts with products of inertia), and against an independent NumPy calculation of the sample aircraft.

## Project structure

```
mass_properties/
  models.py     Component and result data classes
  rollup.py     CG / inertia combination (parallel axis theorem)
  store.py      SQLite persistence with field-level change log
  importer.py   CSV parsing and validation
  cli.py        command-line interface
tests/          pytest suite
examples/       sample aircraft, a design update and an invalid file
```

## Roadmap

- PyQt table view for browsing and editing components
- Export of rollup reports (CSV/PDF)
- Comparing two design states (diff between change-log timestamps)
- LLM-assisted mapping of differently formatted engineering source files to the import schema

## License

MIT
