/**
 * API client layer for CityCare Clinic FastAPI backend.
 * Base URL defaults to http://localhost:8000/api/v1
 */

export const API_BASE_URL =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://localhost:8000/api/v1";

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

export type Role = "patient" | "doctor" | "hospital_owner" | "super_admin";

export type DoctorInfo = {
  doctor_name: string;
  specialization: string;
  clinic_name: string;
  consultation_fee: string;
  morning_hours: string;
  evening_hours: string;
  slot_duration_minutes: number;
  total_slots_per_day: number;
  max_patients_per_slot?: number;
  languages_spoken: string[];
  address: string;
  phone: string;
};

export type FreeSlotsResponse = {
  date: string;
  available_slots: string[];
  total_available: number;
};

export type Appointment = {
  appointment_id: string;
  patient_name: string;
  date: string;
  slot: string;
  reason: string;
  temperature: number;
  symptoms: Symptom[];
  status?: string;
  prescription_id?: string;
  pdf_url?: string;
  is_cancelled: boolean;
  cancellation_reason?: string;
  created_at: string;
  message?: string;
};

export type DoctorScheduleEntry = {
  appointment_id: string;
  slot: string;
  patient_name: string;
  reason: string;
  temperature: number;
  symptoms: Symptom[];
  status?: string;
  prescription_id?: string;
  pdf_url?: string;
  is_cancelled: boolean;
  cancellation_reason?: string;
};

export type DoctorScheduleResponse = {
  date: string;
  is_unavailable?: boolean;
  total_appointments: number;
  schedule: DoctorScheduleEntry[];
};

export type DoctorUnavailabilityResponse = {
  date: string;
  is_unavailable: boolean;
  unavailable_dates: string[];
  cancelled_appointments_count: number;
  message: string;
};

export type DoctorStatsResponse = {
  total_registered_patients: number;
  todays_visit_count: number;
  upcoming_visit_count: number;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  role: Role;
  name: string;
  email?: string;
};

export type UserSignupResponse = {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  message: string;
};

export type Hospital = {
  hospital_id: string;
  name: string;
  address: string;
  city: string;
  contact_number: string;
  owner_id: string;
  is_active: boolean;
  is_approved: boolean;
  created_at: string;
};

export type DoctorProfile = {
  profile_id: string;
  user_id: string;
  hospital_id?: string;
  name?: string;
  email?: string;
  specialization: string;
  consultation_fee: string;
  clinic_hours: Record<string, string>;
  languages_spoken: string[];
  unavailable_dates?: string[];
  is_active: boolean;
  created_at: string;
};

export type PlatformStats = {
  total_hospitals: number;
  active_hospitals: number;
  approved_hospitals: number;
  total_doctors: number;
  total_patients: number;
  total_appointments: number;
  active_appointments: number;
};

export type HospitalStats = {
  hospital_id: string;
  hospital_name: string;
  total_doctors: number;
  active_doctors: number;
  total_appointments: number;
  todays_appointments: number;
  upcoming_appointments: number;
  is_active: boolean;
  is_approved: boolean;
};

export class ApiError extends Error {
  status: number;
  details?: unknown;
  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

const TOKEN_KEY = "citycare_token";

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

/** Maps backend status codes to friendly messages. */
function messageForStatus(
  status: number,
  body: { detail?: string | { msg?: string }[]; message?: string } | null | undefined,
) {
  if (body?.detail) {
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return body.detail[0].msg;
    }
  }
  if (body?.message) return body.message;

  switch (status) {
    case 401:
      return "Invalid email address or password.";
    case 403:
      return "Access denied. Restricted area.";
    case 409:
      return "That slot or resource is already taken/exists.";
    case 422:
      return "Please check the highlighted fields.";
    case 404:
      return "Resource not found.";
    default:
      return status >= 500 ? "Server error. Please try again." : "Request failed.";
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = auth ? getToken() : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ApiError(0, "Network error — is the backend running on port 8000?");
  }

  const text = await res.text();
  const data = text ? safeJson(text) : null;

