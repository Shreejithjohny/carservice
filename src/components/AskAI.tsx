import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bot, Send, X } from "lucide-react";
import { useApp } from "../context";
import { answerAssistant, QUICK_ACTIONS, replyForQuickAction, type ChatMessage } from "../lib/assistant";

function renderText(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p,
  );
}

export function ChatTranscript({
  embedded,
  onClose,
}: {
  embedded?: boolean;
  onClose?: () => void;
}) {
  const { user, vehicles, bookings, setChatOpen } = useApp();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "w",
      role: "assistant",
      text: "Hello! 👋 How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const ctx = { vehicles, bookings, userName: user?.name ?? "" };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function push(q: string, a: string) {
    setMessages((m) => [
      ...m,
      { id: crypto.randomUUID(), role: "user", text: q },
      { id: crypto.randomUUID(), role: "assistant", text: a },
    ]);
  }

  function ask(text: string) {
    const q = text.trim();
    if (!q) return;
    push(q, answerAssistant(q, ctx));
    setInput("");
  }

  function quick(id: string, label: string) {
    if (id === "cost") {
      push(label, replyForQuickAction(id, ctx));
      setTimeout(() => {
        setChatOpen(false);
        navigate("/app/estimate");
      }, 650);
      return;
    }
    push(label, replyForQuickAction(id, ctx));
  }

  return (
    <div className={embedded ? "card" : "chat-panel"} style={embedded ? { padding: 0, overflow: "hidden", display: "flex", flexDirection: "column", minHeight: 560 } : undefined}>
      <div className="chat-head">
        <div>
          <strong>AutoCare Assistant</strong>
          <div style={{ fontSize: 12, opacity: 0.75 }}>AI Help & Customer Care</div>
        </div>
        {!embedded && (
          <button className="btn" style={{ background: "transparent", color: "#fff" }} onClick={onClose} aria-label="Close chat">
            <X size={18} />
          </button>
        )}
      </div>
      <div className="chat-body">
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role}`}>
            {renderText(m.text)}
          </div>
        ))}
        {messages.length <= 2 && (
          <div className="quick-grid">
            {QUICK_ACTIONS.map((a) => (
              <button key={a.id} className="chip" onClick={() => quick(a.id, a.label)}>
                {a.label}
              </button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about tracking, booking, costs…"
        />
        <button className="btn btn-primary" type="submit" aria-label="Send">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

export function AskAI() {
  const { chatOpen, setChatOpen } = useApp();
  const location = useLocation();
  if (location.pathname === "/app/help") return null;
  return (
    <>
      {chatOpen && <ChatTranscript onClose={() => setChatOpen(false)} />}
      <button className="fab" onClick={() => setChatOpen(!chatOpen)}>
        <Bot size={18} /> 💬 Ask AI
      </button>
    </>
  );
}
