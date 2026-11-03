/**
 * Chiro Wellness — Google Calendar booking backend
 * =================================================================
 * Runs as a Google Apps Script Web App under the clinic's BOOKING
 * ACCOUNT (e.g. reception's Google account). For every booking it:
 *
 *   1. checks the time is free on Dr. Venter's calendar (free/busy)
 *      and on the bookings calendar,
 *   2. creates the appointment and sends Google Calendar INVITATIONS
 *      to Dr. Venter and to the patient,
 *   3. the patient CONFIRMS by tapping "Yes" on the invitation.
 *      Dr. Venter sees their answer in the event's guest list.
 *
 * A timed check (checkResponses, every 15 minutes) then:
 *   - cancels the booking and frees the slot if the patient taps "No",
 *   - optionally releases bookings never confirmed (RELEASE_UNCONFIRMED_AFTER_HOURS),
 *   - emails reception if Dr. Venter declines an appointment.
 *
 * Website endpoints:
 *   GET  ?action=availability&visit=new&from=YYYY-MM-DD&days=21  -> free slots
 *   POST {booking JSON}                                          -> create booking
 *
 * Requires the "Google Calendar API" advanced service (Services > + in the editor).
 * Setup steps are in README.md. After editing, deploy a NEW VERSION
 * (Deploy > Manage deployments > Edit > New version).
 */

const SETTINGS = {
  // Calendar the bookings are created on, in the account running this script.
  BOOKINGS_CALENDAR_ID: 'primary',

  // Dr. Venter's Google account. She is invited to every booking, and her busy
  // times are read from her calendar. She must share her calendar with the
  // booking account ("See only free/busy" is enough).
  // Leave '' only if this script runs as Dr. Venter herself: bookings then go
  // straight into her calendar instead of arriving as invitations.
  DOCTOR_EMAIL: '',

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

  // Only these dates can be booked (YYYY-MM-DD), using that weekday's HOURS.
  // Set to [] to open every day in HOURS. Keep in sync with bookableDates in assets/config.js.
  BOOKABLE_DATES: ['2026-11-07'],

  // Where Dr. Venter practises on specific dates, if not at CLINIC_ADDRESS.
  // Used in the invitation, emails and Sheet. Keep in sync with locationsByDate in assets/config.js.
  LOCATIONS_BY_DATE: {
    '2026-11-07': '9 Sherwood Village, Radiokop, Roodepoort, South Africa'
  },

  // Opening hours. CONFIRM WITH DR. VENTER. Use [] for closed days.
  HOURS: {
    Mon: [['08:00', '13:00'], ['14:00', '17:00']],
    Tue: [['08:00', '13:00'], ['14:00', '17:00']],
    Wed: [['08:00', '13:00'], ['14:00', '17:00']],
    Thu: [['08:00', '13:00'], ['14:00', '17:00']],
    Fri: [['08:00', '13:00'], ['14:00', '16:00']],
    Sat: [['08:00', '13:00']],
    Sun: []
  },

  // An all-day event on the BOOKINGS calendar (e.g. "Clinic closed") blocks that day.
  ALL_DAY_EVENTS_BLOCK_DAY: true,

  // Invitations and confirmation
  INVITE_PATIENT: true,               // patient gets an invitation and confirms by tapping "Yes"
  PATIENTS_SEE_GUEST_LIST: true,      // lets Dr. Venter see the patient's Yes/No; patients also see her email address
  HEALTH_DETAILS_IN_INVITE: true,     // reason, history etc. in the invitation (the patient sees their own answers)
  CANCEL_WHEN_PATIENT_DECLINES: true, // patient taps "No" -> booking cancelled, slot freed
  RELEASE_UNCONFIRMED_AFTER_HOURS: 0, // 0 = keep unconfirmed bookings; e.g. 24 = cancel if not confirmed within a day

  NOTIFY_RECEPTION: true,             // email reception for every booking and every alert
  EVENT_COLOR_ID: '7',                // 7 = Peacock (teal) in Google Calendar

  // Optional: paste a Google Sheet ID to keep a log of every booking.
  SHEET_ID: ''
};

