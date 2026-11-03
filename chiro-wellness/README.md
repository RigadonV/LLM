# Chiro Wellness — online booking page

A single-page, hostable booking site for **Chiropractic Wellness Clinic Botswana** (Dr. Machere Venter).
It has a three.js 3D hero, a three-step booking form, and a live connection to **Google Calendar** through
a free Google Apps Script. No server or database is needed.

```
chiro-wellness/
├── index.html                  the page
├── assets/
│   ├── config.js               ← the only website file you edit to go live
│   ├── styles.css
│   ├── booking.js              booking form logic
│   └── spine.js                three.js 3D spine animation
└── google-apps-script/
    ├── Code.gs                 calendar backend (paste into Apps Script)
    └── appsscript.json         manifest (time zone, Calendar API, web app settings)
```

## How a booking works

**On the website**

1. **Appointment:** visit type (new 60 min / follow-up 30 min), main reason, a short **description of the reason**,
   then a date and a time. Times are live from Dr. Venter's calendar.
2. **Patient details:** name, date of birth, gender (optional), mobile, email and medical aid (optional).
   For patients under 18 it also asks for a parent or guardian.
3. **Health history:** tap where it hurts, and describe **ailments or previous injuries**.

**Behind the scenes**

```
Patient books ──► Booking account creates the appointment
                    ├─► Google Calendar invitation to Dr. Venter   (full booking details in the invite)
                    ├─► Google Calendar invitation to the patient  ("tap Yes to confirm")
                    └─► Email summary to reception

Patient taps Yes ─► Dr. Venter sees "Yes" next to the patient in her invitation. Booking confirmed.
Patient taps No ──► Booking cancelled automatically, slot freed, both notified, reception emailed.
Dr. Venter declines ─► Reception emailed to contact the patient and rebook.
```

The patient's Yes/No is picked up by a check that runs every 15 minutes.

### Why a separate "booking account"?

Google only sends an invitation to *guests*, never to the person who owns the event. For Dr. Venter to
**receive** an invitation, bookings must be created by a different Google account. Use reception's Google
account, or create a free Gmail such as `chirowellness.bookings@gmail.com`. That account:

- runs the script and owns the bookings calendar,
- reads Dr. Venter's busy times (she shares her calendar with it),
- sends the invitations, and receives Google's emails when patients accept or decline.

> Prefer no invitation for Dr. Venter? Run the script from **her** account and leave `DOCTOR_EMAIL` empty.
> Bookings then go straight into her calendar, and patients are still invited.

Until the script is connected, the page runs in **demo mode**: it shows sample times and a yellow banner, and saves nothing.

## Preview it

Double-click `index.html`, or serve the folder:

```bash
cd chiro-wellness && python3 -m http.server 8000   # then open http://localhost:8000
```

## Connect Google Calendar (about 15 minutes)

**A. In Dr. Venter's Google account (once):**

1. Open Google Calendar → ⚙ **Settings** → under *Settings for my calendars* click her calendar.
2. **Share with specific people** → **Add people** → enter the booking account's email →
   permission **See only free/busy (hide details)** → Send.

**B. In the booking account:**

1. Go to <https://script.google.com> → **New project**. Name it "Chiro Wellness Bookings".
2. Delete the sample code and paste in the whole of `google-apps-script/Code.gs`.
3. In the left sidebar, click **Services ＋** → choose **Google Calendar API** → **Add**.
4. ⚙ **Project Settings** → set the time zone to **(GMT+02:00) Gaborone**.
5. At the top of `Code.gs`, fill in `SETTINGS`:
   - `DOCTOR_EMAIL`: Dr. Venter's Google account email.
   - `HOURS`: **confirm her real opening hours**. The ones included are placeholders.
   - `RECEPTION_EMAIL`: where booking summaries and alerts go.
   - Optional: `RELEASE_UNCONFIRMED_AFTER_HOURS` (e.g. `24` to cancel bookings never confirmed), `SHEET_ID` for a booking log.
6. Choose `setup` in the function dropdown and click **Run**. Approve the permissions. Google will say
   *"Google hasn't verified this app"*: click **Advanced → Go to Chiro Wellness Bookings**. This is normal for your own scripts.
   The log should confirm it can read Dr. Venter's free/busy, show *Installed the 15-minute response check*, and list free slots.
   If it says it **cannot read free/busy**, step A hasn't been done for this account.
