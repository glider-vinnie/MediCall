import type { Appointment, DashboardData, Doctor, Slot } from "../types/api";

const futureDate = (offset: number) => {
  const day = new Date();
  day.setDate(day.getDate() + offset);
  return day.toISOString().slice(0, 10);
};

const doctors: Doctor[] = [
  { id: 1, name: "Dr. Ananya Mehta", specialty: "Cardiologist", qualification: "MBBS, MD, DM Cardiology", experience_years: 14, consultation_fee: 1100, description: "Preventive and interventional cardiac care." },
  { id: 2, name: "Dr. Rohan Iyer", specialty: "Dermatologist", qualification: "MBBS, MD Dermatology", experience_years: 10, consultation_fee: 850, description: "Skin, hair, and allergy-focused consultations." },
  { id: 3, name: "Dr. Kavya Nair", specialty: "General Physician", qualification: "MBBS, MD Internal Medicine", experience_years: 12, consultation_fee: 700, description: "Comprehensive adult primary care." },
  { id: 4, name: "Dr. Arjun Malhotra", specialty: "Neurologist", qualification: "MBBS, MD, DM Neurology", experience_years: 16, consultation_fee: 1300, description: "Headache, epilepsy, and neurological care." },
  { id: 5, name: "Dr. Neel Shah", specialty: "Orthopaedic", qualification: "MBBS, MS Orthopaedics", experience_years: 11, consultation_fee: 950, description: "Bone, joint, sports, and mobility care." },
  { id: 6, name: "Dr. Priya Menon", specialty: "Paediatrician", qualification: "MBBS, MD Paediatrics", experience_years: 13, consultation_fee: 800, description: "Compassionate child and adolescent care." },
];

const slots: Slot[] = doctors.flatMap((doctor, index) => [
  { id: index * 2 + 1, doctor_id: doctor.id, appointment_date: futureDate(1), start_time: "09:00:00", end_time: "09:30:00", status: "available", doctor },
  { id: index * 2 + 2, doctor_id: doctor.id, appointment_date: futureDate(1), start_time: "10:00:00", end_time: "10:30:00", status: index % 2 === 0 ? "booked" : "available", doctor },
]);

const appointments: Appointment[] = [
  { id: 1, doctor_id: 1, slot_id: 2, patient_name: "Asha Rao", phone_number: "*********3210", appointment_date: futureDate(1), start_time: "10:00:00", status: "booked", created_at: new Date().toISOString(), doctor: doctors[0] },
  { id: 2, doctor_id: 3, slot_id: 6, patient_name: "Vikram Singh", phone_number: "*********9087", appointment_date: futureDate(2), start_time: "09:00:00", status: "cancelled", created_at: new Date().toISOString(), doctor: doctors[2] },
];

export const mockDashboardData: DashboardData = {
  health: { status: "ok", service: "medicall-demo", mode: "demo" },
  doctors,
  slots,
  appointments,
  source: "mock",
  notice: "Backend unavailable — showing labelled demo data only.",
};
