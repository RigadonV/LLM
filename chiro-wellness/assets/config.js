/*
 * Chiro Wellness — site settings
 * ------------------------------------------------------------------
 * This is the only file you need to edit to go live.
 *
 * 1. Deploy the Google Apps Script in /google-apps-script (see README.md).
 * 2. Paste the Web App URL it gives you into APPS_SCRIPT_URL below.
 *
 * While APPS_SCRIPT_URL is empty the page runs in DEMO MODE: it shows
 * sample time slots and does not create real bookings.
 */
window.CHIRO_CONFIG = {
  APPS_SCRIPT_URL: "",

  clinic: {
    name: "Chiro Wellness",
    legalName: "Chiropractic Wellness Clinic Botswana",
    doctor: "Dr. Machere Venter",
    address: "Plot 2775 Manong Close, Extension 9, Gaborone, Botswana",
    phone: "+267 392 6053",
    cell: "+267 744 70669",
    whatsapp: "26774470669",
    email: "reception@chiropracticwellnessclinic.org",
    timeZone: "Africa/Gaborone",
    utcOffset: "+02:00"
  },

  // How many days ahead patients can pick from on the booking form.
  daysToShow: 21,

  // Only these dates are offered (YYYY-MM-DD). Set to [] to offer every open day.
  // Keep in sync with BOOKABLE_DATES in google-apps-script/Code.gs, which enforces it.
  bookableDates: ["2026-11-07"],

  // Visit types. Keys must match DURATIONS in google-apps-script/Code.gs.
  visitTypes: {
    new:      { label: "New patient",      detail: "Initial consultation & assessment", minutes: 60 },
    followup: { label: "Returning patient", detail: "Follow-up adjustment",              minutes: 30 }
  },

  services: [
    "Back & neck pain",
    "Pregnancy chiropractic",
    "Sports & injury",
    "Paediatric & family",
    "Headache & migraine",
    "Arthritis & joint pain",
    "Posture & ergonomics",
    "Something else"
  ],

  bodyAreas: [
    "Neck", "Upper back", "Lower back", "Shoulder", "Hip",
    "Knee", "Headaches", "Sciatica / leg pain", "Pregnancy", "Sports injury"
  ],

  // Opening hours, shown in the footer and used for demo slots.
  // CONFIRM WITH DR. VENTER. The live hours are set in Code.gs (HOURS).
  hours: {
    Mon: [["08:00", "13:00"], ["14:00", "17:00"]],
    Tue: [["08:00", "13:00"], ["14:00", "17:00"]],
    Wed: [["08:00", "13:00"], ["14:00", "17:00"]],
    Thu: [["08:00", "13:00"], ["14:00", "17:00"]],
    Fri: [["08:00", "13:00"], ["14:00", "16:00"]],
    Sat: [["08:00", "12:00"]],
    Sun: []
  },
  slotStepMinutes: 30,
  minNoticeHours: 3
};