7. **Deploy → New deployment → Web app**: *Execute as* **Me**, *Who has access* **Anyone** → **Deploy**.
   Copy the **Web app URL** (ends in `/exec`).
8. Paste it into `assets/config.js`:
   ```js
   APPS_SCRIPT_URL: "https://script.google.com/macros/s/AKfy.../exec",
   ```
9. Reload the page. The demo banner disappears and the times are her real availability. Make a test booking with
   your own email address: you should receive the invitation, and Dr. Venter should receive hers.

**Changing the script later:** after editing `Code.gs`, go to **Deploy → Manage deployments → ✏️ Edit →
Version: New version → Deploy**. The URL stays the same. Saving alone does not update the live version.

## Blocking time off

- Anything **busy** on Dr. Venter's calendar blocks those times.
- Google makes **all-day events "Free" by default**. For a day off on her calendar, open the all-day event and set it to **Busy**,
  or add a normal timed event covering the hours.
- An all-day event on the **booking account's** calendar (e.g. "Clinic closed") always blocks the whole day.

## Settings you may want to change (`Code.gs`)

| Setting | Default | What it does |
|---|---|---|
| `INVITE_PATIENT` | `true` | Patient gets a calendar invitation and confirms by tapping Yes. If `false`, they get a plain confirmation email instead. |
| `PATIENTS_SEE_GUEST_LIST` | `true` | Lets Dr. Venter see the patient's Yes/No in her invitation. The trade-off is that patients can see her email address. |
| `HEALTH_DETAILS_IN_INVITE` | `true` | Puts the reason, history and other answers in the invitation, which the patient also receives. If `false`, those details go only to reception's email, with Dr. Venter copied. |
| `CANCEL_WHEN_PATIENT_DECLINES` | `true` | A "No" from the patient cancels the booking and frees the slot. |
| `RELEASE_UNCONFIRMED_AFTER_HOURS` | `0` | `0` keeps unconfirmed bookings. A number such as `24` cancels bookings not confirmed within that many hours. |

## Host it

It's plain static files. Any of these work:

- **Netlify Drop**: drag the `chiro-wellness` folder onto <https://app.netlify.com/drop>. You get free HTTPS and can add `chirowellness.co.bw` later.
- **GitHub Pages / Vercel / Cloudflare Pages**: point them at this folder.
- **Any cPanel web host**: upload the folder contents to `public_html`.

## Customising

| What | Where |
|---|---|
| Clinic phone, email, address, WhatsApp number | `assets/config.js` → `clinic` (and the matching `SETTINGS` in `Code.gs`) |
| Visit types and their lengths | `assets/config.js` → `visitTypes` **and** `Code.gs` → `DURATIONS` (keys must match) |
| Reasons for visit and body-area tags | `assets/config.js` → `services`, `bodyAreas` |
| Opening hours shown in the footer | `assets/config.js` → `hours` |
| Opening hours used for real bookings | `Code.gs` → `HOURS` (keep the two in sync) |
| Colours and fonts | top of `assets/styles.css` (`:root` variables, per the brand spec in the BRD) |

## Good to know

- **Privacy.** Patient details live only in Google accounts the clinic controls (the booking account, Dr. Venter's calendar
  invitation and reception's inbox), plus the patient's own invitation. The public web app URL only reveals which times are free.
  Turn on 2-Step Verification for the booking account and Dr. Venter's account.
- **Email typos.** Invitations go to whatever address the patient types, and the form reminds them of this.
  If a patient never receives theirs, check the address in the booking (reception's email shows it).
- **Limits.** Reception emails use Apps Script's mail quota: about 100 a day on a free Gmail account, far more on Google Workspace.
  Calendar invitations are sent by Google Calendar itself.
- **Spam.** The form has a hidden honeypot field, and the script validates every field server-side.
- **3D performance.** The hero uses about 5 WebGL draw calls, pauses when scrolled out of view, lowers its resolution
  automatically on slow phones, and shows a static gradient if WebGL is unavailable. It respects "reduce motion".
- three.js (v0.160.0) loads from the jsDelivr CDN via the import map in `index.html`.
