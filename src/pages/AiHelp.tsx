import { ChatTranscript } from "../components/AskAI";

export function AiHelp() {
  return (
    <div className="grid">
      <p style={{ color: "var(--muted)", maxWidth: 640 }}>
        Instant answers on tracking, booking, estimates, and support. For logged-in customers, replies use your current booking.
        You can also tap the floating <strong>Ask AI</strong> button on any customer page.
      </p>
      <ChatTranscript embedded />
    </div>
  );
}