const SOURCE_TAG = 'chirowellness-website';

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
    b.location = locationFor_(data.date);

    createBookingEvent_(b, start, end);

    // Notifications must never undo a booking that is already on the calendar.
    try { if (SETTINGS.NOTIFY_RECEPTION) notifyReception_(b); } catch (err) { console.error(err); }
    try { if (!SETTINGS.INVITE_PATIENT) confirmPatient_(b); } catch (err) { console.error(err); }
    try { if (SETTINGS.SHEET_ID) logToSheet_(b, start); } catch (err) { console.error(err); }

    return json_({ ok: true, ref: ref, invited: SETTINGS.INVITE_PATIENT, start: start.toISOString(), end: end.toISOString() });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, code: 'SERVER_ERROR', message: 'Something went wrong. Please call or WhatsApp the clinic.' });
  } finally {
    lock.releaseLock();
  }
}

/* ------------------------------------------------------------------ */
/* Creating the booking and its invitations                           */
/* ------------------------------------------------------------------ */

function createBookingEvent_(b, start, end) {
  const attendees = [];
  if (SETTINGS.DOCTOR_EMAIL) attendees.push({ email: SETTINGS.DOCTOR_EMAIL, displayName: SETTINGS.DOCTOR_NAME });
  if (SETTINGS.INVITE_PATIENT) attendees.push({ email: b.email, displayName: b.firstName + ' ' + b.lastName });

  return Calendar.Events.insert({
    summary: SETTINGS.CLINIC_NAME + ' · ' + b.firstName + ' ' + b.lastName + ' · ' + b.visitLabel,
    location: b.location,
    description: eventDescription_(b),
    start: { dateTime: start.toISOString(), timeZone: SETTINGS.TIME_ZONE },
    end: { dateTime: end.toISOString(), timeZone: SETTINGS.TIME_ZONE },
    attendees: attendees,
    guestsCanSeeOtherGuests: SETTINGS.PATIENTS_SEE_GUEST_LIST,
    guestsCanInviteOthers: false,
    guestsCanModify: false,
    colorId: SETTINGS.EVENT_COLOR_ID,
    extendedProperties: {
      private: {
        source: SOURCE_TAG,
        ref: b.ref,
        patientEmail: b.email.toLowerCase(),
        patientName: b.firstName + ' ' + b.lastName,
        patientPhone: b.phone
      }
    }
  }, SETTINGS.BOOKINGS_CALENDAR_ID, { sendUpdates: attendees.length ? 'all' : 'none' });
}

/* ------------------------------------------------------------------ */
/* Timed check: patient confirmations, declines, doctor declines      */
/* Installed by setup(); runs every 15 minutes.                        */
/* ------------------------------------------------------------------ */

function checkResponses() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;
  try {
    const now = new Date();
    const until = new Date(now.getTime() + SETTINGS.MAX_DAYS_AHEAD * 86400000);
    listEvents_(now, until, { privateExtendedProperty: 'source=' + SOURCE_TAG }).forEach(function (ev) {
      if (ev.status === 'cancelled' || !ev.start || !ev.start.dateTime) return;
      const info = (ev.extendedProperties && ev.extendedProperties.private) || {};
      const when = Utilities.formatDate(new Date(ev.start.dateTime), SETTINGS.TIME_ZONE, "EEEE d MMMM 'at' HH:mm");
      const patient = responseOf_(ev, info.patientEmail);
      const who = (info.patientName || 'The patient') + (info.patientPhone ? ' (' + info.patientPhone + ')' : '');

      if (SETTINGS.CANCEL_WHEN_PATIENT_DECLINES && patient === 'declined') {
        cancelEvent_(ev);
        alert_('Booking cancelled by patient: ' + (info.patientName || '') + ', ' + when,
          who + ' declined the invitation for ' + when + ', so the booking was cancelled and the time is free again. Ref ' + info.ref + '.');
        return;
      }

      const hours = SETTINGS.RELEASE_UNCONFIRMED_AFTER_HOURS;
      if (hours > 0 && patient === 'needsAction' && now.getTime() - Date.parse(ev.created) > hours * 3600000) {
        cancelEvent_(ev);
        alert_('Unconfirmed booking released: ' + (info.patientName || '') + ', ' + when,
          who + ' did not confirm within ' + hours + ' hours, so the booking for ' + when + ' was cancelled. Ref ' + info.ref + '.');
        return;
      }

      if (SETTINGS.DOCTOR_EMAIL && responseOf_(ev, SETTINGS.DOCTOR_EMAIL) === 'declined' && !info.doctorDeclinedAlerted) {
        alert_('Dr. Venter declined: ' + (info.patientName || '') + ', ' + when,
          SETTINGS.DOCTOR_NAME + ' declined the appointment with ' + who + ' on ' + when + '. Please contact the patient to rebook, ' +
          'then delete the event from the bookings calendar. The time stays blocked until you do. Ref ' + info.ref + '.');
        const updated = Object.assign({}, info, { doctorDeclinedAlerted: '1' });
        Calendar.Events.patch({ extendedProperties: { private: updated } }, SETTINGS.BOOKINGS_CALENDAR_ID, ev.id, { sendUpdates: 'none' });
      }
    });
  } finally {
    lock.releaseLock();
  }
}

