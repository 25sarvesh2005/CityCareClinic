/**
 * CityCare Clinic Web Client Constants & Enums
 * Central single source of truth for frontend domain values.
 */

export const USER_ROLES = {
  PATIENT: "patient",
  DOCTOR: "doctor",
  HOSPITAL_OWNER: "hospital_owner",
  SUPER_ADMIN: "super_admin",
} as const;

export type Role = (typeof USER_ROLES)[keyof typeof USER_ROLES];

export const APPOINTMENT_STATUSES = {
  PENDING: "pending",
  ACCEPTED: "accepted",
  REJECTED: "rejected",
  COMPLETED: "completed",
  CANCELLED: "cancelled",
} as const;

export type AppointmentStatus = (typeof APPOINTMENT_STATUSES)[keyof typeof APPOINTMENT_STATUSES];

export const SYMPTOMS = ["fever", "cough", "cold", "bodyache", "headache", "other"] as const;
export type Symptom = (typeof SYMPTOMS)[number];

export const SYMPTOM_LABELS: Record<Symptom, string> = {
  fever: "Fever",
  cough: "Cough",
  cold: "Cold",
  bodyache: "Body Ache",
  headache: "Headache",
  other: "Other",
};

export const STORAGE_KEYS = {
  TOKEN: "citycare_token",
  ROLE: "citycare_role",
  NAME: "citycare_name",
  EMAIL: "citycare_email",
} as const;

export const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";

export const CLINIC_RULES = {
  MAX_BOOKING_DAYS: 7,
  SLOT_DURATION_MINUTES: 30,
  DEFAULT_CONSULTATION_FEE: 300,
} as const;
