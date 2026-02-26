# Swasthya Frontend

This folder contains a basic Next.js frontend for the Swasthya healthcare system.

## Getting Started

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Run development server:
   ```bash
   npm run dev
   ```

### Notes
- This frontend proxies API requests to the backend running at the same origin (3003).
- Add a `next.config.js` rewrites section if you need to redirect `/api/*` to the backend.