function cancelEvent_(ev) {
  // Google emails a cancellation to Dr. Venter and the patient.
  Calendar.Events.remove(SETTINGS.BOOKINGS_CALENDAR_ID, ev.id, { sendUpdates: 'all' });
}

function alert_(subject, text) {
  if (!SETTINGS.NOTIFY_RECEPTION) return;
  MailApp.sendEmail({ to: SETTINGS.RECEPTION_EMAIL, name: SETTINGS.CLINIC_NAME + ' Bookings', subject: subject, body: text });
}

function responseOf_(ev, email) {
  if (!email) return null;
  const target = String(email).toLowerCase();
  const a = (ev.attendees || []).filter(function (x) { return String(x.email).toLowerCase() === target; })[0];
  return a ? a.responseStatus : null;
}

/* ------------------------------------------------------------------ */
/* Availability                                                       */
/* ------------------------------------------------------------------ */

function availability_(fromStr, days, minutes) {
  const step = SETTINGS.SLOT_STEP_MINUTES * 60000;
  const dur = minutes * 60000;
  const now = Date.now();
  const earliest = now + SETTINGS.MIN_NOTICE_HOURS * 3600000;
  const latest = now + SETTINGS.MAX_DAYS_AHEAD * 86400000;

  const rangeStart = toDate_(fromStr, '00:00');
  const rangeEnd = new Date(rangeStart.getTime() + days * 86400000);
  const busy = busyIntervals_(rangeStart, rangeEnd);

  const out = {};
  for (let d = 0; d < days; d++) {
    const dayStart = new Date(rangeStart.getTime() + d * 86400000);
    const dateStr = Utilities.formatDate(dayStart, SETTINGS.TIME_ZONE, 'yyyy-MM-dd');
    const key = Utilities.formatDate(dayStart, SETTINGS.TIME_ZONE, 'EEE');
    const slots = [];
    if (SETTINGS.BOOKABLE_DATES.length && SETTINGS.BOOKABLE_DATES.indexOf(dateStr) === -1) {
      out[dateStr] = slots;
      continue;
    }
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

function busyIntervals_(start, end) {
  const buffer = SETTINGS.BUFFER_MINUTES * 60000;
  const busy = [];

  // 1. Everything on the bookings calendar, including earlier website bookings.
  listEvents_(start, end).forEach(function (ev) {
    if (ev.status === 'cancelled') return;
    if (ev.start && ev.start.date) {
      if (SETTINGS.ALL_DAY_EVENTS_BLOCK_DAY) {
        busy.push([toDate_(ev.start.date, '00:00').getTime(), toDate_(ev.end.date, '00:00').getTime()]);
      }
      return;
    }
    if (ev.transparency === 'transparent') return;
    if ((ev.attendees || []).some(function (a) { return a.self && a.responseStatus === 'declined'; })) return;
    const info = ev.extendedProperties && ev.extendedProperties.private;
    if (info && info.source === SOURCE_TAG && responseOf_(ev, info.patientEmail) === 'declined') return;
    busy.push([Date.parse(ev.start.dateTime) - buffer, Date.parse(ev.end.dateTime) + buffer]);
  });

  // 2. Dr. Venter's own calendar, via free/busy.
  if (SETTINGS.DOCTOR_EMAIL) {
    doctorBusy_(start, end).forEach(function (b) { busy.push([b[0] - buffer, b[1] + buffer]); });
  }
  return busy;
}

function doctorBusy_(start, end) {
  const id = SETTINGS.DOCTOR_EMAIL;
  const res = Calendar.Freebusy.query({
    timeMin: start.toISOString(), timeMax: end.toISOString(), timeZone: SETTINGS.TIME_ZONE, items: [{ id: id }]
  });
  const cal = res.calendars && (res.calendars[id] || res.calendars[id.toLowerCase()]);
  if (!cal || (cal.errors && cal.errors.length)) {
    const reason = cal && cal.errors && cal.errors.length ? cal.errors[0].reason : 'no data';
    throw new Error('Cannot read free/busy for ' + id + ' (' + reason + '). ' +
      'Dr. Venter must share her calendar with this account: Google Calendar > Settings > her calendar > ' +
      'Share with specific people > add this account > "See only free/busy".');
  }
  return (cal.busy || []).map(function (b) { return [Date.parse(b.start), Date.parse(b.end)]; });
}

function listEvents_(start, end, extra) {
  const out = [];
  let pageToken = null;
  do {
    const params = Object.assign({
      timeMin: start.toISOString(), timeMax: end.toISOString(), singleEvents: true, maxResults: 2500
    }, extra || {});
    if (pageToken) params.pageToken = pageToken;
    const res = Calendar.Events.list(SETTINGS.BOOKINGS_CALENDAR_ID, params);
    (res.items || []).forEach(function (item) { out.push(item); });
    pageToken = res.nextPageToken;
  } while (pageToken);
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
  if (!str_(d.reasonDetails)) return 'Please tell us a little about why you are coming in.';
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
    reasonDetails: str_(d.reasonDetails, 500),
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
/* Invitation text, emails, sheet                                     */
/* ------------------------------------------------------------------ */

function eventDescription_(b) {
  const lines = ['Booking ref: ' + b.ref, b.visitLabel + ' · ' + b.minutes + ' minutes with ' + SETTINGS.DOCTOR_NAME,
    'Where: ' + b.location, ''];
  if (SETTINGS.INVITE_PATIENT) {
    lines.push(
      'FOR THE PATIENT',
      'Please tap "Yes" on this invitation to confirm your booking.',
      'To change or cancel, call ' + SETTINGS.CLINIC_PHONE + ' or email ' + SETTINGS.RECEPTION_EMAIL + '.'
    );
    if (b.visit === 'new') {
      lines.push('First visit: please arrive 10 minutes early, wear comfortable clothing and bring any X-rays, scans or reports.');
    }
    lines.push('');
  }
  lines.push(
    'BOOKING DETAILS',
    'Patient: ' + b.firstName + ' ' + b.lastName,
    'Phone: ' + b.phone,
    'Email: ' + b.email,
    'Reason: ' + b.service
  );
  if (SETTINGS.HEALTH_DETAILS_IN_INVITE) {
    lines.push(
      'About the visit: ' + b.reasonDetails,
      'Date of birth: ' + b.dob + ' (age ' + age_(b.dob) + ')',
      b.gender ? 'Gender: ' + b.gender : null,
      b.guardian ? 'Parent / guardian: ' + b.guardian : null,
      'Medical aid: ' + (b.medicalAid || 'None given'),
      'Areas of concern: ' + (b.areas.length ? b.areas.join(', ') : 'None selected'),
      '',
      'Ailments / previous injuries:',
      b.concerns
    );
  } else {
    lines.push('', 'Clinical details were emailed to the clinic.');
  }
  lines.push('', 'Booked online via the ' + SETTINGS.CLINIC_NAME + ' website.');
  return lines.filter(function (line) { return line !== null; }).join('\n');
}

function notifyReception_(b) {
  const rows = [
    ['When', b.whenText],
    ['Where', b.location],
    ['Visit', b.visitLabel + ' (' + b.minutes + ' min)'],
    ['Reason', b.service],
    ['About the visit', b.reasonDetails],
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
  const invited = [SETTINGS.DOCTOR_EMAIL ? SETTINGS.DOCTOR_NAME : null, SETTINGS.INVITE_PATIENT ? 'the patient' : null]
    .filter(Boolean).join(' and ');
  const footer = invited
    ? 'Calendar invitations were sent to ' + esc_(invited) + '. ' +
      (SETTINGS.INVITE_PATIENT ? 'The booking is confirmed when the patient taps "Yes"; Google emails the booking account when they do.' : '')
    : 'Added to the clinic Google Calendar.';
  const mail = {
    to: SETTINGS.RECEPTION_EMAIL,
    replyTo: b.email,
    name: SETTINGS.CLINIC_NAME + ' Bookings',
    subject: 'New booking: ' + b.firstName + ' ' + b.lastName + ' — ' + b.whenText + ' [' + b.ref + ']',
    htmlBody: '<div style="font-family:Arial,sans-serif;font-size:14px"><h2 style="color:#1A8C78;margin:0 0 12px">New online booking</h2>' +
      '<table style="border-collapse:collapse">' + table + '</table>' +
      '<p style="color:#5b6f6b">Ref ' + esc_(b.ref) + '. ' + footer + '</p></div>'
  };
  // If health details are kept out of the invitation, Dr. Venter gets them here instead.
  if (!SETTINGS.HEALTH_DETAILS_IN_INVITE && SETTINGS.DOCTOR_EMAIL) mail.cc = SETTINGS.DOCTOR_EMAIL;
  MailApp.sendEmail(mail);
}

// Only used when INVITE_PATIENT is false, so the patient still hears back.
function confirmPatient_(b) {
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
      esc_(b.location) + '</p>' +
      (b.visit === 'new' ? '<p>For your first visit, please arrive 10 minutes early, wear comfortable clothing and bring any X-rays, scans or reports you have.</p>' : '') +
      '<p>Need to change or cancel? Reply to this email or call ' + esc_(SETTINGS.CLINIC_PHONE) + '.</p>' +
      '<p style="color:#5b6f6b;font-size:13px">Booking reference: ' + esc_(b.ref) + '</p></div>'
  });
}

function logToSheet_(b, start) {
  const ss = SpreadsheetApp.openById(SETTINGS.SHEET_ID);
  const sheet = ss.getSheetByName('Bookings') || ss.insertSheet('Bookings');
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Booked at', 'Ref', 'Appointment', 'Where', 'Visit', 'Reason', 'About the visit', 'First name', 'Last name',
      'DOB', 'Gender', 'Guardian', 'Phone', 'Email', 'Medical aid', 'Areas', 'Ailments / injuries']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), b.ref, start, b.location, b.visitLabel, b.service, b.reasonDetails, b.firstName, b.lastName,
    b.dob, b.gender, b.guardian, b.phone, b.email, b.medicalAid, b.areas.join(', '), b.concerns]
    .map(function (v) { return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v; }));
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

