import { useState, FormEvent } from "react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton, Empty } from "../components/States";
import { Wrench, ClipboardCheck, Camera, PlusCircle, Sparkles } from "lucide-react";
import { AICostEstimatorModal } from "../components/AICostEstimatorModal";
import type { Booking } from "../types";

export function MechanicDashboard() {
  const { data: jobs, loading, reload } = useApi<Booking[]>("/api/mechanic/jobs/");
  const { push } = useToast();

  const [activeJob, setActiveJob] = useState<Booking | null>(null);
  const [activeSection, setActiveSection] = useState<"status" | "inspection" | "evidence" | "repair">("status");
  const [showAiModal, setShowAiModal] = useState(false);

  // Inspection Form State
  const [inspectionNotes, setInspectionNotes] = useState("");
  const [issueDescription, setIssueDescription] = useState("");
  const [severity, setSeverity] = useState("MEDIUM");
  const [estimatedCost, setEstimatedCost] = useState("0");
  const [submittingInspection, setSubmittingInspection] = useState(false);

  // Evidence Upload State
  const [evidenceTitle, setEvidenceTitle] = useState("");
  const [evidenceDesc, setEvidenceDesc] = useState("");
  const [mediaType, setMediaType] = useState<"PHOTO" | "VIDEO">("PHOTO");
  const [fileUrl, setFileUrl] = useState("");
  const [submittingEvidence, setSubmittingEvidence] = useState(false);

  // Repair Request State
  const [repairTitle, setRepairTitle] = useState("");
  const [repairDesc, setRepairDesc] = useState("");
  const [repairCost, setRepairCost] = useState("1500");
  const [submittingRepair, setSubmittingRepair] = useState(false);

  async function handleStatusUpdate(booking: Booking, newStatus: string) {
    const bId = booking.id || booking._id || booking.booking_reference;
    try {
      await api(`/api/mechanic/jobs/${bId}/status/`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      push({ title: `Service status updated to ${newStatus}` });
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to update status";
      push({ title: msg, tone: "err" });
    }
  }

  async function handleSubmitInspection(e: FormEvent) {
    e.preventDefault();
    if (!activeJob) return;
    const bId = activeJob.id || activeJob._id || activeJob.booking_reference;

    setSubmittingInspection(true);
    try {
      await api("/api/inspections/", {
        method: "POST",
        body: JSON.stringify({
          booking: bId,
          inspection_notes: inspectionNotes,
          issue_description: issueDescription,
          severity,
          estimated_additional_cost: parseFloat(estimatedCost) || 0,
        }),
      });
      push({ title: "Service inspection report submitted successfully" });
      setInspectionNotes("");
      setIssueDescription("");
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to submit inspection";
      push({ title: msg, tone: "err" });
    } finally {
      setSubmittingInspection(false);
    }
  }

  async function handleSubmitEvidence(e: FormEvent) {
    e.preventDefault();
    if (!activeJob) return;
    const bId = activeJob.id || activeJob._id || activeJob.booking_reference;

    setSubmittingEvidence(true);
    try {
      await api("/api/repair-evidence/", {
        method: "POST",
        body: JSON.stringify({
          booking: bId,
          issue_title: evidenceTitle,
          description: evidenceDesc,
          media_type: mediaType,
          file_url: fileUrl || "https://images.unsplash.com/photo-1486006920555-c77dce18193b?auto=format&fit=crop&w=600&q=80",
        }),
      });
      push({ title: "Repair evidence media uploaded successfully" });
      setEvidenceTitle("");
      setEvidenceDesc("");
      setFileUrl("");
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to upload evidence";
      push({ title: msg, tone: "err" });
    } finally {
      setSubmittingEvidence(false);
    }
  }

  async function handleSubmitRepairRequest(e: FormEvent) {
    e.preventDefault();
    if (!activeJob) return;
    const bId = activeJob.id || activeJob._id || activeJob.booking_reference;

    setSubmittingRepair(true);
    try {
      await api("/api/repair-requests/", {
        method: "POST",
        body: JSON.stringify({
          booking: bId,
          issue_title: repairTitle,
          description: repairDesc,
          additional_cost: parseFloat(repairCost) || 0,
          estimated_cost: parseFloat(repairCost) || 0,
        }),
      });
      push({ title: "Additional repair request sent for customer approval!" });
      setRepairTitle("");
      setRepairDesc("");
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to create repair request";
      push({ title: msg, tone: "err" });
    } finally {
      setSubmittingRepair(false);
    }
  }

  if (loading) return <Skeleton className="h-96" />;
  if (!jobs?.length) return <Empty title="No assigned service jobs" hint="You currently have no active service jobs assigned." />;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Wrench className="text-[#ff4d2e]" /> Mechanic Operations Bay
        </h1>
        <p className="text-sm text-zinc-500">Perform digital vehicle inspections, upload repair evidence, and request additional repair approvals.</p>
      </div>

      {/* Jobs Grid */}
      <div className="space-y-4">
        {jobs.map((b) => {
          const bId = b.id || b._id || b.booking_reference;
          const isActive = activeJob?.id === b.id;

          return (
            <div key={bId} className="glass rounded-3xl p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <div>
                  <span className="text-xs font-mono font-bold text-[#ff4d2e] bg-[#ff4d2e]/10 px-2.5 py-0.5 rounded-full">
                    {b.booking_reference || b.booking_id}
                  </span>
                  <h3 className="text-xl font-extrabold mt-1">
                    {b.vehicle_details ? `${b.vehicle_details.brand} ${b.vehicle_details.model}` : "Vehicle"}
                  </h3>
                  <p className="text-xs text-zinc-500">
                    Service: <strong>{b.service_type_details?.name || b.serviceType}</strong> · Customer: {b.customer_name || "Customer"}
                  </p>
                </div>

                <div className="text-right">
                  <span className="rounded-full bg-[#ff4d2e]/15 px-3 py-1 text-xs font-bold text-[#ff4d2e]">
                    {b.status}
                  </span>
                  <p className="text-sm font-extrabold text-emerald-600 mt-1">
                    Est: ₹{Number(b.estimated_cost || 0).toLocaleString("en-IN")}
                  </p>
                </div>
              </div>

              {b.customer_notes && (
                <div className="rounded-2xl bg-zinc-100/70 p-3 text-xs dark:bg-zinc-800/70">
                  <span className="font-bold text-zinc-500 uppercase block mb-0.5">Customer Notes / Complaints</span>
                  <p className="text-zinc-700 dark:text-zinc-300 font-medium">{b.customer_notes}</p>
                </div>
              )}

              {/* Status Action Buttons */}
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={() => handleStatusUpdate(b, "In Service")}
                  className="rounded-xl bg-purple-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-purple-700"
                >
                  Start Service
                </button>
                <button
                  onClick={() => handleStatusUpdate(b, "Inspection")}
                  className="rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
                >
                  Under Inspection
                </button>
                <button
                  onClick={() => handleStatusUpdate(b, "Repair Approval Required")}
                  className="rounded-xl bg-amber-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-amber-700"
                >
                  Request Approval
                </button>
                <button
                  onClick={() => handleStatusUpdate(b, "Ready for Delivery")}
                  className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-700"
                >
                  Mark Ready
                </button>
              </div>

              {/* Open Operations Portal Control */}
              <button
                onClick={() => {
                  if (isActive) {
                    setActiveJob(null);
                  } else {
                    setActiveJob(b);
                  }
                }}
                className="w-full flex items-center justify-center gap-1.5 rounded-2xl border border-zinc-200 py-2 text-xs font-bold hover:border-zinc-400 dark:border-zinc-700"
              >
                <ClipboardCheck size={16} />
                {isActive ? "Hide Mechanics Operations Tool" : "Open Inspection, Evidence & Repair Requests"}
              </button>

              {/* Operations Drawer Container */}
              {isActive && (
                <div className="rounded-3xl bg-zinc-50 p-5 dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 space-y-4">
                  {/* Section Switcher Tabs */}
                  <div className="flex flex-wrap gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-3">
                    <button
                      onClick={() => setActiveSection("inspection")}
                      className={`rounded-xl px-3 py-1.5 text-xs font-bold flex items-center gap-1 ${
                        activeSection === "inspection" ? "bg-[#ff4d2e] text-white" : "bg-zinc-200 dark:bg-zinc-800"
                      }`}
                    >
                      <ClipboardCheck size={14} /> Digital Inspection
                    </button>
                    <button
                      onClick={() => setActiveSection("evidence")}
                      className={`rounded-xl px-3 py-1.5 text-xs font-bold flex items-center gap-1 ${
                        activeSection === "evidence" ? "bg-[#ff4d2e] text-white" : "bg-zinc-200 dark:bg-zinc-800"
                      }`}
                    >
                      <Camera size={14} /> Photo / Video Evidence
                    </button>
                    <button
                      onClick={() => setActiveSection("repair")}
                      className={`rounded-xl px-3 py-1.5 text-xs font-bold flex items-center gap-1 ${
                        activeSection === "repair" ? "bg-[#ff4d2e] text-white" : "bg-zinc-200 dark:bg-zinc-800"
                      }`}
                    >
                      <PlusCircle size={14} /> Additional Repair Request
                    </button>
                  </div>

                  {/* Section 1: Digital Inspection */}
                  {activeSection === "inspection" && (
                    <form onSubmit={handleSubmitInspection} className="space-y-3 text-xs">
                      <h4 className="font-bold text-sm">Vehicle Inspection Report</h4>

                      <label className="block font-bold">
                        Inspection Notes / Checklist Summary
                        <textarea
                          rows={2}
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="e.g. Engine oil clean, brake pads worn out down to 2mm"
                          value={inspectionNotes}
                          onChange={(e) => setInspectionNotes(e.target.value)}
                          required
                        />
                      </label>

                      <label className="block font-bold">
                        Identified Issue Description
                        <textarea
                          rows={2}
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="Detailed mechanical fault description"
                          value={issueDescription}
                          onChange={(e) => setIssueDescription(e.target.value)}
                        />
                      </label>

                      <div className="grid grid-cols-2 gap-3">
                        <label className="block font-bold">
                          Severity Level
                          <select
                            className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs font-bold"
                            value={severity}
                            onChange={(e) => setSeverity(e.target.value)}
                          >
                            <option value="LOW">LOW — Minor Wear</option>
                            <option value="MEDIUM">MEDIUM — Moderate Issue</option>
                            <option value="HIGH">HIGH — Urgent Repair</option>
                            <option value="CRITICAL">CRITICAL — Safety Risk</option>
                          </select>
                        </label>

                        <label className="block font-bold">
                          Estimated Additional Cost (₹)
                          <input
                            type="number"
                            className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                            value={estimatedCost}
                            onChange={(e) => setEstimatedCost(e.target.value)}
                          />
                        </label>
                      </div>

                      <button
                        disabled={submittingInspection}
                        type="submit"
                        className="w-full rounded-2xl bg-[#ff4d2e] py-2.5 font-bold text-white hover:bg-[#e03e21]"
                      >
                        {submittingInspection ? "Submitting..." : "Save Digital Inspection"}
                      </button>
                    </form>
                  )}

                  {/* Section 2: Photo / Video Evidence Upload */}
                  {activeSection === "evidence" && (
                    <form onSubmit={handleSubmitEvidence} className="space-y-3 text-xs">
                      <h4 className="font-bold text-sm">Upload Photo / Video Evidence</h4>

                      <label className="block font-bold">
                        Issue Title
                        <input
                          type="text"
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="e.g. Damaged Front Brake Rotor"
                          value={evidenceTitle}
                          onChange={(e) => setEvidenceTitle(e.target.value)}
                          required
                        />
                      </label>

                      <div className="grid grid-cols-2 gap-3">
                        <label className="block font-bold">
                          Media Type
                          <select
                            className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs font-bold"
                            value={mediaType}
                            onChange={(e) => setMediaType(e.target.value as "PHOTO" | "VIDEO")}
                          >
                            <option value="PHOTO">Photo Evidence</option>
                            <option value="VIDEO">Video Evidence</option>
                          </select>
                        </label>

                        <label className="block font-bold">
                          Media Image/Video URL (or Upload)
                          <input
                            type="text"
                            className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                            placeholder="https://..."
                            value={fileUrl}
                            onChange={(e) => setFileUrl(e.target.value)}
                          />
                        </label>
                      </div>

                      <label className="block font-bold">
                        Description / Caption
                        <textarea
                          rows={2}
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="Explain what the customer is seeing in this evidence photo/video"
                          value={evidenceDesc}
                          onChange={(e) => setEvidenceDesc(e.target.value)}
                        />
                      </label>

                      <button
                        disabled={submittingEvidence}
                        type="submit"
                        className="w-full rounded-2xl bg-blue-600 py-2.5 font-bold text-white hover:bg-blue-700"
                      >
                        {submittingEvidence ? "Uploading..." : "Save Media Evidence"}
                      </button>
                    </form>
                  )}

                  {/* Section 3: Additional Repair Request */}
                  {activeSection === "repair" && (
                    <form onSubmit={handleSubmitRepairRequest} className="space-y-3 text-xs">
                      <div className="flex items-center justify-between">
                        <h4 className="font-bold text-sm">Create Additional Repair Request</h4>
                        <button
                          type="button"
                          onClick={() => setShowAiModal(true)}
                          className="flex items-center gap-1.5 rounded-xl bg-[#ff4d2e]/10 px-3 py-1.5 text-xs font-bold text-[#ff4d2e] hover:bg-[#ff4d2e]/20"
                        >
                          <Sparkles className="h-3.5 w-3.5" /> Cost Estimator
                        </button>
                      </div>

                      <label className="block font-bold">
                        Repair Title
                        <input
                          type="text"
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="e.g. Replacement of Brake Pads & Disc Resurfacing"
                          value={repairTitle}
                          onChange={(e) => setRepairTitle(e.target.value)}
                          required
                        />
                      </label>

                      <label className="block font-bold">
                        Problem Description & Recommendation
                        <textarea
                          rows={2}
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          placeholder="Describe why this repair is required and what parts are involved"
                          value={repairDesc}
                          onChange={(e) => setRepairDesc(e.target.value)}
                          required
                        />
                      </label>

                      <label className="block font-bold">
                        Estimated Additional Cost (₹)
                        <input
                          type="number"
                          className="mt-1 w-full rounded-2xl border border-zinc-200 p-2.5 dark:border-zinc-700 dark:bg-zinc-800 text-xs"
                          value={repairCost}
                          onChange={(e) => setRepairCost(e.target.value)}
                          required
                        />
                      </label>

                      <button
                        disabled={submittingRepair}
                        type="submit"
                        className="w-full rounded-2xl bg-amber-600 py-2.5 font-bold text-white hover:bg-amber-700"
                      >
                        {submittingRepair ? "Sending Request..." : "Send Request for Customer Approval"}
                      </button>
                    </form>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {showAiModal && activeJob && (
        <AICostEstimatorModal
          vehicleId={activeJob.vehicle || activeJob.vehicle_details?.id}
          initialIssue={repairDesc || repairTitle}
          onClose={() => setShowAiModal(false)}
          onApplyEstimate={(est) => {
            setRepairCost(String(est.estimated_max_cost));
            setRepairDesc(est.explanation);
            setShowAiModal(false);
          }}
        />
      )}
    </div>
  );
}
