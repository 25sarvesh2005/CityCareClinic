# CityCare Clinic — Web Client

A modern, responsive healthcare consultation and clinic management web application built with React 19, TypeScript, TanStack Start, and TailwindCSS.

---

## Features

- **Patient Portal**:
  - Doctor discovery, profiles, consultation fee details, and clinic hours.
  - Interactive appointment booking with real-time slot availability.
  - Multi-select symptom logging and dual-scale temperature input (°F / °C) with automated range validation.
  - AI-assisted schedule query assistant and prescription assistant.
  - Telegram integration with one-time verification code generation.
- **Doctor Portal**:
  - Daily appointment roster view with patient symptom details and vital signs.
  - Appointment acceptance, rejection, and clinical status workflow.
  - Digital prescription generation and consultation history.
- **Hospital Owner & Super Admin Dashboards**:
  - Multi-tenant clinic management and doctor staff rostering.
  - Platform-wide clinic onboarding and owner administration.

---

## Technology Stack

- **Framework**: [TanStack Start](https://tanstack.com/start) with [TanStack Router](https://tanstack.com/router)
- **UI Library**: React 19, [Radix UI](https://www.radix-ui.com/) primitives
- **Styling**: TailwindCSS, CSS Variables theme system
- **State & Data Fetching**: TanStack Query (React Query)
- **Icons**: Lucide React

---

## Getting Started

### Prerequisites

- Node.js 20+ (LTS recommended)
- npm 10+
- CityCare Clinic FastAPI backend running at `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm ci
```

### Development Server

```bash
# Start local development server on http://localhost:5173
npm run dev
```

### Production Build

```bash
# Run TypeScript type check
npx tsc --noEmit

# Run ESLint validation
npm run lint

# Build production bundle
npm run build
```

---

## Environment Configuration

Create a `.env` file in the frontend root or rely on default development fallbacks:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```
