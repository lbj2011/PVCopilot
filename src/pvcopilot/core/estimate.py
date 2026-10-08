"""Data-driven filter thresholds (copied verbatim from the app page, so Simple
mode in the Python API uses the same thresholds as the web UI)."""
import numpy as np
import pandas as pd


def estimate_filter_params(df, mapping):
    out = {}
    if df is None or not mapping:
        return out
    try:
        irr = pd.to_numeric(df[mapping["Irradiance"]], errors="coerce")
        pwr = pd.to_numeric(df[mapping["DC Power"]], errors="coerce")
    except Exception:
        return out

    lit0 = np.isfinite(irr) & (irr > 0)
    if int(lit0.sum()) < 100:
        return out
    g_peak = float(np.nanpercentile(irr[lit0], 98))
    if not np.isfinite(g_peak) or g_peak <= 0:
        return out

    # 1) Min irradiance threshold
    irr_thresh = int(np.clip(round(0.18 * g_peak / 10.0) * 10, 100, 500))
    out["param-irr-thresh"] = {
        "value": irr_thresh,
        "basis": f"18% of the ~{g_peak:.0f} W/m\u00b2 clear-sky peak",
    }

    lit = np.isfinite(irr) & (irr > irr_thresh) & np.isfinite(pwr)
    ratio = (pwr / irr)[lit]
    ratio = ratio[np.isfinite(ratio)]

    # 2) gamma from a P/G-vs-temperature fit
    tkey = mapping.get("Module temperature")
    if tkey and tkey in df.columns:
        try:
            temp = pd.to_numeric(df[tkey], errors="coerce")
            m = lit & np.isfinite(temp)
            r = (pwr[m] / irr[m]).to_numpy()
            t = (temp[m] - 25.0).to_numpy()
            good = np.isfinite(r) & np.isfinite(t)
            r, t = r[good], t[good]
            if len(r) >= 200 and (np.nanmax(t) - np.nanmin(t)) > 5:
                A = np.vstack([t, np.ones_like(t)]).T
                slope, intercept = np.linalg.lstsq(A, r, rcond=None)[0]
                if intercept > 0:
                    g_est = float(np.clip(slope / intercept, -0.006, -0.001))
                    out["param-gamma"] = {
                        "value": round(g_est, 4),
                        "basis": "fit of P/G vs module temperature",
                    }
        except Exception:
            pass

    # 3) Min power / irradiance ratio floor
    if len(ratio) >= 100:
        r_lo = float(np.nanpercentile(ratio, 2))
        pr = float(np.clip(0.4 * r_lo, 0.005, 0.5))
        out["param-power-ratio"] = {
            "value": round(pr, 3),
            "basis": "40% of the 2nd-percentile daytime P/G",
        }

    # 4) IQR multiplier
    if len(ratio) >= 200:
        try:
            exkurt = float(pd.Series(ratio).kurtosis())  # Fisher (excess)
            iqr_k = 2.0 if exkurt > 3 else 1.5
            out["param-iqr-multiplier"] = {
                "value": iqr_k,
                "basis": ("heavy-tailed P/G \u2192 relaxed to 2.0" if iqr_k == 2.0
                          else "Tukey standard 1.5"),
            }
        except Exception:
            pass

    return out
