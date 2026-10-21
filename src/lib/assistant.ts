import type { Booking, Vehicle } from "../types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  html?: boolean;
}

export const QUICK_ACTIONS = [
  { id: "track", label: "Track My Vehicle" },
  { id: "booking", label: "Booking Help" },
  { id: "service", label: "Service Information" },
  { id: "cost", label: "Cost Estimation" },
  { id: "cancel", label: "Cancel Booking" },
  { id: "support", label: "Talk to Customer Support" },
] as const;

function statusMeaning(status: string): string {
  const map: Record<string, string> = {
    Requested: "We have received your booking and will assign a pickup driver shortly.",
    "Driver Assigned": "A driver is on the way to collect your vehicle.",
    "Picked Up": "Your vehicle has been collected and is heading to the workshop.",
    "In Service": "The technician is working on the requested service. You will receive a notification once it is ready for delivery.",
    "Ready for Delivery": "Work is complete. We will dispatch a driver to return your vehicle.",
    "Out for Delivery": "Your vehicle is on the way back to your address.",
    Delivered: "Your vehicle has been returned. Thank you for choosing AutoCare.",
    Cancelled: "This booking was cancelled and will not be processed.",
  };
  return map[status] ?? "We will update you as the status changes.";
}

function activeBooking(bookings: Booking[]): Booking | undefined {
  return bookings.find((b) => b.status !== "Delivered" && b.status !== "Cancelled");
}

export function answerAssistant(
  question: string,
  ctx: { vehicles: Vehicle[]; bookings: Booking[]; userName: string },
): string {
  const q = question.toLowerCase().trim();
  const live = activeBooking(ctx.bookings);
  const vehicle = live ? ctx.vehicles.find((v) => v.id === live.vehicleId) : undefined;
  const vehicleLabel = vehicle
    ? `${vehicle.make} ${vehicle.model} (${vehicle.registration})`
    : "your vehicle";

  if ((/in service/.test(q) && /mean/.test(q)) || q.includes('what does "in service"')) {
    return `**In Service** means the vehicle is at our workshop and a technician is working on the requested job. You will be notified when it is ready for delivery.`;
  }

  if (/where.*(vehicle|car)|track|current (location|status)|service status|delivered when|when.*deliver/.test(q)) {
    if (live) {
      if (/deliver/.test(q)) {
        return live.status === "Ready for Delivery" || live.status === "Out for Delivery"
          ? `Booking **${live.id}**: ${vehicleLabel} is **${live.status}**. ${statusMeaning(live.status)}`
          : `Booking **${live.id}**: ${vehicleLabel} is currently **${live.status}**. Delivery is scheduled after the technician completes the job. You will get a notification when it is out for delivery.`;
      }
      return `Your vehicle is currently marked as **${live.status}**. ${statusMeaning(live.status)}`;
    }
    return "You do not have an active booking right now. Open **Track Service** after you book a pickup, or tap **Book Service** to schedule one.";
  }

  if (/book|schedule|pickup|how do i book/.test(q)) {
    return `To book a service:\n1. Add or select a vehicle under **My Vehicles**.\n2. Open **Book Service** and choose a service type, date, and pickup slot.\n3. Confirm your address and submit.\nA driver will be assigned for doorstep pickup. You can also start from an **AI Cost Estimate** using **Book This Service**.`;
  }

  if (/cancel/.test(q)) {
    if (live && ["Requested", "Driver Assigned"].includes(live.status)) {
      return `Booking **${live.id}** is **${live.status}**, so it can still be cancelled from **Track Service**. Once the vehicle is picked up, cancellation needs customer support.`;
    }
    if (live) {
      return `Booking **${live.id}** is already **${live.status}**. Pickup or workshop work has started, so please use **Talk to Customer Support** to request a cancellation.`;
    }
    return "You can cancel a booking from **Track Service** before pickup. After pickup, contact customer support so we can check workshop status.";
  }

  if (/approv|additional work|extra work|job card/.test(q)) {
    return "If the technician finds extra work, you will get a notification with the extra items and cost. Open **Track Service** and tap **Approve additional work**. Work continues only after you approve.";
  }

  if (/cost|estimate|how much|price|₹|rs\b/.test(q)) {
    if (live) {
      return `For booking **${live.id}** (${vehicleLabel}), the current estimate is **${live.estimatedCost}**. For a new issue, use **AI Cost Estimator** — it is an approximate AI-generated range and the final cost may vary after inspection.`;
    }
    return "Use **AI Cost Estimator**: select the vehicle, service type, and describe the problem (for example, brake noise and vibration). You will get a possible issue, recommended service, cost range, and time. It is approximate until we inspect the car.";
  }

  if (/support|human|agent|call| helpline|phone/.test(q)) {
    return "You can reach AutoCare support at **1800-22-8080** (8 AM – 10 PM) or email **help@autocare.example**. Share your booking ID so we can help faster.";
  }

  if (/hello|hi\b|hey/.test(q)) {
    return `Hello${ctx.userName ? `, ${ctx.userName.split(" ")[0]}` : ""}! 👋 I can help with tracking, booking, estimates, and support. Try a quick action below.`;
  }

  return "I can help with vehicle tracking, booking steps, service status meanings, cancellations, extra-work approvals, and cost estimates. Try a quick action, or ask something like “Where is my vehicle?”";
}

export function replyForQuickAction(
  id: string,
  ctx: { vehicles: Vehicle[]; bookings: Booking[]; userName: string },
): string {
  const map: Record<string, string> = {
    track: "Where is my vehicle?",
    booking: "How do I book a service?",
    service: 'What does "In Service" mean?',
    cost: "How much will my repair cost?",
    cancel: "How do I cancel my booking?",
    support: "I want to talk to customer support",
  };
  return answerAssistant(map[id] ?? id, ctx);
}
