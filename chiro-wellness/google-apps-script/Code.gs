/**
 * Chiro Wellness — Google Calendar booking backend
 * =================================================================
 * Runs as a Google Apps Script Web App under Dr. Venter's Google
 * account. The website calls it to:
 *
 *   GET  ?action=availability&visit=new&from=YYYY-MM-DD&days=21
 *        -> free time slots, worked out from HOURS below minus anything
 *           already on her Google Calendar.
 *   POST {booking JSON}
 *        -> re-checks the slot, creates the calendar event, emails the
 *           clinic and the patient, and (optionally) logs to a Sheet.
 *
 * Setup steps are in README.md. After editing this file you must
 * deploy a NEW VERSION (Deploy > Manage deployments > Edit > New version)
 * for the change to reach the website.
 */

const SETTINGS = {
  // 'primary' = the main calendar of the account that deploys this script.
  // Or paste a specific Calendar ID (Calendar settings > Integrate calendar).
  CALENDAR_ID: 'primary',

  CLINIC_NAME: 'Chiro Wellness',
  DOCTOR_NAME: 'Dr. Machere Venter',
  CLINIC_ADDRESS: 'Plot 2775 Manong Close, Extension 9, Gaborone, Botswana',
  CLINIC_PHONE: '+267 392 6053',
  RECEPTION_EMAIL: 'reception@chiropracticwellnessclinic.org',

  TIME_ZONE: 'Africa/Gaborone',
  UTC_OFFSET: '+02:00', // Botswana has no daylight saving

  // Appointment length in minutes, per visit type.
  DURATIONS: { new: 60, followup: 30 },
  SLOT_STEP_MINUTES: 30,   // a new start time every 30 minutes
  BUFFER_MINUTES: 0,       // gap to keep clear around existing events
  MIN_NOTICE_HOURS: 3,     // no bookings sooner than this
  MAX_DAYS_AHEAD: 60,

  // Opening hours. CONFIRM WITH DR. VENTER. Use [] for closed days.
  HOURS: {
    Mon: [['08:00', '13:00'], ['14:00', '17:00']],
    Tue: [['08:00', '13:00'], ['14:00', '17:00']],
    Wed: [['08:00', '13:00'], ['14:00', '17:00']],
    Thu: [['08:00', '13:00'], ['14:00', '17:00']],
    Fri: [['08:00', '13:00'], ['14:00', '16:00']],
    Sat: [['08:00', '12:00']],
    Sun: []
  },

  // An all-day event (e.g. "Leave", "Conference") blocks that whole day.
  ALL_DAY_EVENTS_BLOCK_DAY: true,

  NOTIFY_RECEPTION: true,          // email the clinic for every booking
  SEND_PATIENT_CONFIRMATION: true, // email the patient a confirmation
  EVENT_COLOR: CalendarApp.EventColor.CYAN,

  // Optional: paste a Google Sheet ID to keep a log of every booking.
  SHEET_ID: ''
};

/* ------------------------------------------------------------------ */
/* Web app entry points                                               */
/* ------------------------------------------------------------------ */

function doGet(e) {
  try {
    const p = (e && e.parameter) || {};
    if (p.action === 'availability') {
      const visit = validVisit_(p.visit);
      const days = Math.max(1, Math.min(31, parseInt(p.days, 10) || 21));
      const from = /^\d{4}-\d{2}-\d{2}$/.test(p.from || '') ? p.from : todayStr_();
      return json_({ ok: true, visit: visit, dates: availability_(from, days, SETTINGS.DURATIONS[visit]) });
    }
    return json_({ ok: true, service: SETTINGS.CLINIC_NAME + ' booking API' });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, code: 'SERVER_ERROR', message: 'Could not load availability.' });
  }
}

