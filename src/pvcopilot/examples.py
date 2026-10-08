"""The nine example datasets shipped with PV-Copilot (same as the web app's globe)."""
from __future__ import annotations

import pandas as pd

from ._paths import example_path

# key: (file, description, latitude, longitude, location)
EXAMPLES = {
    "sys1278":        ("sys_1278_downsampled_with_VI.parquet", "PVDAQ 1278, 8.9 yr c-Si",
                       36.1952, -115.1582, "Las Vegas, NV, USA"),
    "sys1403":        ("sys_1403_part1_downsampled_with_VI.parquet", "PVDAQ 1403, 3.1 yr c-Si",
                       28.405, -80.7709, "Cocoa Beach, FL, USA"),
    "sys1422":        ("sys_1422_downsampled.parquet", "PVDAQ 1422, 1.7 yr c-Si",
                       44.4665, -73.1014, "Burlington, VT, USA"),
    "pvdaq4":         ("pvdaq_system4_golden_hourly.parquet", "PVDAQ system 4, 6.8 yr c-Si",
                       39.7406, -105.1774, "Golden, CO, USA"),
    "nrel_stf":       ("nrel_stf_golden_hourly.parquet", "NREL STF building, 8.3 yr multi-Si",
                       39.7422, -105.1719, "Golden, CO, USA"),
    "pvdaq1300":      ("pvdaq_system1300_stpetersburg_hourly.parquet",
                       "PVDAQ 1300, 5.5 yr c-Si (3-yr outage)", 27.7701, -82.629,
                       "St Petersburg, FL, USA"),
    "eurac6":         ("eurac_bolzano_pcSi6_hourly.parquet", "EURAC system 6, 8.0 yr multi-Si",
                       46.4576, 11.3285, "Bolzano, Italy"),
    "pfaffstaetten":  ("pfaffstaetten_austria_hourly.parquet", "Pfaffstätten A, 6.3 yr c-Si",
                       48.017, 16.258, "Pfaffstätten, Austria"),
    "ucy_nicosia":    ("ucy_nicosia_monoSi_hourly.parquet", "UCY Nicosia, 10.0 yr mono-Si",
                       35.145, 33.410, "Nicosia, Cyprus"),
}


# Column mapping for each example (role -> column), checked against the data.
# Pass it to analyze() to skip the LLM:  analyze("pvdaq4", EXAMPLE_MAPPINGS["pvdaq4"])
# "Time" is omitted: every example already has the timestamps on its index.
# Roles a dataset does not have are left out (e.g. no V/I -> no PVPRO).
EXAMPLE_MAPPINGS = {
    # PVDAQ 1278: DC power + inverter-1 input V/I (PVPRO-capable)
    "sys1278": {"DC Power": "dc_power", "Irradiance": "poa_irradiance",
                "Module temperature": "module_temperature_C",
                "DC Voltage": "inv1_input_voltage", "DC Current": "inv1_input_current"},
    # PVDAQ 1403: as above; module_temperature_C has logger error codes (3276.7),
    # which the preprocessing removes
    "sys1403": {"DC Power": "dc_power", "Irradiance": "poa_irradiance",
                "Module temperature": "module_temperature_C",
                "DC Voltage": "inv1_dc_voltage", "DC Current": "inv1_dc_current1"},
    # PVDAQ 1422: 1.7 yr only (YoY needs 2 yr -> falls back to LR); no V/I
    "sys1422": {"DC Power": "dc_power_inv1", "Irradiance": "poa_irradiance",
                "Module temperature": "module_temperature_C"},
    # PVDAQ system 4 (RdTools example): AC power only, no module temperature
    "pvdaq4": {"DC Power": "ac_power", "Irradiance": "poa_irradiance"},
    # NREL STF: AC power. Three irradiance channels; poa_local drifts upward
    # (P/G rises ~1 %/yr, which reads as +1.4 %/yr "improvement"), so the measured 40° POA is used
    "nrel_stf": {"DC Power": "ac_power", "Irradiance": "poa_measured_40",
                 "Module temperature": "module_temp"},
    # PVDAQ 1300: DC power/V/I; temperatures in °F (converted automatically);
    # 3-year outage in the middle of the record
    "pvdaq1300": {"DC Power": "dc_power_calc", "Irradiance": "intsolirrad",
                  "Module temperature": "module_temp_f",
                  "DC Voltage": "dc_voltage", "DC Current": "dc_current"},
    # EURAC Bolzano system 6: MPP DC power/V/I (PVPRO-capable)
    "eurac6": {"DC Power": "P_mpp_[W]", "Irradiance": "POA_pyranometer_[W/m2]",
               "Module temperature": "BackOfModule_Temperature_[C]",
               "DC Voltage": "U_mpp_[V]", "DC Current": "I_mpp_[A]"},
    # Pfaffstätten A: DC power, no V/I
    "pfaffstaetten": {"DC Power": "Pdc", "Irradiance": "G_POA", "Module temperature": "Tmod"},
    # UCY Nicosia mono-Si: MPP power, no V/I
    "ucy_nicosia": {"DC Power": "Pmpp (W)", "Irradiance": "GPOA (W/m2)",
                    "Module temperature": "Tmod (°C)"},
}


def list_examples() -> pd.DataFrame:
    """Table of the bundled example datasets."""
    return pd.DataFrame(
        [(k, v[1], v[4], v[2], v[3], v[0]) for k, v in EXAMPLES.items()],
        columns=["name", "description", "location", "latitude", "longitude", "file"],
    ).set_index("name")


def _resolve(name: str):
    if name in EXAMPLES:
        return EXAMPLES[name][0]
    for v in EXAMPLES.values():
        if name == v[0]:
            return v[0]
    raise KeyError(f"unknown example {name!r}; choose from {', '.join(EXAMPLES)}")


def example_file(name: str) -> str:
    return str(example_path(_resolve(name)))


def load_example(name: str) -> pd.DataFrame:
    """Raw example data, column names exactly as published."""
    return pd.read_parquet(example_file(name))


def export_example(name: str, path: str | None = None) -> str:
    """Write an example as CSV (e.g. to try the upload box in the web UI)."""
    import os
    path = path or f"{name}.csv"
    if os.path.isdir(path):
        path = os.path.join(path, f"{name}.csv")
    load_example(name).to_csv(path)
    return path
