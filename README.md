# Omelet

> 🚧 **Under heavy construction.** This is the current, actively-developed code.

Omelet is a packaging-aware, packaging-aware network simulator for 2.5D and 3D chiplet systems. 

## Requirements

- Linux, `gcc`/`g++`, `git`, `python3`, `scons`, and Python `pyyaml`.
- ~10 GB disk and a few minutes to build gem5.

## Install

`scripts/install.sh` fetches the pinned gem5 (v22.1.0.0) submodule, applies the
Omelet Garnet patches, links the Omelet gem5 configs, installs the `omelet`
package, and builds `gem5.opt`:

```bash
git clone --recurse-submodules <this-repo> omelet
cd omelet
scripts/install.sh
```

The build takes ~6-10 minutes. When it finishes you have
`gem5/build/Garnet_standalone/gem5.opt`.

## Run the examples

Run from the repo root. If gem5 cannot import the `omelet` package, export the
path first:

```bash
export PYTHONPATH="$PWD"
```

**2.5D — four chiplets on an organic interposer, mesh NoI:**

```bash
omelet-run examples/config/2_5d_org_mesh.yaml --injectionrate 0.1
```

**3D — eight chiplets in two stacked tiers (NoC + NoI + NoL):**

```bash
omelet-run examples/config/3d_org_mesh.yaml --injectionrate 0.1
```

Each run creates `results/<config>_ir<rate>/` automatically, containing
`stats.txt` (gem5 stats), `config.ini` (the built network), and `energy.txt`
(traffic-activated interconnect energy from the EPB tables).

Sweep a load-latency curve by running several injection rates
(`--injectionrate 0.02 … 1.0`) and reading `average_flit_latency` from each
`stats.txt`.

## What to set

A design point is the input files referenced by the top-level config
(`examples/config/*.yaml`). The important knobs are:

| What | Where | Effect |
|---|---|---|
| Interposer material | `tech.interposer` (`interposer_org` / `interposer_sil`) | RDL pitch and latency/EPB tables. Silicon is finer-pitch → higher D2D bandwidth. |
| Bonding | `--bonding` (2.5D) / `simulation.bonding` | solder / ubump / cucu / hybrid — the bond pitch. |
| Chiplet size (area) | `examples/layout/*.yaml` `width`/`height` | The die edge is the D2D beach-front; bigger chiplets → wider inter-chiplet links. |
| 3D vertical bonding | `simulation.c2c_bonding` (ubump10 / cucu / hybrid) | Selects the F2F vertical latency/EPB table. |
| 3D vertical width | `system.via_signal_area_mm2` | Signal-bearing share of the die overlap |


## Scope & Limitations

Omelet is a research simulator for early-stage design-space exploration of 2.5D/3D chiplet systems. Omelet can be used to compare design points and spot trends, not to sign off a final design or trust an absolute number.

### 1) PHY Modeling

Our current model uses a simplified abstraction of the PHY layer, including CDC and SerDes. Future versions could add more detailed PHY models, but at present we do not support accurate PHY modeling.

### 2) Extrapolation outof range we support

We cannot guarantee the numbers **outside of the ranges we tested**. Pushing a parameter past the validated range gives an extrapolation we do not guarantee.

- scaling link lanency/EPB for a longer link than we support
- a bump or TSV pitch finer than anything we characterized


## Contact & Maintenance

We're actively improving Omelet and expect it to get more accurate and more capable over time. Feedback, bug reports, and contributions are all very welcome!

- **[Submit an issue report](https://forms.gle/R1APEBE6Qj56CBuaA)** (preferred for bugs and feature requests). Include your config, the command you ran, and what you expected versus what happened.
- **Email the maintainers** for questions that do not fit an issue.

**Core maintainers**

| Name | Role | Email |
|---|---|---|
| Jiho Kim | Maintainer | jiho.kim@gatech.edu |
