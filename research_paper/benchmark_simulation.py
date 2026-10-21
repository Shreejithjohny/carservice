"""
Simulation script for the research paper.
Evaluates:
1. Vehicle Health Index (VHI) response to service history, faults and vehicle age
2. Parametric cost estimator error metrics (MAE, RMSE, MAPE, interval coverage) on SYNTHETIC data
3. Computation time of the cost formula

IMPORTANT: there is no real repair-price data here. The "ground truth" for each simulated order is the
estimator's own output multiplied by Gaussian noise N(1, noise_sigma). The error metrics therefore
measure the assumed noise, not real-world accuracy (MAPE ~= noise_sigma * sqrt(2/pi)). Report them as a
simulation/sensitivity result, or replace ground_truth with observed invoice amounts before claiming accuracy.

The VHI and cost formulas mirror backend/api/health_service.py and backend/api/ai_cost_service.py.
Run make_figures.py to produce the paper's charts.
"""

import time
import random
import numpy as np

# Severity Multipliers matching backend
SEVERITY_MULTIPLIERS = {
    "LOW": 1.0,
    "MEDIUM": 1.35,
    "HIGH": 1.8,
    "CRITICAL": 2.4,
}

FUEL_ADJUSTMENTS = {
    "PETROL": 1.0,
    "CNG": 1.0,
    "DIESEL": 1.10,
    "ELECTRIC": 1.15,
    "HYBRID": 1.15,
}

LABOR_HOURLY_RATE = 500.0


def calculate_vhi(service_count, critical_issues, warning_issues, resolved_issues, age):
    """Vehicle Health Index as implemented in the app (warning_issues there also includes pending repairs)."""
    base_score = 90
    service_bonus = min(service_count * 5, 15)
    resolved_bonus = min(resolved_issues * 3, 10)
    critical_penalty = critical_issues * 25
    warning_penalty = warning_issues * 10
    age_penalty = max(0, (age - 3) * 2)

    raw = base_score + service_bonus + resolved_bonus - critical_penalty - warning_penalty - age_penalty
    return max(0, min(100, raw))


def estimate_cost(base_price, severity, fuel_type, labor_hours):
    """Formalized Parametric Cost Estimation."""
    sev_mult = SEVERITY_MULTIPLIERS[severity]
    fuel_adj = FUEL_ADJUSTMENTS[fuel_type]
    labor_cost = labor_hours * LABOR_HOURLY_RATE
    comp = (base_price * sev_mult * fuel_adj) + labor_cost
    min_cost = comp * 0.85
    max_cost = comp * 1.25
    return comp, min_cost, max_cost


VHI_SCENARIOS = {
    "Pristine (New, 2 Services, 0 Faults)": (2, 0, 0, 0, 1),
    "Maintained Aged (6 yrs, 4 Services, 1 Resolved)": (4, 0, 0, 1, 6),
    "Moderate Degradation (4 yrs, 1 Serv, 2 Warnings)": (1, 0, 2, 0, 4),
    "Critical Unaddressed (5 yrs, 0 Serv, 2 Critical)": (0, 2, 1, 0, 5),
}


def run_benchmarks(n_samples=1000, noise_sigma=0.08, seed=42, verbose=True):
    """Runs the simulation and returns the metrics (and raw samples) as a dict."""
    random.seed(seed)
    np.random.seed(seed)

    # 1. Cost Estimation Evaluation
    base_prices = [1200, 1500, 2500, 4000, 7500, 12000]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    fuels = ["PETROL", "DIESEL", "CNG", "ELECTRIC", "HYBRID"]

    actual_costs = []
    estimated_medians = []
    latencies = []
    coverage_count = 0

    for _ in range(n_samples):
        base = random.choice(base_prices)
        sev = random.choice(severities)
        fuel = random.choice(fuels)
        labor = round(random.uniform(0.5, 4.5), 1)

        t0 = time.perf_counter()
        comp, min_c, max_c = estimate_cost(base, sev, fuel, labor)
        latencies.append((time.perf_counter() - t0) * 1000)

        # Synthetic ground truth: the estimate itself times Gaussian noise (std = noise_sigma)
        ground_truth = comp * np.random.normal(1.0, noise_sigma)
        actual_costs.append(ground_truth)
        estimated_medians.append(comp)

        if min_c <= ground_truth <= max_c:
            coverage_count += 1

    actual_costs = np.array(actual_costs)
    estimated_medians = np.array(estimated_medians)

    mae = np.mean(np.abs(actual_costs - estimated_medians))
    rmse = np.sqrt(np.mean((actual_costs - estimated_medians) ** 2))
    mape = np.mean(np.abs((actual_costs - estimated_medians) / actual_costs)) * 100
    confidence_interval_coverage = (coverage_count / n_samples) * 100
    avg_latency = np.mean(latencies)
    p99_latency = np.percentile(latencies, 99)

    # 2. VHI Sensitivity Analysis across conditions
    vhi_samples = {name: calculate_vhi(*args) for name, args in VHI_SCENARIOS.items()}

    results = {
        "n_samples": n_samples,
        "noise_sigma": noise_sigma,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "picp": confidence_interval_coverage,
        "latency_mean_ms": avg_latency,
        "latency_p99_ms": p99_latency,
        "latencies_ms": np.array(latencies),
        "vhi_samples": vhi_samples,
    }
    if not verbose:
        return results

    print("--- SIMULATION RESULTS (synthetic ground truth; see module docstring) ---")
    print(f"Sample Size: {n_samples} simulated repair orders, assumed noise sigma = {noise_sigma:.0%}")
    print(f"Mean Absolute Error (MAE): INR {mae:.2f}")
    print(f"Root Mean Squared Error (RMSE): INR {rmse:.2f}")
    print(f"Mean Absolute Percentage Error (MAPE): {mape:.2f}%")
    print(f"Prediction Interval Coverage Probability (PICP @ 85%-125%): {confidence_interval_coverage:.2f}%")
    print(f"Algorithmic Inference Latency (Mean): {avg_latency*1000:.3f} microseconds")
    print(f"Algorithmic Inference Latency (99th percentile): {p99_latency*1000:.3f} microseconds")
    print("\nVHI Representative Scores:")
    for k, v in vhi_samples.items():
        print(f"  {k}: {v}/100")
    return results


if __name__ == "__main__":
    run_benchmarks()
