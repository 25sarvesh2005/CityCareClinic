# Aurora Design Suite

🎨 Design System

Dark mode first — #0a0a0f background, indigo + cyan accent palette

Glassmorphism cards with backdrop-filter: blur(16px) and subtle glow shadows

Inter font from Google Fonts

Micro-animations: hover lift, button press, fade-in on mount

📄 4 Pages Built to Your Backend

PageRouteAuthLanding (hero + doctor info card)/PublicLogin / Signup/login, /signupPublicPatient Dashboard/dashboardrole: patientDoctor Dashboard/doctorrole: doctor

🔌 All 9 API Endpoints Mapped

Every endpoint has exact request bodies, response shapes, and error handling instructions (409 slot clash, 401 wrong creds, 422 validation, 403 role guard, etc.)

⚡ UX Details

Slot picker grouped into 🌅 Morning / 🌆 Evening

Symptom multi-select toggles (exactly your 6 enums)

Temperature input bounded to 95.0–110.0°F

Cancel with confirmation modal (soft delete awareness)

Custom toast system (not alert())

Skeleton loaders on all fetch states

Route guards based on role from localStorage
create this i have shared an image i want similar implementation

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/dbbfc72e-eb0f-414c-9b00-4a37d941472a).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