  if (!res.ok) {
    throw new ApiError(res.status, messageForStatus(res.status, data), data);
  }
  return data as T;
}

function safeJson(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export const api = {
  /** POST /signup */
  signup: (input: { name: string; email: string; password: string }) =>
    request<UserSignupResponse>("/signup", { method: "POST", body: input, auth: false }),

  /** POST /login */
  login: (input: { email: string; password: string }) =>
    request<TokenResponse>("/login", { method: "POST", body: input, auth: false }),

  /** GET /doctor-info */
  getDoctorInfo: () => request<DoctorInfo>("/doctor-info", { auth: false }),

  /** GET /free-slots?date=YYYY-MM-DD */
  getFreeSlots: (date: string) =>
    request<FreeSlotsResponse>(`/free-slots?date=${encodeURIComponent(date)}`, { auth: false }),

  /** POST /book */
  bookAppointment: (input: {
    hospital_id: string;
    doctor_id: string;
    date: string;
    slot: string;
    reason: string;
    temperature: number;
    symptoms: Symptom[];
  }) => request<Appointment>("/book", { method: "POST", body: input }),

  /** GET /my-appointments */
  myAppointments: () => request<Appointment[]>("/my-appointments"),

  /** DELETE /cancel/:appointment_id */
  cancelAppointment: (appointment_id: string) =>
    request<{ appointment_id: string; message: string }>(`/cancel/${appointment_id}`, {
      method: "DELETE",
    }),

  /** GET /doctor/schedule?date=YYYY-MM-DD */
  doctorSchedule: (date: string) =>
    request<DoctorScheduleResponse>(`/doctor/schedule?date=${encodeURIComponent(date)}`),

  /** GET /doctor/unavailability */
  getDoctorUnavailability: () => request<DoctorUnavailabilityResponse>("/doctor/unavailability"),

  /** POST /doctor/unavailability */
  toggleDoctorUnavailability: (input: { date: string; is_unavailable: boolean }) =>
    request<DoctorUnavailabilityResponse>("/doctor/unavailability", {
      method: "POST",
      body: input,
    }),

  /** GET /doctor/stats */
  doctorStats: () => request<DoctorStatsResponse>("/doctor/stats"),

  // ─── Super Admin Endpoints ────────────────────────────────────────────────
  getPlatformStats: () => request<PlatformStats>("/admin/stats"),

  listHospitals: () => request<Hospital[]>("/admin/hospitals"),

  createHospital: (input: {
    name: string;
    address: string;
    city: string;
    contact_number: string;
  }) => request<Hospital>("/admin/hospitals", { method: "POST", body: input }),

  createHospitalOwner: (
    hospital_id: string,
    input: { name: string; email: string; password: string },
  ) => request<unknown>(`/admin/hospitals/${hospital_id}/owner`, { method: "POST", body: input }),

  setHospitalStatus: (
    hospital_id: string,
    statusFlags: { is_active?: boolean; is_approved?: boolean },
  ) =>
    request<Hospital>(`/admin/hospitals/${hospital_id}/status`, {
      method: "PATCH",
      body: statusFlags,
    }),

  getHospitalStatsAdmin: (hospital_id: string) =>
    request<HospitalStats>(`/admin/hospitals/${hospital_id}/stats`),

  // ─── Hospital Owner Endpoints ─────────────────────────────────────────────
  getHospitalStatsOwner: () => request<HospitalStats>("/hospital/stats"),

  listOwnerDoctors: () => request<DoctorProfile[]>("/hospital/doctors"),

  createDoctor: (input: {
    name: string;
    email: string;
    password: string;
    specialization: string;
    consultation_fee: string;
  }) => request<DoctorProfile>("/hospital/doctors", { method: "POST", body: input }),

  setDoctorStatus: (profile_id: string, statusFlags: { is_active: boolean }) =>
    request<DoctorProfile>(`/hospital/doctors/${profile_id}/status`, {
      method: "PATCH",
      body: statusFlags,
    }),

  // ─── Patient Multi-Tenant Discovery Endpoints ─────────────────────────────
  browseHospitals: (city?: string) =>
    request<Hospital[]>(`/hospitals${city ? `?city=${encodeURIComponent(city)}` : ""}`, {
      auth: false,
    }),

  getHospitalDoctors: (hospital_id: string) =>
    request<DoctorProfile[]>(`/hospitals/${hospital_id}/doctors`, { auth: false }),

  getDoctorFreeSlots: (hospital_id: string, doctor_id: string, date: string) =>
    request<{
      hospital_id: string;
      doctor_id: string;
      date: string;
      available_slots: string[];
      total_available: number;
      is_unavailable?: boolean;
    }>(
      `/hospitals/${hospital_id}/doctors/${doctor_id}/free-slots?date=${encodeURIComponent(date)}`,
      { auth: false },
    ),

  // ─── Phase 6 Schedule Chatbot Endpoints ──────────────────────────────
  sendScheduleChatMessage: (input: { session_id?: string; message: string }) =>
    request<{
      session_id: string;
      response: string;
      messages: {
        message_id: string;
        session_id: string;
        role: "user" | "assistant" | "system" | "tool";
        content: string;
        created_at: string;
      }[];
    }>("/chat/schedule", { method: "POST", body: input }),

  getChatSessions: () =>
    request<
      {
        session_id: string;
        user_id: string;
        hospital_id: string;
        title: string;
        created_at: string;
      }[]
    >("/chat/schedule/sessions"),

  getChatMessages: (session_id: string) =>
    request<
      {
        message_id: string;
        session_id: string;
        role: "user" | "assistant" | "system" | "tool";
        content: string;
        created_at: string;
      }[]
    >(`/chat/schedule/sessions/${encodeURIComponent(session_id)}`),

  // ─── Prescription Endpoints ──────────────────────────────────────────
  acceptAppointment: (appointment_id: string) =>
    request<{ appointment_id: string; status: string; message: string }>(
      `/doctor/appointments/${appointment_id}/accept`,
      { method: "PATCH" },
    ),

  rejectAppointment: (appointment_id: string, reason?: string) =>
    request<{ appointment_id: string; status: string; message: string }>(
      `/doctor/appointments/${appointment_id}/reject`,
      { method: "PATCH", body: { reason } },
    ),

  createPrescription: (payload: {
    appointment_id: string;
    diagnosis: string;
    medications: {
      medicine_name: string;
      dosage: string;
      frequency: string;
      duration: string;
      instructions?: string;
    }[];
    notes?: string;
    follow_up_date?: string;
  }) => request<Prescription>("/doctor/prescriptions", { method: "POST", body: payload }),

  myPrescriptions: () => request<Prescription[]>("/patient/prescriptions"),

  getPrescriptionDetails: (prescription_id: string) =>
    request<Prescription>(`/patient/prescriptions/${prescription_id}`),

  getPrescriptionPdfUrl: (prescription_id: string) => {
    const backendOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
    return `${backendOrigin}/api/v1/patient/prescriptions/${prescription_id}/pdf-file`;
  },

  getPdfUrl: (pdf_url?: string | null, prescription_id?: string | null) => {
    const backendOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
    if (pdf_url) {
      if (pdf_url.startsWith("http://") || pdf_url.startsWith("https://")) {
        return pdf_url;
      }
      if (pdf_url.startsWith("/")) {
        return `${backendOrigin}${pdf_url}`;
      }
    }
    if (prescription_id) {
      return `${backendOrigin}/api/v1/patient/prescriptions/${prescription_id}/pdf-file`;
    }
    return "#";
  },
};

export type MedicationItem = {
  medicine_name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string;
};

export type Prescription = {
  prescription_id: string;
  hospital_id: string;
  doctor_id: string;
  doctor_name: string;
  patient_id: string;
  patient_name: string;
  appointment_id: string;
  date: string;
  diagnosis: string;
  medications: MedicationItem[];
  notes?: string;
  follow_up_date?: string;
  pdf_url: string;
  created_at: string;
};

