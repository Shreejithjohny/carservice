import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../context";

export function Register() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2 || phone.replace(/\D/g, "").length < 10) {
      setError("Please enter your name and a valid phone number.");
      return;
    }
    login({ name: name.trim(), phone, email });
    navigate("/app");
  }

  return (
    <div className="auth-wrap">
      <Link to="/" className="pill">← AutoCare</Link>
      <h1 className="display" style={{ fontSize: 36, margin: "14px 0 8px" }}>Create your account</h1>
      <p style={{ color: "var(--muted)", marginBottom: 18 }}>Book pickup, track service, and chat with AI support.</p>
      <form className="card grid" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="name">Full name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="phone">Phone</label>
          <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="email">Email (optional)</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        {error && <p style={{ color: "var(--danger)", fontSize: 14 }}>{error}</p>}
        <button className="btn btn-primary" type="submit">Register</button>
      </form>
      <p style={{ marginTop: 14 }}>
        Already registered? <Link to="/login"><strong>Sign in</strong></Link>
      </p>
    </div>
  );
}
