import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { defaultUser, useApp } from "../context";

export function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [phone, setPhone] = useState("9876543210");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (phone.replace(/\D/g, "").length < 10 || password.length < 4) {
      setError("Enter a valid 10-digit phone number and password.");
      return;
    }
    login({ ...defaultUser, phone });
    navigate("/app");
  }

  return (
    <div className="auth-wrap">
      <Link to="/" className="pill">← AutoCare</Link>
      <h1 className="display" style={{ fontSize: 36, margin: "14px 0 8px" }}>Welcome back</h1>
      <p style={{ color: "var(--muted)", marginBottom: 18 }}>Use the demo number to explore seeded bookings.</p>
      <form className="card grid" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="phone">Phone</label>
          <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p style={{ color: "var(--danger)", fontSize: 14 }}>{error}</p>}
        <button className="btn btn-primary" type="submit">Sign in</button>
      </form>
      <p style={{ marginTop: 14 }}>
        New here? <Link to="/register"><strong>Create an account</strong></Link>
      </p>
    </div>
  );
}
