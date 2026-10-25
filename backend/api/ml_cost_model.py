"""
Learned repair-cost estimator.

Training data: every approved extra repair on a completed booking. The target is what the customer
was actually billed for that repair (repair charge + repair labour at the invoice rate). Inputs are
known before the repair is done: inspection severity, fuel type, vehicle age, the booked package's
base price and the mechanic's labour-hour estimate.

Model: ridge regression on log(cost), solved in closed form with numpy. Log space makes errors
proportional (a ₹500 miss matters more on a ₹2,000 job than on a ₹40,000 one) and keeps predictions
positive. The 80% price range comes from the spread of the model's own cross-validated errors.

Evaluation: k-fold cross-validation, scoring this model and the existing rule-based formula on the
same held-out repairs, so the comparison is like for like.
"""
import math
from decimal import Decimal

import numpy as np
from django.utils import timezone

from .ai_cost_service import DEFAULT_HOURLY_LABOR_RATE, FallbackRuleBasedEstimator
from .models import BookingStatus, CostModel, RepairRequest, RepairRequestStatus, ServiceInspection

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
FUELS = ["PETROL", "DIESEL", "CNG", "ELECTRIC", "HYBRID"]
NUMERIC = ["vehicle_age", "log_base_price", "labor_hours"]
FEATURES = NUMERIC + [f"severity_{s}" for s in SEVERITIES[1:]] + [f"fuel_{f}" for f in FUELS[1:]]

INVOICE_LABOR_RATE = 400  # per hour, as charged in invoice_service
MIN_TRAINING_SAMPLES = 30
RIDGE_LAMBDA = 1.0
DEFAULT_BASE_PRICE = 1500.0
# Generated demo history (seed_repair_history) is marked in the booking notes and owned by this account
SYNTHETIC_MARKER = "[synthetic]"
SYNTHETIC_HISTORY_EMAIL = "synthetic-history@smartdoorstep.local"


def feature_row(severity, fuel_type, vehicle_age, base_price, labor_hours):
    sev = (severity or "MEDIUM").upper()
    fuel = (fuel_type or "PETROL").upper()
    row = {
        "vehicle_age": float(max(0, vehicle_age)),
        "log_base_price": math.log(float(base_price or DEFAULT_BASE_PRICE)),
        "labor_hours": float(labor_hours or 0),
    }
    for s in SEVERITIES[1:]:
        row[f"severity_{s}"] = 1.0 if sev == s else 0.0
    for f in FUELS[1:]:
        row[f"fuel_{f}"] = 1.0 if fuel == f else 0.0
    return [row[name] for name in FEATURES]


def training_rows():
    """(features, billed cost, inputs for the rule formula, is_synthetic) for every usable repair."""
    repairs = (
        RepairRequest.objects.filter(status=RepairRequestStatus.APPROVED, booking__status=BookingStatus.COMPLETED)
        .select_related("booking__vehicle", "booking__service_type")
    )
    rows = []
    for r in repairs:
        cost = float(r.additional_cost or 0) + r.estimated_extra_hours * INVOICE_LABOR_RATE
        if cost <= 0:
            continue
        booking = r.booking
        inspection = ServiceInspection.objects.filter(booking=booking).order_by("-created_at").first()
        severity = inspection.severity if inspection else "MEDIUM"
        age = booking.created_at.year - (booking.vehicle.year or booking.created_at.year)
        base = float(booking.service_type.base_price) if booking.service_type else DEFAULT_BASE_PRICE
        rows.append({
            "x": feature_row(severity, booking.vehicle.fuel_type, age, base, r.estimated_extra_hours),
            "y": cost,
            "rule": (booking.vehicle, booking.service_type, severity, r.estimated_extra_hours),
            "synthetic": booking.customer_notes.startswith(SYNTHETIC_MARKER),
        })
    return rows


class RidgeModel:
    def __init__(self, lam=RIDGE_LAMBDA):
        self.lam = lam

    def fit(self, X, log_y):
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std == 0] = 1.0  # a constant column (e.g. no CNG cars yet) stays harmless
        Z = np.hstack([np.ones((len(X), 1)), (X - self.mean) / self.std])
        penalty = self.lam * np.eye(Z.shape[1])
        penalty[0, 0] = 0.0  # never shrink the intercept
        self.weights = np.linalg.solve(Z.T @ Z + penalty, Z.T @ log_y)
        return self

    def predict_log(self, X):
        Z = np.hstack([np.ones((len(X), 1)), (X - self.mean) / self.std])
        return Z @ self.weights


