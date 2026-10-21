import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  seedBookings,
  seedNotifications,
  seedVehicles,
  type Booking,
  type Notification,
  type User,
  type Vehicle,
} from "./types";

interface AppState {
  user: User | null;
  vehicles: Vehicle[];
  bookings: Booking[];
  notifications: Notification[];
  chatOpen: boolean;
  estimatorPrefill: Partial<{
    vehicleId: string;
    serviceType: string;
    problem: string;
  }> | null;
}

interface AppContextValue extends AppState {
  login: (user: User) => void;
  logout: () => void;
  addVehicle: (v: Omit<Vehicle, "id">) => void;
  addBooking: (b: Omit<Booking, "id" | "createdAt" | "status">) => Booking;
  cancelBooking: (id: string) => void;
  markNotificationsRead: () => void;
  setChatOpen: (open: boolean) => void;
  setEstimatorPrefill: (p: AppState["estimatorPrefill"]) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

const defaultUser: User = {
  name: "Shreejith",
  phone: "9876543210",
  email: "shreejith@example.com",
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>(seedVehicles);
  const [bookings, setBookings] = useState<Booking[]>(seedBookings);
  const [notifications, setNotifications] = useState<Notification[]>(seedNotifications);
  const [chatOpen, setChatOpen] = useState(false);
  const [estimatorPrefill, setEstimatorPrefill] = useState<AppState["estimatorPrefill"]>(null);

  const login = useCallback((next: User) => {
    setUser(next);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setChatOpen(false);
  }, []);

  const addVehicle = useCallback((v: Omit<Vehicle, "id">) => {
    setVehicles((prev) => [...prev, { ...v, id: `v${Date.now()}` }]);
  }, []);

  const addBooking = useCallback((b: Omit<Booking, "id" | "createdAt" | "status">) => {
    const booking: Booking = {
      ...b,
      id: `BK-${Math.floor(1000 + Math.random() * 9000)}`,
      status: "Requested",
      createdAt: new Date().toISOString(),
    };
    setBookings((prev) => [booking, ...prev]);
    setNotifications((prev) => [
      {
        id: `n${Date.now()}`,
        title: "Booking confirmed",
        body: `${booking.id} is requested. We will assign a pickup driver shortly.`,
        time: "Just now",
        read: false,
      },
      ...prev,
    ]);
    return booking;
  }, []);

  const cancelBooking = useCallback((id: string) => {
    setBookings((prev) =>
      prev.map((b) => (b.id === id ? { ...b, status: "Cancelled" } : b)),
    );
  }, []);

  const markNotificationsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const value = useMemo(
    () => ({
      user,
      vehicles,
      bookings,
      notifications,
      chatOpen,
      estimatorPrefill,
      login,
      logout,
      addVehicle,
      addBooking,
      cancelBooking,
      markNotificationsRead,
      setChatOpen,
      setEstimatorPrefill,
    }),
    [
      user,
      vehicles,
      bookings,
      notifications,
      chatOpen,
      estimatorPrefill,
      login,
      logout,
      addVehicle,
      addBooking,
      cancelBooking,
      markNotificationsRead,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export { defaultUser };
