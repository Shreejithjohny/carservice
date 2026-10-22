export type Role = "customer" | "service_center_manager" | "driver" | "mechanic" | "admin";

export interface User {
  id?: string;
  _id?: string;
  name: string;
  phone: string;
  email?: string;
  role: Role;
  avatarUrl?: string;
  is_verified?: boolean;
}

export interface CarBrand {
  id: number;
  name: string;
  logo?: string;
  logo_url?: string;
  is_active: boolean;
  models_count?: number;
}

export interface CarModel {
  id: number;
  brand: number;
  brand_name?: string;
  name: string;
  body_type: string;
  is_active: boolean;
  variants_count?: number;
}

export interface CarVariant {
  id: number;
  model: number;
  model_name?: string;
  brand_name?: string;
  name: string;
  fuel_type: string;
  transmission: string;
  engine: string;
  is_active: boolean;
}

export interface Vehicle {
  id?: number;
  _id?: string;
  customer?: string;
  customer_email?: string;
  car_brand?: number;
  car_brand_details?: CarBrand;
  car_model?: number;
  car_model_details?: CarModel;
  car_variant?: number;
  car_variant_details?: CarVariant;
  brand: string;
  model: string;
  variant_name?: string;
  nickname: string;
  year: number;
  fuel_type: string;
  fuelType?: string;
  registration_number: string;
  registration?: string;
  color?: string;
  odometer_km?: number | null;
  image?: string;
  image_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ServiceType {
  id: number;
  name: string;
  description: string;
  base_price: number | string;
  estimated_duration: string;
  active: boolean;
}

export interface ServiceCenter {
  id: number;
  name: string;
  address: string;
  phone: string;
  email: string;
  latitude?: number;
  longitude?: number;
  rating?: number;
  review_count?: number;
  average_rating?: number | null;
  slot_capacity?: number;
  is_active?: boolean;
  active?: boolean;
}

export interface Booking {
  id: number | string;
  _id?: string;
  booking_reference: string;
  booking_id?: string;
  customer?: number;
  customer_name?: string;
  customer_phone?: string;
  customer_email?: string;
  vehicle?: number | string;
  vehicle_details?: Vehicle;
  vehicleId?: string;
  service_type?: number;
  service_type_details?: ServiceType;
  serviceType?: string;
  service_center?: number;
  service_center_details?: ServiceCenter;
  assigned_driver?: number | null;
  assigned_driver_details?: User | null;
  assigned_mechanic?: number | null;
  assigned_mechanic_details?: User | null;
  handover_otp?: string | null;
  handover_otp_verified?: boolean;
  delivery_otp_verified?: boolean;
  delivered_at?: string | null;
  completed_at?: string | null;
  pickup_odometer_km?: number | null;
  delivery_odometer_km?: number | null;
  plate_verified?: boolean;
  plate_detected?: string;
  has_review?: boolean;
  pickup_address?: string;
  pickup_latitude?: number | null;
  pickup_longitude?: number | null;
  address?: string;
  preferred_date?: string;
  preferred_time?: string;
  customer_notes?: string;
  problem?: string;
  estimated_cost?: number | string;
  estimatedCost?: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  pickupAt?: string;
}

export interface ConditionPhoto {
  id: number;
  stage: "PICKUP" | "DELIVERY";
  angle: string;
  file: string;
  notes: string;
  created_at: string;
}

export interface ConditionReport {
  booking: number;
  pickup_photos: ConditionPhoto[];
  delivery_photos: ConditionPhoto[];
  pickup_odometer_km: number | null;
  delivery_odometer_km: number | null;
  km_driven: number | null;
}

export interface ServiceDue {
  vehicle: number;
  registration_number: string;
  name: string;
  status: "OK" | "DUE_SOON" | "OVERDUE" | "BOOKED";
  last_service_date: string | null;
  due_date: string;
  days_left: number;
  km_left: number | null;
  odometer_km: number | null;
  reasons: string[];
}

export interface CenterAnalytics {
  scope: string;
  monthly: { month: string; label: string; bookings: number; completed: number; revenue: number }[];
  totals: { bookings: number; completed: number; cancelled: number; revenue_paid: number; outstanding: number };
  turnaround_hours: { count: number; average: number | null; median: number | null };
  repairs: {
    approved: number;
    rejected: number;
    pending: number;
    approval_rate: number | null;
    top: { title: string; count: number; average_cost: number }[];
  };
  ratings: {
    count: number;
    average: number | null;
    distribution: { stars: number; count: number }[];
    recent: { rating: number; comment: string; created_at: string }[];
  };
  status_breakdown: { status: string; count: number }[];
}

export interface InvoiceItem {
  id?: number;
  description: string;
  item_type: string;
  quantity: number;
  unit_price: number | string;
  total_price: number | string;
}

export interface Invoice {
  id: number | string;
  invoice_number: string;
  booking: number | string;
  booking_reference?: string;
  customer?: number | string;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
  vehicle?: number | string;
  vehicle_details?: Vehicle;
  service_center?: number | string;
  service_center_name?: string;
  subtotal: number | string;
  additional_repairs_total: number | string;
  labor_total: number | string;
  tax: number | string;
  discount: number | string;
  grand_total: number | string;
  payment_status: "PENDING" | "PAID" | "FAILED" | "REFUNDED" | string;
  invoice_status: "DRAFT" | "ISSUED" | "PAID" | "CANCELLED" | string;
  issued_at: string;
  created_at?: string;
  items: InvoiceItem[];
  payments?: Payment[];
}

export interface Payment {
  id: number;
  amount: number | string;
  method: "UPI" | "CARD";
  status: "SUCCESS" | "FAILED";
  provider: string;
  transaction_id: string;
  payer_reference: string;
  failure_reason: string;
  created_at: string;
}

export interface NotificationItem {
  id?: number | string;
  _id?: string;
  user?: number | string;
  booking?: number | string;
  booking_reference?: string;
  type?: string;
  notification_type?: string;
  title: string;
  message?: string;
  body?: string;
  read?: boolean;
  is_read?: boolean;
  created_at?: string;
  createdAt?: string;
  meta?: Record<string, unknown>;
}

export interface CarHealthScore {
  id?: number;
  vehicle: number | string;
  vehicle_details?: Vehicle;
  score: number;
  previous_score: number;
  service_count: number;
  recent_service_count: number;
  maintenance_compliance: string;
  critical_issue_count: number;
  warning_issue_count: number;
  resolved_issue_count: number;
  explanation: string;
  calculated_at: string;
}

export interface RepairCostEstimate {
  id?: number;
  vehicle: number | string;
  service_type?: number | string | null;
  issue_description: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  estimated_min_cost: number | string;
  estimated_max_cost: number | string;
  estimated_labor_hours: number | string;
  estimation_source: "AI" | "RULE_BASED" | "MANUAL" | string;
  explanation: string;
  created_at?: string;
}

export interface AdminStats {
  total_customers: number;
  total_vehicles: number;
  total_bookings: number;
  active_services: number;
  completed_services: number;
  service_centers: number;
  total_drivers: number;
  total_mechanics: number;
  total_revenue: number;
  outstanding_amount: number;
  repair_approvals: {
    total: number;
    approved: number;
    pending: number;
    rejected: number;
  };
}

export const TOKEN_KEY = "doorstep_token";
export const REFRESH_TOKEN_KEY = "doorstep_refresh_token";
export const USER_KEY = "doorstep_user";

