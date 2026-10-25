import { Link, useNavigate } from "react-router-dom";
import { AICostEstimatorModal } from "../components/AICostEstimatorModal";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import type { ServiceType, Vehicle } from "../types";

export function Estimate() {
  const navigate = useNavigate();
  const { data: vehicles, loading: loadingVehicles } = useApi<Vehicle[]>("/api/vehicles/");
  const { data: serviceTypes, loading: loadingServices } = useApi<ServiceType[]>("/api/service-types/");

  if (loadingVehicles || loadingServices) return <Skeleton className="h-64" />;

  if (!vehicles?.length) {
    return (
      <div className="space-y-3">
        <Empty title="Add a vehicle first" hint="Cost estimates are calculated for a specific vehicle." />
        <Link to="/app/vehicles" className="inline-block rounded-2xl bg-brand px-4 py-2 font-semibold text-white">
          Add vehicle
        </Link>
      </div>
    );
  }

  return <AICostEstimatorModal vehicles={vehicles} serviceTypes={serviceTypes ?? []} onClose={() => navigate("/app")} />;
}
