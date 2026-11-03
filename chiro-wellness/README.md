# Chiro Wellness — online booking page

A single-page, hostable booking site for **Chiropractic Wellness Clinic Botswana** (Dr. Machere Venter).
It has a three.js 3D hero, a three-step booking form, and a live connection to Dr. Venter's
**Google Calendar** through a free Google Apps Script. No server or database is needed.

```
chiro-wellness/
├── index.html                  the page
├── assets/
│   ├── config.js               ← the only file you edit to go live
│   ├── styles.css
│   ├── booking.js              booking form logic
│   └── spine.js                three.js 3D spine animation
└── google-apps-script/
    ├── Code.gs                 calendar backend (paste into Apps Script)
    └── appsscript.json         optional manifest (time zone, web app settings)
```

## How it works

1. A patient picks a **visit type** (new 60 min / follow-up 30 min), a **reason**, a **date** and a **time**.
   The free times come live from her calendar: opening hours minus anything already booked.
2. They enter **patient details**: name, date of birth, gender (optional), mobile, email and medical aid (optional).
   If the patient is under 18, the form asks for a parent or guardian's name.
3. They tap **where they feel discomfort** and describe their **ailments or previous injuries** in a free-text box, then consent and confirm.

When they confirm, the Apps Script:
- re-checks the slot is still free (so two people can't take the same time),
- creates an event on her Google Calendar with all the patient details in the description,
- emails the reception address a full summary,
- emails the patient a confirmation (date, time and address only, no health details),
- optionally logs the booking to a Google Sheet.

Until the script is connected, the page runs in **demo mode**: it shows sample times and a yellow banner, and saves nothing.

## Preview it

Double-click `index.html`, or serve the folder:

```bash
cd chiro-wellness && python3 -m http.server 8000   # then open http://localhost:8000
```

## Connect Google Calendar (about 10 minutes)

Do this **signed in to Dr. Venter's Google account**, the one whose calendar should take the bookings.

1. Go to <https://script.google.com> and click **New project**. Name it "Chiro Wellness Bookings".
2. Delete the sample code, then paste in the whole of `google-apps-script/Code.gs`.
3. At the top of the file, check `SETTINGS`:
   - `CALENDAR_ID`: leave as `'primary'` for her main calendar, or paste a Calendar ID
     (Google Calendar → Settings → pick the calendar → *Integrate calendar* → *Calendar ID*).
   - `HOURS`: **confirm her real opening hours**. The ones included are placeholders.
   - `DURATIONS`, `MIN_NOTICE_HOURS`, `BUFFER_MINUTES` as preferred.
   - `SHEET_ID` (optional): the ID from a Google Sheet URL, to keep a booking log.
4. Click ⚙ **Project Settings** and set the time zone to **(GMT+02:00) Gaborone**.
5. Back in the editor, choose `testSetup` from the function dropdown and click **Run**.
   Approve the permissions. Google will say *"Google hasn't verified this app"*: click **Advanced → Go to Chiro Wellness Bookings**.
   This is normal for your own scripts. The log should list her calendar name and some free slots.
6. Click **Deploy → New deployment → Web app**:
   - *Execute as*: **Me**
   - *Who has access*: **Anyone**
   Click **Deploy** and copy the **Web app URL** (it ends in `/exec`).
7. Open `assets/config.js` and paste it in:
   ```js
   APPS_SCRIPT_URL: "https://script.google.com/macros/s/AKfy.../exec",
   ```
8. Reload the page. The demo banner disappears and the times shown are her real availability.

**Changing the script later:** after editing `Code.gs`, go to **Deploy → Manage deployments → ✏️ Edit →
Version: New version → Deploy**. The URL stays the same. Saving alone does not update the live version.

**Blocking time off:** anything on her calendar blocks those times. An **all-day event** (e.g. "Leave")
blocks the whole day. Events she has **declined** are ignored.

## Host it

It's plain static files. Any of these work:

- **Netlify Drop**: drag the `chiro-wellness` folder onto <https://app.netlify.com/drop>. You get free HTTPS and can add `chirowellness.co.bw` later.
- **GitHub Pages / Vercel / Cloudflare Pages**: point them at this folder.
- **Any cPanel web host**: upload the folder contents to `public_html`.

## Customising

| What | Where |
|---|---|
| Clinic phone, email, address, WhatsApp number | `assets/config.js` → `clinic` |
| Visit types and their lengths | `assets/config.js` → `visitTypes` **and** `Code.gs` → `DURATIONS` (keys must match) |
| Reasons for visit and body-area tags | `assets/config.js` → `services`, `bodyAreas` |
| Opening hours shown in the footer | `assets/config.js` → `hours` |
| Opening hours used for real bookings | `Code.gs` → `HOURS` (keep the two in sync) |
| Colours and fonts | top of `assets/styles.css` (`:root` variables, per the brand spec in the BRD) |

## Good to know

- **Privacy.** Patient details are stored only in Dr. Venter's Google account (Calendar, Gmail and optionally a Sheet).
  The public web app URL only reveals which time slots are free, never who booked them. Turn on
  2-Step Verification for that Google account, since it now holds patient health information.
- **Email limits.** A free Gmail account can send about 100 emails a day from Apps Script. Each booking sends 2,
  so roughly 50 bookings a day. A Google Workspace account allows far more.
- **Sender.** Confirmation emails come from her Google account's address, named "Chiro Wellness",
  with replies going to the reception email.
- **Spam.** The form has a hidden honeypot field, and the script validates every field server-side.
- **3D performance.** The hero uses about 5 WebGL draw calls, pauses when scrolled out of view, lowers its
  resolution automatically on slow phones, and shows a static gradient if WebGL is unavailable.
  It respects the device's "reduce motion" setting.
- three.js (v0.160.0) loads from the jsDelivr CDN via the import map in `index.html`.