function doPost(e) {
  let data;
  try {
    data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
  } catch (err) {
    return json_({ ok: false, code: 'BAD_REQUEST', message: 'Invalid request.' });
  }

  // Honeypot: real people never fill this hidden field.
  if (data.website) return json_({ ok: true, ref: 'CW-OK' });

  const problem = validate_(data);
  if (problem) return json_({ ok: false, code: 'INVALID', message: problem });

  const lock = LockService.getScriptLock();
  if (!lock.tryLock(15000)) {
    return json_({ ok: false, code: 'BUSY', message: 'The booking system is busy. Please try again.' });
  }
  try {
    const visit = validVisit_(data.visit);
    const minutes = SETTINGS.DURATIONS[visit];
    const free = availability_(data.date, 1, minutes)[data.date] || [];
    if (free.indexOf(data.time) === -1) {
      return json_({ ok: false, code: 'SLOT_TAKEN', message: 'Sorry, that time has just been taken. Please choose another.' });
    }

    const start = toDate_(data.date, data.time);
    const end = new Date(start.getTime() + minutes * 60000);
    const ref = 'CW-' + Utilities.formatDate(start, SETTINGS.TIME_ZONE, 'MMdd') + '-' +
      Math.random().toString(36).slice(2, 6).toUpperCase();
    const b = clean_(data);
    b.ref = ref;
    b.visitLabel = visit === 'new' ? 'New patient' : 'Follow-up';
    b.minutes = minutes;
    b.whenText = Utilities.formatDate(start, SETTINGS.TIME_ZONE, "EEEE d MMMM yyyy 'at' HH:mm");

    const event = calendar_().createEvent(
      b.firstName + ' ' + b.lastName + ' · ' + b.visitLabel + ' (' + minutes + ' min)',
      start, end,
      { description: eventDescription_(b), location: SETTINGS.CLINIC_ADDRESS }
    );
    try { event.setColor(SETTINGS.EVENT_COLOR); } catch (ignore) {}
    try { event.setTag('booking_ref', ref); } catch (ignore) {}

    // Notifications must never undo a booking that is already on the calendar.
    try { if (SETTINGS.NOTIFY_RECEPTION) notifyReception_(b); } catch (err) { console.error(err); }
    try { if (SETTINGS.SEND_PATIENT_CONFIRMATION) confirmPatient_(b); } catch (err) { console.error(err); }
    try { if (SETTINGS.SHEET_ID) logToSheet_(b, start); } catch (err) { console.error(err); }

    return json_({ ok: true, ref: ref, start: start.toISOString(), end: end.toISOString() });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, code: 'SERVER_ERROR', message: 'Something went wrong. Please call or WhatsApp the clinic.' });
  } finally {
    lock.releaseLock();
  }
}

/* ------------------------------------------------------------------ */
/* Availability                                                       */
/* ------------------------------------------------------------------ */

function availability_(fromStr, days, minutes) {
  const step = SETTINGS.SLOT_STEP_MINUTES * 60000;
  const dur = minutes * 60000;
  const buffer = SETTINGS.BUFFER_MINUTES * 60000;
  const now = Date.now();
  const earliest = now + SETTINGS.MIN_NOTICE_HOURS * 3600000;
  const latest = now + SETTINGS.MAX_DAYS_AHEAD * 86400000;

  const rangeStart = toDate_(fromStr, '00:00');
  const rangeEnd = new Date(rangeStart.getTime() + days * 86400000);
  const busy = [];
  calendar_().getEvents(rangeStart, rangeEnd).forEach(function (ev) {
    try {
      if (ev.getMyStatus && ev.getMyStatus() === CalendarApp.GuestStatus.NO) return; // she declined it
    } catch (ignore) {}
    if (ev.isAllDayEvent()) {
      if (SETTINGS.ALL_DAY_EVENTS_BLOCK_DAY) {
        busy.push([ev.getAllDayStartDate().getTime(), ev.getAllDayEndDate().getTime()]);
      }
      return;
    }
    busy.push([ev.getStartTime().getTime() - buffer, ev.getEndTime().getTime() + buffer]);
  });

  const out = {};
  for (let d = 0; d < days; d++) {
    const dayStart = new Date(rangeStart.getTime() + d * 86400000);
    const dateStr = Utilities.formatDate(dayStart, SETTINGS.TIME_ZONE, 'yyyy-MM-dd');
    const key = Utilities.formatDate(dayStart, SETTINGS.TIME_ZONE, 'EEE');
    const slots = [];
    (SETTINGS.HOURS[key] || []).forEach(function (range) {
      const open = toDate_(dateStr, range[0]).getTime();
      const close = toDate_(dateStr, range[1]).getTime();
      for (let t = open; t + dur <= close; t += step) {
        if (t < earliest || t > latest) continue;
        const clash = busy.some(function (b) { return t < b[1] && t + dur > b[0]; });
        if (!clash) slots.push(Utilities.formatDate(new Date(t), SETTINGS.TIME_ZONE, 'HH:mm'));
      }
    });
    out[dateStr] = slots;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Validation                                                         */
/* ------------------------------------------------------------------ */

function validate_(d) {
  if (!d || typeof d !== 'object') return 'Invalid request.';
  if (!SETTINGS.DURATIONS[d.visit]) return 'Please choose a visit type.';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.date || '')) return 'Please choose a date.';
  if (!/^\d{2}:\d{2}$/.test(d.time || '')) return 'Please choose a time.';
  if (!str_(d.firstName) || !str_(d.lastName)) return 'Please enter the patient\'s name.';
  if (!/^[+0-9 ()-]{7,20}$/.test(str_(d.phone))) return 'Please enter a valid phone number.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str_(d.email))) return 'Please enter a valid email address.';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.dob || '')) return 'Please enter a date of birth.';
  if (!str_(d.concerns)) return 'Please describe your ailments or previous injuries.';
  if (d.consent !== true) return 'Please accept the privacy consent.';
  return null;
}

