import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton, Empty } from "../components/States";
import { ShieldAlert, Camera, Sparkles } from "lucide-react";
import { AICostEstimatorModal } from "../components/AICostEstimatorModal";
import type { Booking } from "../types";

export function RepairApproval() {
  const { data: bookings, loading, reload } = useApi<Booking[]>("/api/bookings/");
  const { push } = useToast();

  // Filter bookings that have active tracking data or repair requests
  const activeBookings = (bookings || []).filter(
    (b) => b.status === "Repair Approval Required" || b.status === "In Service"
  );

  if (loading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <ShieldAlert className="text-[#ff4d2e]" /> Additional Repair Approvals
        </h1>
        <p className="text-sm text-zinc-500">Inspect mechanic photo/video evidence and approve or decline additional repairs.</p>
      </div>

      {!activeBookings.length ? (
        <Empty title="No pending repair approvals" hint="All your vehicle services are currently running smoothly without additional repair requests." />
      ) : (
        <div className="space-y-6">
          {activeBookings.map((b) => (
            <BookingApprovalCard key={b.id || b._id || b.booking_reference} booking={b} onReload={reload} push={push} />
          ))}
        </div>
      )}
    </div>
  );
}

function BookingApprovalCard({ booking, onReload, push }: { booking: Booking; onReload: () => void; push: (t: any) => void }) {
  const bId = booking.id || booking._id || booking.booking_reference;
  const { data: trackingData, loading } = useApi<any>(`/api/bookings/${bId}/tracking/`);
  const [processing, setProcessing] = useState(false);
  const [selectedReqForAi, setSelectedReqForAi] = useState<any>(null);

  if (loading) return <Skeleton className="h-48" />;

  const repairRequests = trackingData?.repair_requests || [];
  const evidenceItems = trackingData?.evidence || [];

  async function handleApprove(reqId: number | string) {
    setProcessing(true);
    try {
      await api(`/api/repair-requests/${reqId}/approve/`, { method: "POST" });
      push({ title: "Additional repair approved successfully!" });
      onReload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to approve repair";
      push({ title: msg, tone: "err" });
    } finally {
      setProcessing(false);
    }
  }

  async function handleReject(reqId: number | string) {
    setProcessing(true);
    try {
      await api(`/api/repair-requests/${reqId}/reject/`, { method: "POST" });
      push({ title: "Additional repair rejected" });
      onReload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to reject repair";
      push({ title: msg, tone: "err" });
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="glass rounded-3xl p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800 pb-3">
        <div>
          <span className="text-xs font-mono font-bold text-[#ff4d2e] bg-[#ff4d2e]/10 px-2.5 py-0.5 rounded-full">
            {booking.booking_reference || booking.booking_id}
          </span>
          <h3 className="text-lg font-extrabold mt-1">
            {booking.vehicle_details ? `${booking.vehicle_details.brand} ${booking.vehicle_details.model}` : "Vehicle"}
          </h3>
          <p className="text-xs text-zinc-500">Service: {booking.service_type_details?.name || booking.serviceType}</p>
        </div>
        <span className="rounded-full bg-[#ff4d2e]/15 px-3 py-1 text-xs font-bold text-[#ff4d2e]">
          {booking.status}
        </span>
      </div>

      {/* Media Evidence Gallery */}
      {evidenceItems.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
            <Camera size={15} className="text-[#ff4d2e]" /> Photo & Video Inspection Evidence
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {evidenceItems.map((item: any) => (
              <div key={item.id} className="rounded-2xl overflow-hidden border border-zinc-200/80 bg-black dark:border-zinc-800">
                {item.media_type === "VIDEO" ? (
                  <video src={item.file_url || item.file} controls className="w-full aspect-video object-cover" />
                ) : (
                  <img src={item.file_url || item.file} alt={item.issue_title} className="w-full aspect-video object-cover" />
                )}
                <div className="p-3 bg-white dark:bg-zinc-900 text-xs space-y-1">
                  <p className="font-bold">{item.issue_title}</p>
                  {item.description && <p className="text-zinc-500">{item.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pending Repair Requests */}
      {!repairRequests.length ? (
        <p className="text-xs text-zinc-500 italic">No additional repair proposals for this booking.</p>
      ) : (
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
            Additional Repair Proposals
          </h4>
          {repairRequests.map((req: any) => (
            <div key={req.id} className="rounded-2xl border border-zinc-200/80 p-4 dark:border-zinc-800 space-y-3 bg-zinc-50/60 dark:bg-zinc-900/60">
              <div className="flex justify-between items-start">
                <div>
                  <h5 className="font-extrabold text-base">{req.issue_title}</h5>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1">{req.description}</p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-xs text-zinc-400 font-bold block uppercase">Additional Cost</span>
                  <span className="text-lg font-black text-[#ff4d2e]">
                    ₹{Number(req.estimated_cost || req.additional_cost || 0).toLocaleString("en-IN")}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-zinc-200/60 dark:border-zinc-800 text-xs">
                <div className="flex items-center gap-3">
                  <span className="text-zinc-500">
                    Mechanic: <strong>{req.mechanic_name || "Assigned Mechanic"}</strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedReqForAi(req)}
                    className="flex items-center gap-1 text-[11px] font-bold text-[#ff4d2e] hover:underline"
                  >
                    <Sparkles className="h-3 w-3" /> Check Estimate
                  </button>
                </div>

                {req.status === "PENDING" ? (
                  <div className="flex gap-2">
                    <button
                      disabled={processing}
                      onClick={() => handleReject(req.id)}
                      className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-1.5 font-bold text-red-600 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400 disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      disabled={processing}
                      onClick={() => handleApprove(req.id)}
                      className="rounded-xl bg-emerald-600 px-3.5 py-1.5 font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Approve Repair
                    </button>
                  </div>
                ) : (
                  <span className={`font-bold px-3 py-1 rounded-full ${req.status === "APPROVED" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                    {req.status}
                  </span>
                )}
              </div>
            </div>
          ))}

          {selectedReqForAi && (
            <AICostEstimatorModal
              vehicleId={booking.vehicle || booking.vehicle_details?.id}
              initialIssue={selectedReqForAi.description || selectedReqForAi.issue_title}
              onClose={() => setSelectedReqForAi(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}
