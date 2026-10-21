# Research paper: simulation and figures

```bash
pip install -r requirements.txt
python benchmark_simulation.py   # prints the metrics
python make_figures.py           # writes figures/*.png (300 dpi) and figures/*.pdf (vector)
```

The VHI and cost formulas in `benchmark_simulation.py` mirror the app (`backend/api/health_service.py`, `backend/api/ai_cost_service.py`). If either formula changes in the app, update the script and regenerate.

## Figures

| File | Shows | Safe to claim |
|---|---|---|
| `fig1_vhi_sensitivity` | VHI as one input varies (critical issues, open warnings, age, services) | How the index responds to each factor |
| `fig2_vhi_scenarios` | VHI for representative vehicles | Example scores, including a repaired critical fault |
| `fig3_cost_model` | Point estimate vs base price for each severity | How the estimator scales; the customer sees 85-125% of it |
| `fig4_synthetic_error` | MAPE and interval coverage vs the **assumed** noise level | That these metrics are set by the simulation's noise assumption |
| `fig5_formula_latency` | Per-call time of the cost formula | Formula cost only (machine-dependent; varies run to run) |

Figures use colorblind-checked colors, and each line also has its own marker or label, so they stay readable in grayscale print.

## Limitations to state in the paper

1. **The cost "accuracy" is not measured against real data.** Each simulated order's ground truth is the estimate multiplied by N(1, σ) with σ = 8%. MAPE ≈ σ·√(2/π) ≈ 6.4% and coverage ≈ 97% follow from that choice (Fig. 4), not from estimator quality. To report real accuracy, replace the synthetic ground truth with final invoice amounts for real repairs.
2. **VHI saturates at 100.** A new car and a 6-year-old maintained car both score 100, so the index cannot rank healthy vehicles (Fig. 1, 2).
3. **Inspection findings are never cleared.** A critical fault keeps its −25 penalty after it is repaired (+3 for the approved repair), so a repaired car stays "Fair" (Fig. 2).
4. **Latency** covers the formula only, not the API, database or network.