function validVisit_(v) {
  return SETTINGS.DURATIONS[v] ? v : 'new';
}

function clean_(d) {
  const areas = Array.isArray(d.areas) ? d.areas.slice(0, 12).map(function (a) { return str_(a, 40); }) : [];
  return {
    visit: d.visit,
    date: d.date,
    time: d.time,
    service: str_(d.service, 60) || 'Not specified',
    firstName: str_(d.firstName, 60),
    lastName: str_(d.lastName, 60),
    dob: d.dob,
    gender: str_(d.gender, 30),
    phone: str_(d.phone, 20),
    email: str_(d.email, 120),
    medicalAid: str_(d.medicalAid, 80),
    guardian: str_(d.guardian, 100),
    areas: areas,
    concerns: str_(d.concerns, 2000)
  };
}

function str_(v, max) {
  const s = (v === undefined || v === null) ? '' : String(v).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim();
  return max ? s.slice(0, max) : s;
}

/* ------------------------------------------------------------------ */
/* Calendar event, emails, sheet                                      */
/* ------------------------------------------------------------------ */

function eventDescription_(b) {
  return [
    'Booking ref: ' + b.ref,
    'Visit: ' + b.visitLabel + ' (' + b.minutes + ' min)',
    'Reason: ' + b.service,
    '',
    'PATIENT',
    'Name: ' + b.firstName + ' ' + b.lastName,
    'Date of birth: ' + b.dob + ' (age ' + age_(b.dob) + ')',
    b.gender ? 'Gender: ' + b.gender : null,
    b.guardian ? 'Parent / guardian: ' + b.guardian : null,
    'Phone: ' + b.phone,
    'Email: ' + b.email,
    'Medical aid: ' + (b.medicalAid || 'None given'),
    '',
    'AREAS OF CONCERN',
    b.areas.length ? b.areas.join(', ') : 'None selected',
    '',
    'AILMENTS / PREVIOUS INJURIES',
    b.concerns,
    '',
    'Booked online via the Chiro Wellness website.'
  ].filter(function (line) { return line !== null; }).join('\n');
}

function notifyReception_(b) {
  const rows = [
    ['When', b.whenText],
    ['Visit', b.visitLabel + ' (' + b.minutes + ' min)'],
    ['Reason', b.service],
    ['Patient', b.firstName + ' ' + b.lastName],
    ['Date of birth', b.dob + ' (age ' + age_(b.dob) + ')'],
    ['Gender', b.gender || '—'],
    ['Parent / guardian', b.guardian || '—'],
    ['Phone', b.phone],
    ['Email', b.email],
    ['Medical aid', b.medicalAid || '—'],
    ['Areas', b.areas.join(', ') || '—'],
    ['Ailments / injuries', b.concerns]
  ];
  const table = rows.map(function (r) {
    return '<tr><td style="padding:6px 12px 6px 0;color:#5b6f6b;vertical-align:top;white-space:nowrap">' + esc_(r[0]) +
      '</td><td style="padding:6px 0;color:#0D2E2A;white-space:pre-wrap">' + esc_(r[1]) + '</td></tr>';
  }).join('');
  MailApp.sendEmail({
    to: SETTINGS.RECEPTION_EMAIL,
    replyTo: b.email,
    name: SETTINGS.CLINIC_NAME + ' Bookings',
    subject: 'New booking: ' + b.firstName + ' ' + b.lastName + ' — ' + b.whenText + ' [' + b.ref + ']',
    htmlBody: '<div style="font-family:Arial,sans-serif;font-size:14px"><h2 style="color:#1A8C78;margin:0 0 12px">New online booking</h2>' +
      '<table style="border-collapse:collapse">' + table + '</table>' +
      '<p style="color:#5b6f6b">Ref ' + esc_(b.ref) + ' — already added to the clinic Google Calendar.</p></div>'
  });
}