def _rule_point(vehicle, service_type, severity, labor_hours):
    est = FallbackRuleBasedEstimator().estimate(vehicle, service_type, "", severity, Decimal(str(labor_hours or 1)))
    # The formula's own point estimate sits between its 85% and 125% bounds
    return float(est["estimated_min_cost"]) / 0.85


def _scores(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    return {
        "mae": round(float(np.mean(np.abs(predicted - actual))), 2),
        "mape": round(float(100 * np.mean(np.abs(predicted - actual) / actual)), 2),
    }


def cross_validate(rows, folds=5, seed=42):
    """
    Out-of-fold predictions for both estimators. Each fold's 80% range is set from its own training
    repairs only, then checked on the held-out ones, so the coverage figure is an honest test.
    """
    X = np.array([r["x"] for r in rows])
    y = np.array([r["y"] for r in rows])
    order = np.random.default_rng(seed).permutation(len(rows))
    ml_pred = np.zeros(len(rows))
    residuals = np.zeros(len(rows))
    inside = np.zeros(len(rows), dtype=bool)
    for k in range(folds):
        test = order[k::folds]
        train = np.setdiff1d(order, test)
        model = RidgeModel().fit(X[train], np.log(y[train]))
        lo, hi = np.quantile(np.log(y[train]) - model.predict_log(X[train]), [0.10, 0.90])
        log_pred = model.predict_log(X[test])
        ml_pred[test] = np.exp(log_pred)
        residuals[test] = np.log(y[test]) - log_pred
        inside[test] = (residuals[test] >= lo) & (residuals[test] <= hi)
    rule_pred = [_rule_point(*r["rule"]) for r in rows]
    # The deployed range uses the spread of held-out errors, which is wider than in-sample error
    lo, hi = np.quantile(residuals, [0.10, 0.90])
    return {
        "ml": _scores(y, ml_pred),
        "rule_based": _scores(y, rule_pred),
        "interval_coverage": round(float(100 * inside.mean()), 1),
        "residual_q10": float(lo),
        "residual_q90": float(hi),
    }


def train_cost_model(min_samples=MIN_TRAINING_SAMPLES):
    """Trains on all usable repairs and stores the result as the active model. Raises ValueError if too few."""
    rows = training_rows()
    if len(rows) < min_samples:
        raise ValueError(f"Only {len(rows)} completed, approved repairs to learn from; at least {min_samples} are needed.")
    X = np.array([r["x"] for r in rows])
    y = np.array([r["y"] for r in rows])
    cv = cross_validate(rows)
    model = RidgeModel().fit(X, np.log(y))
    synthetic_share = round(100 * sum(r["synthetic"] for r in rows) / len(rows), 1)

    CostModel.objects.filter(is_active=True).update(is_active=False)
    return CostModel.objects.create(
        n_samples=len(rows),
        synthetic_share=synthetic_share,
        features=FEATURES,
        weights=model.weights.tolist(),
        feature_mean=model.mean.tolist(),
        feature_std=model.std.tolist(),
        residual_q10=cv["residual_q10"],
        residual_q90=cv["residual_q90"],
        metrics={k: cv[k] for k in ("ml", "rule_based", "interval_coverage")},
        is_active=True,
    )


def active_model():
    model = CostModel.objects.filter(is_active=True).order_by("-trained_at").first()
    if model and model.n_samples >= MIN_TRAINING_SAMPLES and model.features == FEATURES:
        return model
    return None


def predict(stored: CostModel, vehicle, service_type, severity, labor_hours):
    age = timezone.localdate().year - (vehicle.year or timezone.localdate().year)
    base = float(service_type.base_price) if service_type else DEFAULT_BASE_PRICE
    x = np.array([feature_row(severity, vehicle.fuel_type, age, base, labor_hours)])
    model = RidgeModel()
    model.mean = np.array(stored.feature_mean)
    model.std = np.array(stored.feature_std)
    model.weights = np.array(stored.weights)
    log_point = float(model.predict_log(x)[0])
    return {
        "point": math.exp(log_point),
        "low": math.exp(log_point + stored.residual_q10),
        "high": math.exp(log_point + stored.residual_q90),
    }
