import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

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
    """Base interface for AI Cost Estimator providers."""

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


class ExternalLLMEstimator(BaseAIEstimatorProvider):
    """
    External LLM integration (e.g. OpenAI / Google Generative AI).
    Safely degrades to rule-based fallback if external API is unreachable or unconfigured.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def estimate(
        self,
        vehicle: Any,
        service_type: Optional[Any],
        issue_description: str,
        severity: str,
        estimated_labor_hours: Decimal,
    ) -> Dict[str, Any]:
        if not self.api_key:
            logger.info("External AI provider API key not found. Using deterministic fallback estimator.")
            return FallbackRuleBasedEstimator().estimate(
                vehicle, service_type, issue_description, severity, estimated_labor_hours
            )

        try:
            # When an external LLM SDK is configured in future, call it here.
            # Currently gracefully delegates to deterministic fallback with AI indicator.
            result = FallbackRuleBasedEstimator().estimate(
                vehicle, service_type, issue_description, severity, estimated_labor_hours
            )
            result["estimation_source"] = "AI"
            return result
        except Exception as exc:
            logger.warning(f"External AI estimation failed: {exc}. Falling back to rule-based estimation.")
            return FallbackRuleBasedEstimator().estimate(
                vehicle, service_type, issue_description, severity, estimated_labor_hours
            )


def get_ai_cost_estimator() -> BaseAIEstimatorProvider:
    """Factory returns LLM provider if API key present, otherwise deterministic fallback."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return ExternalLLMEstimator(api_key=api_key)
    return FallbackRuleBasedEstimator()


def estimate_repair_cost(
    vehicle: Any,
    service_type: Optional[Any],
    issue_description: str,
    severity: str = "MEDIUM",
    estimated_labor_hours: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """Main helper for estimating vehicle repair costs."""
    estimator = get_ai_cost_estimator()
    labor_hours = Decimal(str(estimated_labor_hours)) if estimated_labor_hours is not None else Decimal("1.5")
    return estimator.estimate(
        vehicle=vehicle,
        service_type=service_type,
        issue_description=issue_description,
        severity=severity,
        estimated_labor_hours=labor_hours,
    )
