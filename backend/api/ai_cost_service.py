from decimal import Decimal
from typing import Dict, Any, Optional

SEVERITY_MULTIPLIERS = {
    "LOW": Decimal("1.0"),
    "MEDIUM": Decimal("1.35"),
    "HIGH": Decimal("1.8"),
    "CRITICAL": Decimal("2.4"),
}

FUEL_TYPE_ADJUSTMENTS = {
    "PETROL": Decimal("1.0"),
    "CNG": Decimal("1.0"),
    "DIESEL": Decimal("1.10"),
    "ELECTRIC": Decimal("1.15"),
    "HYBRID": Decimal("1.15"),
}

DEFAULT_HOURLY_LABOR_RATE = Decimal("500.00")


class BaseAIEstimatorProvider:
    """Base interface for repair cost estimator providers (rule-based today; an ML/LLM provider can implement this later)."""

    def estimate(
        self,
        vehicle: Any,
        service_type: Optional[Any],
        issue_description: str,
        severity: str,
        estimated_labor_hours: Decimal,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class FallbackRuleBasedEstimator(BaseAIEstimatorProvider):
    """
    Deterministic rule-based estimator that runs locally without external dependencies.
    Computes cost based on service type base price, severity multiplier, labor hours,
    and vehicle powertrain characteristics.
    """

    def estimate(
        self,
        vehicle: Any,
        service_type: Optional[Any],
        issue_description: str,
        severity: str,
        estimated_labor_hours: Decimal,
    ) -> Dict[str, Any]:
        sev_key = (severity or "MEDIUM").upper()
        sev_multiplier = SEVERITY_MULTIPLIERS.get(sev_key, Decimal("1.35"))

        fuel_key = (getattr(vehicle, "fuel_type", "PETROL") or "PETROL").upper()
        fuel_adj = FUEL_TYPE_ADJUSTMENTS.get(fuel_key, Decimal("1.0"))

        # Base parts/service rate
        if service_type and hasattr(service_type, "base_price"):
            base_service_cost = Decimal(str(service_type.base_price))
        else:
            base_service_cost = Decimal("1500.00")

        # Labor cost calculation
        labor_hours = Decimal(str(estimated_labor_hours or "1.5"))
        if labor_hours <= 0:
            labor_hours = Decimal("1.0")
        labor_cost = labor_hours * DEFAULT_HOURLY_LABOR_RATE

        # Combined cost with multipliers
        composite_base = (base_service_cost * sev_multiplier * fuel_adj) + labor_cost

        # Estimated cost range: 85% to 125% of composite estimate
        min_cost = (composite_base * Decimal("0.85")).quantize(Decimal("0.01"))
        max_cost = (composite_base * Decimal("1.25")).quantize(Decimal("0.01"))

        brand_name = getattr(vehicle, "brand", "") or (vehicle.car_brand.name if getattr(vehicle, "car_brand", None) else "vehicle")
        model_name = getattr(vehicle, "model", "") or (vehicle.car_model.name if getattr(vehicle, "car_model", None) else "")
        veh_str = f"{brand_name} {model_name}".strip() or "Vehicle"

        explanation = (
            f"Calculated estimate for {veh_str} ({fuel_key}) with {sev_key} severity. "
            f"Factored base service charge of ₹{base_service_cost:.2f}, {labor_hours:.1f} estimated labor hours "
            f"(₹{DEFAULT_HOURLY_LABOR_RATE}/hr), and powertrain characteristics. "
            f"Final price may vary based on actual inspection and service-center pricing."
        )

        return {
            "estimated_min_cost": min_cost,
            "estimated_max_cost": max_cost,
            "estimated_labor_hours": labor_hours,
            "explanation": explanation,
            "estimation_source": "RULE_BASED",
        }


def estimate_repair_cost(
    vehicle: Any,
    service_type: Optional[Any],
    issue_description: str,
    severity: str = "MEDIUM",
    estimated_labor_hours: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Main helper for estimating vehicle repair costs. Uses the learned model once one has been trained
    on enough billed repairs, otherwise the rule-based formula.
    """
    from .ml_cost_model import active_model, predict

    labor_hours = Decimal(str(estimated_labor_hours)) if estimated_labor_hours is not None else Decimal("1.5")
    stored = active_model()
    if stored is not None:
        result = predict(stored, vehicle, service_type, severity, labor_hours)
        mape = stored.metrics.get("ml", {}).get("mape")
        coverage = stored.metrics.get("interval_coverage")
        if stored.synthetic_share:
            source = (
                f"Learned from {stored.n_samples} past repairs, {stored.synthetic_share:.0f}% of them synthetic demo data, "
                "so this accuracy is not real-world evidence"
            )
        else:
            source = f"Learned from {stored.n_samples} completed repairs billed by our workshops"
        return {
            "estimated_min_cost": Decimal(str(result["low"])).quantize(Decimal("0.01")),
            "estimated_max_cost": Decimal(str(result["high"])).quantize(Decimal("0.01")),
            "estimated_labor_hours": labor_hours,
            "explanation": (
                f"{source} (cross-validated average error {mape}%; {coverage}% of held-out repairs fell inside "
                "their predicted range). The final price is confirmed after inspection."
            ),
            "estimation_source": "ML",
        }

    estimator = FallbackRuleBasedEstimator()
    return estimator.estimate(
        vehicle=vehicle,
        service_type=service_type,
        issue_description=issue_description,
        severity=severity,
        estimated_labor_hours=labor_hours,
    )
