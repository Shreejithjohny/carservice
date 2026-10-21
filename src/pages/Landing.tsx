import { Link } from "react-router-dom";
import { ArrowRight, MapPin, Sparkles, Wrench } from "lucide-react";

export function Landing() {
  return (
    <div className="hero">
      <div className="hero-copy">
        <div className="pill">Doorstep pickup & delivery</div>
        <h1 className="display">Car service without the workshop wait.</h1>
        <p style={{ color: "var(--muted)", fontSize: 18, maxWidth: 520 }}>
          Book pickup, track every stage, and get an AI repair cost estimate before you confirm.
        </p>
        <div className="btn-row" style={{ marginTop: 22 }}>
          <Link className="btn btn-primary" to="/register">
            Create account <ArrowRight size={16} />
          </Link>
          <Link className="btn btn-ghost" to="/login">
            Sign in
          </Link>
        </div>
      </div>
      <div className="hero-visual">
        <p className="pill">Live demo</p>
        <h2 className="display" style={{ fontSize: 36, margin: "16px 0" }}>Today’s booking</h2>
        <p style={{ opacity: 0.85 }}>Maruti Swift · KA 05 MJ 2148</p>
        <div style={{ marginTop: 24, display: "grid", gap: 12 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <MapPin size={18} color="#F4C95D" /> Picked up from Indiranagar
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Wrench size={18} color="#F4C95D" /> Status: In Service
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Sparkles size={18} color="#F4C95D" /> AI estimate ₹3,000 – ₹6,000
          </div>
        </div>
      </div>
    </div>
  );
}
