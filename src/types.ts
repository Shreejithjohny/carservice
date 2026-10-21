export type ServiceType =
  | "Periodic Service"
  | "Repair"
  | "Brake Service"
  | "AC Service"
  | "Battery Replacement"
  | "Tyre Service"
  | "Denting & Painting"
  | "Engine Diagnostic"
  | "General Inspection";

export type BookingStatus =
  | "Requested"
  | "Driver Assigned"
  | "Picked Up"
  | "In Service"
  | "Ready for Delivery"
  | "Out for Delivery"
  | "Delivered"
  | "Cancelled";

export interface Vehicle {
  id: string;
  nickname: string;
  make: string;
  model: string;
  year: number;
  registration: string;
  fuel: "Petrol" | "Diesel" | "CNG" | "Electric" | "Hybrid";
  color: string;
}

export interface Booking {
  id: string;
  vehicleId: string;
  serviceType: ServiceType;
  problem: string;
  pickupDate: string;
  pickupSlot: string;
  address: string;
  status: BookingStatus;
  estimatedCost: string;
  createdAt: string;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  time: string;
  read: boolean;
}

export interface User {
  name: string;
  phone: string;
  email: string;
}

export interface CostEstimate {
  possibleIssue: string;
  recommendedService: string;
  costMin: number;
  costMax: number;
  timeMinHours: number;
  timeMaxHours: number;
  confidence: "High" | "Medium" | "Low";
}

export const SERVICE_TYPES: ServiceType[] = [
  "Periodic Service",
  "Repair",
  "Brake Service",
  "AC Service",
  "Battery Replacement",
  "Tyre Service",
  "Denting & Painting",
  "Engine Diagnostic",
  "General Inspection",
];

export const MAKES_MODELS: Record<string, string[]> = {
  Maruti: ["Swift", "Baleno", "Dzire", "Brezza", "WagonR", "Alto", "Ertiga"],
  Hyundai: ["i20", "Creta", "Venue", "Verna", "Grand i10 Nios"],
  Honda: ["City", "Amaze", "Elevate", "Jazz"],
  Tata: ["Nexon", "Punch", "Harrier", "Safari", "Altroz"],
  Toyota: ["Innova Crysta", "Fortuner", "Glanza", "Urban Cruiser Hyryder"],
  Kia: ["Seltos", "Sonet", "Carens", "Carnival"],
  Mahindra: ["XUV700", "Thar", "Scorpio-N", "XUV 3XO"],
  Skoda: ["Kushaq", "Slavia", "Kodiaq"],
};

export const seedVehicles: Vehicle[] = [
  {
    id: "v1",
    nickname: "Family Swift",
    make: "Maruti",
    model: "Swift",
    year: 2019,
    registration: "KA 05 MJ 2148",
    fuel: "Petrol",
    color: "Pearl White",
  },
  {
    id: "v2",
    nickname: "Office Creta",
    make: "Hyundai",
    model: "Creta",
    year: 2022,
    registration: "KA 03 AB 9021",
    fuel: "Diesel",
    color: "Phantom Black",
  },
];

export const seedBookings: Booking[] = [
  {
    id: "BK-4821",
    vehicleId: "v1",
    serviceType: "Brake Service",
    problem: "Strange noise from brakes and vibration while braking.",
    pickupDate: "2026-08-27",
    pickupSlot: "10:00 AM – 12:00 PM",
    address: "12, 4th Cross, Indiranagar, Bengaluru",
    status: "In Service",
    estimatedCost: "₹3,000 – ₹6,000",
    createdAt: "2026-08-26T09:20:00",
  },
  {
    id: "BK-3902",
    vehicleId: "v2",
    serviceType: "Periodic Service",
    problem: "Regular 10,000 km service.",
    pickupDate: "2026-08-12",
    pickupSlot: "8:00 AM – 10:00 AM",
    address: "12, 4th Cross, Indiranagar, Bengaluru",
    status: "Delivered",
    estimatedCost: "₹4,200",
    createdAt: "2026-08-10T14:00:00",
  },
];

export const seedNotifications: Notification[] = [
  {
    id: "n1",
    title: "Vehicle in service",
    body: "Your Maruti Swift (KA 05 MJ 2148) is currently In Service.",
    time: "Today, 2:14 PM",
    read: false,
  },
  {
    id: "n2",
    title: "Pickup completed",
    body: "Driver Ravi picked up your vehicle from Indiranagar.",
    time: "Today, 10:42 AM",
    read: false,
  },
  {
    id: "n3",
    title: "Service completed",
    body: "Periodic service for Hyundai Creta was completed and delivered.",
    time: "12 Aug, 6:05 PM",
    read: true,
  },
];
