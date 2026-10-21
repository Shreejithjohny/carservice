import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { VerifyOtp } from "./pages/VerifyOtp";
import { Dashboard } from "./pages/Dashboard";
import { Vehicles } from "./pages/Vehicles";
import { Book } from "./pages/Book";
import { History, Track } from "./pages/Track";
import { Estimate } from "./pages/Estimate";
import { Health } from "./pages/Health";
import { Approvals } from "./pages/Approvals";
import { OtpHandover } from "./pages/Otp";
import { Notifications } from "./pages/Notifications";
import { Offers, Wallet } from "./pages/Wallet";
import { AdminBookings, AdminDiscounts, AdminHome, AdminVideo } from "./pages/Admin";
import { AdminCatalog } from "./pages/AdminCatalog";
import { ServiceCenterDashboard } from "./pages/ServiceCenterDashboard";
import { DriverDashboard } from "./pages/DriverDashboard";
import { MechanicDashboard } from "./pages/MechanicDashboard";
import { Invoices } from "./pages/Invoices";
import { Guard } from "./layouts/Guard";
import { AppShell } from "./layouts/AppShell";

function Fade({ children }: { children: ReactNode }) {
  const loc = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-otp" element={<VerifyOtp />} />

      {/* Protected Customer Routes */}
      <Route element={<Guard roles={["customer", "CUSTOMER"]} />}>
        <Route path="/app" element={<AppShell variant="customer" />}>
          <Route index element={<Fade><Dashboard /></Fade>} />
          <Route path="vehicles" element={<Fade><Vehicles /></Fade>} />
          <Route path="book" element={<Fade><Book /></Fade>} />
          <Route path="track" element={<Fade><Track /></Fade>} />
          <Route path="history" element={<Fade><History /></Fade>} />
          <Route path="estimate" element={<Fade><Estimate /></Fade>} />
          <Route path="health" element={<Fade><Health /></Fade>} />
          <Route path="approvals" element={<Fade><Approvals /></Fade>} />
          <Route path="otp" element={<Fade><OtpHandover /></Fade>} />
          <Route path="notifications" element={<Fade><Notifications /></Fade>} />
          <Route path="invoices" element={<Fade><Invoices /></Fade>} />
          <Route path="wallet" element={<Fade><Wallet /></Fade>} />
          <Route path="offers" element={<Fade><Offers /></Fade>} />
        </Route>
      </Route>

      {/* Protected Service Center Manager Routes */}
      <Route element={<Guard roles={["admin", "ADMIN", "SERVICE_CENTER", "SERVICE_CENTER_MANAGER", "manager"]} />}>
        <Route path="/service-center" element={<AppShell variant="admin" />}>
          <Route index element={<Fade><ServiceCenterDashboard /></Fade>} />
          <Route path="bookings" element={<Fade><ServiceCenterDashboard /></Fade>} />
          <Route path="invoices" element={<Fade><Invoices /></Fade>} />
        </Route>
      </Route>

      {/* Protected Admin Routes */}
      <Route element={<Guard roles={["admin", "ADMIN"]} />}>
        <Route path="/admin" element={<AppShell variant="admin" />}>
          <Route index element={<Fade><AdminHome /></Fade>} />
          <Route path="catalog" element={<Fade><AdminCatalog /></Fade>} />
          <Route path="bookings" element={<Fade><AdminBookings /></Fade>} />
          <Route path="invoices" element={<Fade><Invoices /></Fade>} />
          <Route path="video" element={<Fade><AdminVideo /></Fade>} />
          <Route path="discounts" element={<Fade><AdminDiscounts /></Fade>} />
        </Route>
      </Route>

      {/* Protected Valet/Driver Routes */}
      <Route element={<Guard roles={["driver", "DRIVER", "VALET", "EMPLOYEE"]} />}>
        <Route path="/driver" element={<AppShell variant="driver" />}>
          <Route index element={<Fade><DriverDashboard /></Fade>} />
        </Route>
      </Route>

      {/* Protected Mechanic Routes */}
      <Route element={<Guard roles={["mechanic", "MECHANIC", "admin", "ADMIN"]} />}>
        <Route path="/mechanic" element={<AppShell variant="admin" />}>
          <Route index element={<Fade><MechanicDashboard /></Fade>} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
