"""
Generates the paper's figures from benchmark_simulation.py into research_paper/figures/
as 300-dpi PNG and vector PDF.

    pip install -r requirements.txt
    python make_figures.py

Figures
1. fig1_vhi_sensitivity    - VHI response to each input factor (one factor varied at a time)
2. fig2_vhi_scenarios      - VHI for representative vehicles, incl. a repaired critical fault
3. fig3_cost_model         - Cost estimate vs base service price for each severity
4. fig4_synthetic_error    - MAPE and interval coverage as a function of the ASSUMED noise level
5. fig5_formula_latency    - Per-call computation time of the cost formula
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from benchmark_simulation import (
    SEVERITY_MULTIPLIERS,
    VHI_SCENARIOS,
    calculate_vhi,
    estimate_cost,
    run_benchmarks,
)

OUT = Path(__file__).resolve().parent / "figures"

# Validated categorical slots (light surface), used in fixed order.
# Slot 4 (yellow) only appears on the 4-line chart, where every line is also direct-labelled.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MARKERS = ["o", "s", "^", "D"]  # secondary encoding so lines survive grayscale print
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"

COMPLIANCE_BANDS = [(90, "Excellent"), (75, "Good"), (60, "Fair"), (40, "Needs attention")]

# IEEE column widths in inches
SINGLE_COL, DOUBLE_COL = 3.5, 7.16

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": 8,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "text.color": INK,
        "legend.frameon": False,
        "legend.fontsize": 7.5,
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,  # embed TrueType so journal PDF checks pass
    }
)


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{name}.png and .pdf")


def draw_compliance_bands(ax, label=True):
    for threshold, name in COMPLIANCE_BANDS:
        ax.axhline(threshold, color=AXIS, linewidth=0.7, linestyle=(0, (3, 3)), zorder=1)
        if label:
            ax.text(1.0, threshold, f" {name} ≥{threshold}", transform=ax.get_yaxis_transform(),
                    va="center", ha="left", fontsize=6.5, color=MUTED, clip_on=False)


def fig1_vhi_sensitivity():
    # Reference vehicle: 4 years old, 1 completed service, no open issues -> VHI 93
    ref = dict(service_count=1, critical_issues=0, warning_issues=0, resolved_issues=0, age=4)
    panels = [
        ("Critical issues", "critical_issues", range(0, 5)),
        ("Open warnings*", "warning_issues", range(0, 8)),
        ("Vehicle age (years)", "age", range(0, 21)),
        ("Completed services", "service_count", range(0, 7)),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.1), sharey=True)
    for i, (ax, (label, key, values)) in enumerate(zip(axes, panels)):
        xs = list(values)
        ys = [calculate_vhi(**{**ref, key: x}) for x in xs]
        ax.plot(xs, ys, color=SERIES[0], linewidth=1.8, marker="o", markersize=3.2, zorder=3)
        ax.set_title(label, fontsize=7, fontweight="normal", color=INK_2)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5, integer=True))
        ax.set_ylim(0, 105)
        ax.set_xlim(min(xs) - 0.3, max(xs) + 0.3)
        draw_compliance_bands(ax, label=(i == len(axes) - 1))
    axes[0].set_ylabel("VHI (0-100)")
    fig.suptitle("VHI response to each factor (others held at a 4-year-old car, 1 service, no issues)",
                 x=0.0, ha="left", fontsize=8.5, fontweight="bold")
    fig.text(0.0, -0.08,
             "Bonuses push most maintained cars past the 100 cap, so the index cannot separate them; "
             "a single critical issue costs 25 points.\n*Includes pending repair requests.",
             fontsize=7, color=INK_2, ha="left")
    fig.tight_layout(rect=(0, 0, 0.93, 1), w_pad=2.2)
    save(fig, "fig1_vhi_sensitivity")


def fig2_vhi_scenarios():
    scenarios = dict(VHI_SCENARIOS)
    # A critical fault stops counting once its repair is approved and the service completed.
    scenarios["Critical fault found and repaired (4 yrs, 1 Serv)"] = (1, 0, 0, 1, 4)
    scenarios["Critical fault found, repair declined (4 yrs, 1 Serv)"] = (1, 1, 0, 0, 4)
    names = list(scenarios)[::-1]
    scores = [calculate_vhi(*scenarios[n]) for n in names]

    fig, ax = plt.subplots(figsize=(SINGLE_COL * 1.45, 2.2))
    bars = ax.barh(names, scores, color=SERIES[0], height=0.55, zorder=3)
    for bar, score in zip(bars, scores):
        band = next((b for t, b in COMPLIANCE_BANDS if score >= t), "Critical")
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2, f"{score}  ({band})",
                va="center", fontsize=7, color=INK)
    ax.set_xlim(0, 125)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("VHI (0-100)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("VHI for representative vehicles")
    save(fig, "fig2_vhi_scenarios")


def fig3_cost_model():
    base_prices = np.linspace(1000, 12000, 12)
    labor_hours, fuel = 1.5, "PETROL"
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.5))
    for i, severity in enumerate(SEVERITY_MULTIPLIERS):
        est = [estimate_cost(b, severity, fuel, labor_hours)[0] for b in base_prices]
        ax.plot(base_prices, est, color=SERIES[i], linewidth=1.8, marker=MARKERS[i], markersize=3.2,
                markevery=2, zorder=3, label=severity.title())
        ax.text(base_prices[-1] + 250, est[-1], severity.title(), va="center", fontsize=7, color=INK)
    ax.set_xlim(0, 14200)
    ax.set_xlabel("Base service price (₹)")
    ax.set_ylabel("Point estimate (₹)")
    k_fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v else "0")
    ax.xaxis.set_major_formatter(k_fmt)
    ax.yaxis.set_major_formatter(k_fmt)
    ax.legend(title="Severity", loc="upper left", title_fontsize=7.5)
    ax.set_title("Cost estimate by severity (petrol, 1.5 h labour)")
    fig.text(0.0, -0.1, "Range shown to the customer: 85%-125% of the point estimate.",
             fontsize=7, color=INK_2, ha="left")
    save(fig, "fig3_cost_model")


def fig4_synthetic_error():
    sigmas = np.array([0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25])
    runs = [run_benchmarks(n_samples=4000, noise_sigma=s, verbose=False) for s in sigmas]
    mape = np.array([r["mape"] for r in runs])
    picp = np.array([r["picp"] for r in runs])
    used = run_benchmarks(verbose=False)  # the configuration reported in the paper

    from math import erf, sqrt

    phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    fine = np.linspace(0.005, 0.26, 200)
    mape_theory = fine * np.sqrt(2 / np.pi) * 100
    picp_theory = [(phi(0.25 / s) - phi(-0.15 / s)) * 100 for s in fine]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_COL, 2.4))
    for ax, sim, theory, theory_label, ylabel, title in (
        (ax1, mape, mape_theory, "Approximation σ√(2/π)", "MAPE (%)", "MAPE vs assumed noise"),
        (ax2, picp, picp_theory, "Exact (normal CDF)", "Coverage of 85%-125% range (%)", "Interval coverage vs assumed noise"),
    ):
        ax.plot(fine * 100, theory, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)), label=theory_label, zorder=2)
        ax.plot(sigmas * 100, sim, color=SERIES[0], linewidth=0, marker="o", markersize=4, label="Simulation", zorder=3)
        ax.axvline(used["noise_sigma"] * 100, color=SERIES[1], linewidth=1, zorder=1)
        ax.set_xlabel("Assumed noise σ of synthetic ground truth (%)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xlim(0, 26)
    ax1.text(used["noise_sigma"] * 100 + 0.6, ax1.get_ylim()[1] * 0.9,
             f"paper setting σ=8%\nMAPE {used['mape']:.2f}%", fontsize=7, color=INK, va="top")
    ax2.text(used["noise_sigma"] * 100 + 0.6, 30,
             f"paper setting σ=8%\ncoverage {used['picp']:.1f}%", fontsize=7, color=INK)
    ax2.set_ylim(0, 102)
    ax1.legend(loc="lower right")
    ax2.legend(loc="lower left")
    fig.text(0.0, -0.08,
             "Ground truth is the estimate times N(1, σ): the metrics follow the assumed σ, not estimator quality. "
             "Real accuracy needs observed invoice amounts.",
             fontsize=7, color=INK_2, ha="left")
    fig.tight_layout()
    save(fig, "fig4_synthetic_error")


def fig5_formula_latency():
    res = run_benchmarks(n_samples=20000, verbose=False)
    lat_us = res["latencies_ms"] * 1000
    lat_us = lat_us[lat_us > 0]
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.2))
    bins = np.logspace(np.log10(lat_us.min()), np.log10(lat_us.max()), 40)
    ax.hist(lat_us, bins=bins, color=SERIES[0], edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    median, p99 = np.median(lat_us), np.percentile(lat_us, 99)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)  # headroom so the labels sit above the bars
    for value, label, side in ((median, "median", "right"), (p99, "p99", "left")):
        ax.axvline(value, color=INK_2, linewidth=0.9, linestyle=(0, (3, 2)), zorder=4)
        offset = 0.93 if side == "right" else 1.08  # median label left of its line, p99 label right of it
        ax.text(value * offset, ax.get_ylim()[1] * 0.92, f"{label}\n{value:.2f} µs", fontsize=6.5, color=INK,
                va="top", ha=side)
    ax.set_xlabel("Time per estimate (µs, log scale)")
    ax.set_ylabel("Calls")
    ax.set_title("Cost formula computation time (20,000 calls)")
    fig.text(0.0, -0.1, "Pure formula only - excludes API, database and network time.", fontsize=7, color=INK_2, ha="left")
    save(fig, "fig5_formula_latency")


if __name__ == "__main__":
    print("Generating figures...")
    fig1_vhi_sensitivity()
    fig2_vhi_scenarios()
    fig3_cost_model()
    fig4_synthetic_error()
    fig5_formula_latency()