function locationFor_(dateStr) {
  return (SETTINGS.LOCATIONS_BY_DATE && SETTINGS.LOCATIONS_BY_DATE[dateStr]) || SETTINGS.CLINIC_ADDRESS;
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
 * Run this once from the editor (select setup > Run) before deploying.
 * It grants permissions, checks both calendars can be read, installs the
 * 15-minute response check, and prints the next week's free slots.
 */
function setup() {
  const cal = Calendar.Calendars.get(SETTINGS.BOOKINGS_CALENDAR_ID);
  console.log('Bookings calendar: ' + cal.summary + ' (' + cal.id + ')');

  if (SETTINGS.DOCTOR_EMAIL) {
    doctorBusy_(new Date(), new Date(Date.now() + 7 * 86400000));
    console.log('Can read free/busy for ' + SETTINGS.DOCTOR_EMAIL + '. She will be invited to every booking.');
  } else {
    console.log('DOCTOR_EMAIL is empty: bookings go straight into this account\'s calendar with no invitation for Dr. Venter.');
  }

  const installed = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'checkResponses'; });
  if (!installed) {
    ScriptApp.newTrigger('checkResponses').timeBased().everyMinutes(15).create();
    console.log('Installed the 15-minute response check.');
  } else {
    console.log('Response check already installed.');
  }

  const slots = availability_(todayStr_(), 7, SETTINGS.DURATIONS.new);
  Object.keys(slots).forEach(function (d) { console.log(d + ': ' + (slots[d].join(', ') || 'no free slots')); });
}
