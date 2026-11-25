export type AppointmentStatus = "booked" | "cancelled";
export type SlotStatus = "available" | "booked";

export interface Health {
  status: "ok";
  service: string;
  mode: "demo" | string;
}

export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  qualification: string;
  experience_years: number;
  consultation_fee: number;
  description: string;
}

export interface Slot {
  id: number;
  doctor_id: number;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: SlotStatus;
  doctor: Doctor;
}

export interface Appointment {
  id: number;
  doctor_id: number;
  slot_id: number;
  patient_name: string | null;
  phone_number: string;
  appointment_date: string;
  start_time: string;
  status: AppointmentStatus;
  created_at: string;
  doctor: Doctor;
}

export interface DashboardData {
  health: Health;
  doctors: Doctor[];
  slots: Slot[];
  appointments: Appointment[];
  source: "live" | "mock";
  notice?: string;
}
