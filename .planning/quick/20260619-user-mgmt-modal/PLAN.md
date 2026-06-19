# Quick Task: User Management Modal

## Goal
Add a settings gear icon to the nav and a modal for user management — admin sees "Crear usuario" + "Cambiar mi contraseña"; non-admin sees only "Cambiar mi contraseña".

## Context
- Backend endpoints already exist: POST /auth/users (admin only), POST /auth/change-password, GET /auth/me
- Admin email: santillan@talentagency.mx (hardcoded in frontend for role-based UI)
- Design system: dark theme, CSS variables (--bg, --text, --accent), .btn / .btn.primary, showToast()
- No existing modal pattern — needs new CSS + HTML

## Tasks

### T1: Add modal HTML to index.html
- Settings gear button in `.nav-right` (right of sync pill)
- Modal overlay (`#settings-modal`) with:
  - Header with title + close button
  - Section "Crear usuario" (hidden by default, shown only for admin): email + password + confirm password
  - Divider between sections (only shown for admin)
  - Section "Cambiar mi contraseña": current password + new password + confirm new password
- Each section has its own submit button

### T2: Add modal + button CSS to styles.css
- `.nav-settings-btn` — icon button, styled to match nav
- `.modal-overlay` — fixed full-screen, dark semi-transparent backdrop
- `.modal` — centered card, max-width 400px, dark bg
- `.modal-header` — title + close X button
- `.modal-section` — padding/spacing for each form section
- `.modal-section-title` — section title styling
- `.form-group` — label + input stacked
- `.form-input` — input styling matching existing selects/textareas

### T3: Add modal logic to auth.js
- `_currentUserEmail` module var, fetched from /auth/me on DOMContentLoaded
- `openSettingsModal()` — shows modal, applies admin-conditional visibility
- `closeSettingsModal()` — hides modal, resets forms
- `handleCreateUser(e)` — validates + POST /auth/users + toast + reset
- `handleChangePassword(e)` — validates + POST /auth/change-password + toast + reset
- Close on backdrop click
- Form validation: password confirmation match, non-empty fields

## Files
- frontend/index.html
- frontend/css/styles.css
- frontend/js/auth.js