function confirmPatient_(b) {
  // Deliberately leaves out health details: email is not a secure channel.
  MailApp.sendEmail({
    to: b.email,
    replyTo: SETTINGS.RECEPTION_EMAIL,
    name: SETTINGS.CLINIC_NAME,
    subject: 'Your appointment at ' + SETTINGS.CLINIC_NAME + ' — ' + b.whenText,
    htmlBody:
      '<div style="font-family:Arial,sans-serif;font-size:15px;color:#0D2E2A;max-width:560px">' +
      '<h2 style="font-family:Georgia,serif;color:#1A8C78;font-weight:normal">Thank you, ' + esc_(b.firstName) + '.</h2>' +
      '<p>Your appointment with ' + esc_(SETTINGS.DOCTOR_NAME) + ' is booked.</p>' +
      '<p style="background:#F2F7F6;padding:14px 16px;border-left:3px solid #F0A500">' +
      '<strong>' + esc_(b.whenText) + '</strong><br>' + esc_(b.visitLabel) + ' · ' + b.minutes + ' minutes<br>' +
      esc_(SETTINGS.CLINIC_ADDRESS) + '</p>' +
      (b.visit === 'new' ? '<p>For your first visit, please arrive 10 minutes early, wear comfortable clothing and bring any X-rays, scans or reports you have.</p>' : '') +
      '<p>Need to change or cancel? Reply to this email or call ' + esc_(SETTINGS.CLINIC_PHONE) + '.</p>' +
      '<p style="color:#5b6f6b;font-size:13px">Booking reference: ' + esc_(b.ref) + '</p></div>'
  });
}

function logToSheet_(b, start) {
  const ss = SpreadsheetApp.openById(SETTINGS.SHEET_ID);
  const sheet = ss.getSheetByName('Bookings') || ss.insertSheet('Bookings');
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Booked at', 'Ref', 'Appointment', 'Visit', 'Reason', 'First name', 'Last name',
      'DOB', 'Gender', 'Guardian', 'Phone', 'Email', 'Medical aid', 'Areas', 'Ailments / injuries']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), b.ref, start, b.visitLabel, b.service, b.firstName, b.lastName,
    b.dob, b.gender, b.guardian, b.phone, b.email, b.medicalAid, b.areas.join(', '), b.concerns]
    .map(function (v) { return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v; }));
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

function calendar_() {
  const cal = SETTINGS.CALENDAR_ID === 'primary'
    ? CalendarApp.getDefaultCalendar()
    : CalendarApp.getCalendarById(SETTINGS.CALENDAR_ID);
  if (!cal) throw new Error('Calendar not found: ' + SETTINGS.CALENDAR_ID);
  return cal;
}

function toDate_(dateStr, timeStr) {
  return new Date(dateStr + 'T' + timeStr + ':00' + SETTINGS.UTC_OFFSET);
}

function todayStr_() {
  return Utilities.formatDate(new Date(), SETTINGS.TIME_ZONE, 'yyyy-MM-dd');
}

function age_(dob) {
  const parts = String(dob).split('-').map(Number);
  const today = todayStr_().split('-').map(Number);
  let age = today[0] - parts[0];
  if (today[1] < parts[1] || (today[1] === parts[1] && today[2] < parts[2])) age--;
  return age;
}

function esc_(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Run this once from the editor (select testSetup > Run) to grant
 * permissions and check the calendar connection before deploying.
 */
function testSetup() {
  const cal = calendar_();
  console.log('Connected to calendar: ' + cal.getName());
  const slots = availability_(todayStr_(), 7, SETTINGS.DURATIONS.new);
  Object.keys(slots).forEach(function (d) { console.log(d + ': ' + (slots[d].join(', ') || 'no free slots')); });
}
