/* Chiro Wellness — booking form
 * Talks to the Google Apps Script in /google-apps-script, which reads and
 * writes Dr. Venter's Google Calendar. Without a URL it runs in demo mode.
 */
(function () {
  "use strict";

  var C = window.CHIRO_CONFIG;
  var LIVE = !!(C.APPS_SCRIPT_URL && C.APPS_SCRIPT_URL.trim());
  var TZ = C.clinic.timeZone;
  var DAY_KEYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };

  var form = $("#booking-form");
  var state = { step: 1, visit: "new", service: "", date: "", time: "", cache: {}, request: 0 };

  /* ---------------------------------------------------------------- */
  /* Date helpers. Dates are "YYYY-MM-DD" strings in clinic time.      */
  /* ---------------------------------------------------------------- */
  function todayInClinic() {
    var parts = new Intl.DateTimeFormat("en-US", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date())
      .reduce(function (acc, p) { acc[p.type] = p.value; return acc; }, {});
    return parts.year + "-" + parts.month + "-" + parts.day;
  }
  function addDays(dateStr, n) {
    var d = new Date(dateStr + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function isBookable(dateStr) {
    var only = C.bookableDates || [];
    return !only.length || only.indexOf(dateStr) !== -1;
  }
  function utcNoon(dateStr) { return new Date(dateStr + "T12:00:00Z"); }
  function weekdayKey(dateStr) { return DAY_KEYS[utcNoon(dateStr).getUTCDay()]; }
  function fmt(dateStr, opts) {
    return new Intl.DateTimeFormat("en-GB", Object.assign({ timeZone: "UTC" }, opts)).format(utcNoon(dateStr));
  }
  function slotEpoch(dateStr, time) { return Date.parse(dateStr + "T" + time + ":00" + C.clinic.utcOffset); }
  function toMinutes(t) { var p = t.split(":"); return +p[0] * 60 + +p[1]; }
  function toHHMM(m) { return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); }
  function pretty12(t) {
    var m = toMinutes(t), h = Math.floor(m / 60), mm = String(m % 60).padStart(2, "0");
    return { time: ((h + 11) % 12 + 1) + ":" + mm, ampm: h < 12 ? "am" : "pm" };
  }
  function longDate(dateStr) { return fmt(dateStr, { weekday: "long", day: "numeric", month: "long" }); }
  function ageFrom(dob) {
    var t = todayInClinic().split("-").map(Number), b = dob.split("-").map(Number);
    var age = t[0] - b[0];
    if (t[1] < b[1] || (t[1] === b[1] && t[2] < b[2])) age--;
    return age;
  }
  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------------------------------------------------------------- */
  /* Static content from config                                       */
  /* ---------------------------------------------------------------- */
  function fillClinicDetails() {
    var cl = C.clinic;
    var wa = "https://wa.me/" + cl.whatsapp + "?text=" +
      encodeURIComponent("Hi Chiro Wellness, I'd like to ask about an appointment.");
    $$("[data-whatsapp]").forEach(function (a) { a.href = wa; a.target = "_blank"; a.rel = "noopener"; });
    $$("[data-text='address']").forEach(function (el) { el.textContent = cl.address; });
    $$("[data-tel]").forEach(function (a) {
      var num = cl[a.getAttribute("data-tel")];
      a.href = "tel:" + num.replace(/[^+0-9]/g, "");
      if (!a.classList.contains("nav-phone") || !a.textContent.trim()) a.textContent = num;
    });
    $$("[data-mail]").forEach(function (a) { a.href = "mailto:" + cl.email; a.textContent = cl.email; });
    var q = encodeURIComponent(cl.address);
    $("#directions").href = "https://www.google.com/maps/dir/?api=1&destination=" + q;
    $("#map").src = "https://maps.google.com/maps?q=" + q + "&z=15&output=embed";
    $("#year").textContent = new Date().getFullYear();

    // Opening hours, grouping consecutive days with identical times.
    var order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    var label = function (ranges) {
      return ranges.length ? ranges.map(function (r) { return r[0] + "–" + r[1]; }).join(", ") : "Closed";
    };
    var rows = [];
    order.forEach(function (d) {
      var text = label(C.hours[d] || []);
      var last = rows[rows.length - 1];
      if (last && last.text === text) last.to = d; else rows.push({ from: d, to: d, text: text });
    });
    $("#hours").innerHTML = rows.map(function (r) {
      return "<div><dt>" + r.from + (r.to !== r.from ? " – " + r.to : "") + "</dt><dd>" + r.text + "</dd></div>";
    }).join("");
  }

  function renderOptions() {
    $("#visit-options").innerHTML = Object.keys(C.visitTypes).map(function (key) {
      var v = C.visitTypes[key];
      return '<label class="option"><input type="radio" name="visit" value="' + key + '"' + (key === state.visit ? " checked" : "") + ">" +
        '<span class="option-body"><strong>' + escapeHTML(v.label) + "</strong><small>" + escapeHTML(v.detail) + "</small>" +
        '<span class="mins">' + v.minutes + " min</span></span></label>";
    }).join("");

    $("#service-options").innerHTML = C.services.map(function (s) {
      return '<label class="chip"><input type="radio" name="service" value="' + escapeHTML(s) + '"><span>' + escapeHTML(s) + "</span></label>";
    }).join("");

    $("#area-options").innerHTML = C.bodyAreas.map(function (a) {
      return '<label class="chip"><input type="checkbox" name="areas" value="' + escapeHTML(a) + '"><span>' + escapeHTML(a) + "</span></label>";
    }).join("");
  }

  /* ---------------------------------------------------------------- */
  /* Availability                                                     */
  /* ---------------------------------------------------------------- */
  function demoAvailability(visit) {
    var minutes = C.visitTypes[visit].minutes;
    var earliest = Date.now() + C.minNoticeHours * 3600000;
    var start = todayInClinic();
    var out = {};
    for (var d = 0; d < C.daysToShow; d++) {
      var date = addDays(start, d);
      var slots = [];
      if (!isBookable(date)) { out[date] = slots; continue; }
      (C.hours[weekdayKey(date)] || []).forEach(function (r) {
        for (var m = toMinutes(r[0]); m + minutes <= toMinutes(r[1]); m += C.slotStepMinutes) {
          var t = toHHMM(m);
          if (slotEpoch(date, t) < earliest) continue;
          // Pretend roughly a third of the diary is already booked.
          var h = 0, key = date + t + visit;
          for (var i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
          if (h % 10 < 3) continue;
          slots.push(t);
        }
      });
      out[date] = slots;
    }
    return new Promise(function (resolve) { setTimeout(function () { resolve(out); }, 450); });
  }

  function liveAvailability(visit) {
    var url = C.APPS_SCRIPT_URL + "?action=availability&visit=" + encodeURIComponent(visit) +
      "&from=" + todayInClinic() + "&days=" + C.daysToShow;
    return fetch(url, { method: "GET", redirect: "follow" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (j) { if (!j.ok) throw new Error(j.message || "Unavailable"); return j.dates; });
  }

  function loadAvailability(force) {
    var visit = state.visit;
    var id = ++state.request;
    if (!force && state.cache[visit]) { renderDates(); return; }
    if (force) delete state.cache[visit];
    $("#date-strip").innerHTML = '<div class="skeleton">' + "<i></i>".repeat(8) + "</div>";
    $("#time-slots").innerHTML = '<div class="skeleton slots">' + "<i></i>".repeat(6) + "</div>";
    $("#time-note").textContent = "";
    (LIVE ? liveAvailability(visit) : demoAvailability(visit))
      .then(function (dates) {
        if (id !== state.request) return; // a newer request superseded this one
        state.cache[visit] = dates;
        renderDates();
      })
      .catch(function (err) {
        if (id !== state.request) return;
        console.error(err);
        $("#date-strip").innerHTML = "";
        $("#time-slots").innerHTML =
          '<div class="slot-error">We couldn’t load the clinic calendar just now. Please try again, or ' +
          '<a href="' + $("[data-whatsapp]").href + '" target="_blank" rel="noopener">WhatsApp us</a> to book.' +
          '<br><button type="button" class="btn btn-dark btn-sm" id="retry">Try again</button></div>';
        $("#retry").addEventListener("click", function () { loadAvailability(true); });
      });
  }

  function renderDates() {
    var dates = state.cache[state.visit] || {};
    var strip = $("#date-strip");
    var start = todayInClinic();
    var html = "";
    var firstOpen = "";
    for (var d = 0; d < C.daysToShow; d++) {
      var date = addDays(start, d);
      if (!isBookable(date)) continue;
      var open = (C.hours[weekdayKey(date)] || []).length > 0 || (dates[date] && dates[date].length);
      if (!open) continue; // closed days are left out entirely
      var count = (dates[date] || []).length;
      if (count && !firstOpen) firstOpen = date;
      var note = count ? count + (count === 1 ? " slot" : " slots") : (d === 0 ? "No times" : "Full");
      var label = longDate(date) + ", " + (count ? count + " times available" : "fully booked");
      html += '<label class="date-chip"><input type="radio" name="date" value="' + date + '"' +
        (count ? "" : " disabled") + ' aria-label="' + label + '">' +
        "<span><small>" + (d === 0 ? "Today" : fmt(date, { weekday: "short" })) + "</small>" +
        "<strong>" + fmt(date, { day: "numeric" }) + "</strong>" +
        "<small>" + fmt(date, { month: "short" }) + "</small><i>" + note + "</i></span></label>";
    }
    strip.innerHTML = html || '<div class="slot-empty">Online booking is closed at the moment. Please WhatsApp or call us to book.</div>';
    // Only show the scroll arrows when there are more dates than fit.
    var overflow = strip.scrollWidth > strip.clientWidth + 4;
    $$(".strip-nav").forEach(function (b) { b.hidden = !overflow; });

    if (!(dates[state.date] && dates[state.date].length)) { state.date = firstOpen; }
    if (state.date) {
      var input = $('input[name="date"][value="' + state.date + '"]', strip);
      if (input) {
        input.checked = true;
        var chip = input.closest(".date-chip");
        strip.scrollLeft = Math.max(0, chip.offsetLeft - strip.offsetLeft - 16);
      }
    }
    renderTimes();
  }

  function renderTimes() {
    var box = $("#time-slots");
    var slots = ((state.cache[state.visit] || {})[state.date]) || [];
    if (slots.indexOf(state.time) === -1) state.time = "";
    $("#time-note").textContent = state.date ? "· " + longDate(state.date) : "";
    if (!state.date) { box.innerHTML = '<div class="slot-empty">Choose a date to see available times.</div>'; updateSummary(); return; }
    if (!slots.length) { box.innerHTML = '<div class="slot-empty">No times left on this day. Please pick another date.</div>'; updateSummary(); return; }

    var groups = { Morning: [], Afternoon: [] };
    slots.forEach(function (t) { (toMinutes(t) < 720 ? groups.Morning : groups.Afternoon).push(t); });
    box.innerHTML = Object.keys(groups).filter(function (g) { return groups[g].length; }).map(function (g) {
      return '<div class="slot-group"><p class="slot-group-label">' + g + '</p><div class="slot-grid">' +
        groups[g].map(function (t) {
          var p = pretty12(t);
          return '<label class="slot"><input type="radio" name="time" value="' + t + '"' + (t === state.time ? " checked" : "") +
            "><span>" + p.time + "<small>" + p.ampm + "</small></span></label>";
        }).join("") + "</div></div>";
    }).join("");
    updateSummary();
  }

  /* ---------------------------------------------------------------- */
  /* Summary panel                                                    */
  /* ---------------------------------------------------------------- */
  function setSum(key, value) {
    var el = $('[data-sum="' + key + '"]');
    el.textContent = value || "—";
    el.classList.toggle("is-empty", !value);
  }
  function updateSummary() {
    var v = C.visitTypes[state.visit];
    setSum("visit", v ? v.label + " · " + v.minutes + " min" : "");
    setSum("service", state.service);
    setSum("date", state.date ? fmt(state.date, { weekday: "short", day: "numeric", month: "short" }) : "");
    if (state.time) {
      var p = pretty12(state.time), end = pretty12(toHHMM(toMinutes(state.time) + v.minutes));
      setSum("time", p.time + " " + p.ampm + " – " + end.time + " " + end.ampm);
    } else setSum("time", "");
  }

  /* ---------------------------------------------------------------- */
  /* Steps and validation                                             */
  /* ---------------------------------------------------------------- */
  var MESSAGES = {
    reasonDetails: "Please tell us a little about why you’re coming in.",
    firstName: "Please enter a first name.",
    lastName: "Please enter a surname.",
    dob: "Please enter a valid date of birth.",
    phone: "Please enter a valid phone number, e.g. +267 71 234 567.",
    email: "Please enter a valid email address.",
    guardian: "Please enter the name of a parent or guardian.",
    concerns: "Please tell us a little about your ailments or previous injuries."
  };

  function setGroupError(name, msg) {
    var g = $('[data-group="' + name + '"] .group-error');
    if (g) g.textContent = msg || "";
  }

  function validateField(input) {
    var field = input.closest(".field");
    var err = field && $(".field-error", field);
    var valid = input.checkValidity();
    if (valid && input.required && input.type !== "checkbox" && !input.value.trim()) valid = false;
    if (input.id === "phone" && valid) valid = input.value.replace(/\D/g, "").length >= 7;
    if (field) field.classList.toggle("is-invalid", !valid);
    if (err) err.textContent = valid ? "" : (MESSAGES[input.name] || input.validationMessage);
    input.setAttribute("aria-invalid", valid ? "false" : "true");
    return valid;
  }

  function validateStep(n) {
    if (n === 1) {
      setGroupError("service", state.service ? "" : "Please choose the main reason for your visit.");
      setGroupError("date", state.date ? "" : "Please choose a date.");
      setGroupError("time", state.time ? "" : "Please choose a time.");
      var reason = $("#reasonDetails");
      var reasonOk = validateField(reason);
      var target = !state.service ? $('[data-group="service"]')
        : !reasonOk ? reason
        : !state.date ? $('[data-group="date"]')
        : !state.time ? $('[data-group="time"]') : null;
      if (!target) return true;
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      if (target === reason) reason.focus({ preventScroll: true });
      return false;
    }
    var section = $('[data-step="' + n + '"]');
    var inputs = $$("input[required], textarea[required], select[required]", section)
      .filter(function (i) { return !i.closest("[hidden]"); });
    var bad = inputs.filter(function (i) { return i.type !== "checkbox" && !validateField(i); });
    if (n === 3) {
      var consent = $("#consent");
      $(".consent-error").textContent = consent.checked ? "" : "Please tick the box to agree before booking.";
      if (!consent.checked) bad.push(consent);
    }
    if (bad.length) { bad[0].focus(); return false; }
    return true;
  }

  function goTo(n) {
    state.step = n;
    $$(".step").forEach(function (s) { s.hidden = +s.dataset.step !== n; });
    $$("[data-step-tab]").forEach(function (t) {
      var k = +t.dataset.stepTab;
      t.classList.toggle("is-active", k === n);
      t.classList.toggle("is-done", k < n);
      if (k === n) t.setAttribute("aria-current", "step"); else t.removeAttribute("aria-current");
    });
    var title = $('[data-step="' + n + '"] .step-title');
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(function () { title.focus({ preventScroll: true }); }, 50);
  }

  /* ---------------------------------------------------------------- */
  /* Submit                                                           */
  /* ---------------------------------------------------------------- */
  function payload() {
    var f = form.elements;
    return {
      visit: state.visit,
      service: state.service,
      reasonDetails: f.reasonDetails.value.trim(),
      date: state.date,
      time: state.time,
      firstName: f.firstName.value.trim(),
      lastName: f.lastName.value.trim(),
      dob: f.dob.value,
      gender: f.gender.value,
      phone: f.phone.value.trim(),
      email: f.email.value.trim(),
      medicalAid: f.medicalAid.value.trim(),
      guardian: $("#guardian-field").hidden ? "" : f.guardian.value.trim(),
      areas: $$('input[name="areas"]:checked').map(function (i) { return i.value; }),
      concerns: f.concerns.value.trim(),
      consent: f.consent.checked,
      website: f.website.value
    };
  }

  function sendBooking(data) {
    if (!LIVE) {
      return new Promise(function (resolve) {
        setTimeout(function () { resolve({ ok: true, ref: "DEMO-" + Math.random().toString(36).slice(2, 6).toUpperCase() }); }, 1100);
      });
    }
    // text/plain keeps this a "simple" request, which Apps Script accepts without CORS preflight.
    return fetch(C.APPS_SCRIPT_URL, {
      method: "POST",
      redirect: "follow",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(data)
    }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }

  function onSubmit(e) {
    e.preventDefault();
    if (state.step !== 3) return;
    if (!validateStep(3)) return;
    var btn = $("#submit-btn");
    var errBox = $("#form-error");
    errBox.hidden = true;
    btn.disabled = true;
    btn.classList.add("is-loading");
    $(".btn-label", btn).textContent = "Booking…";

    var data = payload();
    sendBooking(data)
      .then(function (res) {
        if (res.ok) return showSuccess(data, res);
        if (res.code === "SLOT_TAKEN") {
          state.time = "";
          loadAvailability(true);
          goTo(1);
          setGroupError("time", res.message);
          return;
        }
        throw new Error(res.message || "Booking failed");
      })
      .catch(function (err) {
        console.error(err);
        errBox.innerHTML = escapeHTML(err && err.message && !/HTTP|fetch|network/i.test(err.message)
          ? err.message
          : "We couldn’t complete your booking. Please check your connection and try again.") +
          ' Or <a href="' + $("[data-whatsapp]").href + '" target="_blank" rel="noopener">book on WhatsApp</a>.';
        errBox.hidden = false;
      })
      .then(function () {
        btn.disabled = false;
        btn.classList.remove("is-loading");
        $(".btn-label", btn).textContent = "Book appointment";
      });
  }

  function showSuccess(data, res) {
    var p = pretty12(data.time);
    var invited = res.invited !== false;
    $('[data-success="name"]').textContent = data.firstName;
    $('[data-success="when"]').textContent = longDate(data.date) + " at " + p.time + " " + p.ampm;
    $('[data-success="invite"]').textContent = invited
      ? "Open the calendar invitation sent to " + data.email + " and tap Yes."
      : "The clinic will contact you on " + data.phone + " to confirm.";
    $('[data-success="sub"]').textContent = LIVE
      ? "Not in your inbox within a few minutes? Check your spam folder, or call " + C.clinic.phone + "."
      : "Demo mode: nothing was saved or sent. Once connected, Dr. Venter and the patient both receive Google Calendar invitations.";
    $('[data-success="ref"]').textContent = res.ref;

    $$(".step").forEach(function (s) { s.hidden = true; });
    $(".stepper").hidden = true;
    $("#demo-banner").hidden = true;
    $("#success").hidden = false;
    $$("[data-step-tab]").forEach(function (t) { t.classList.add("is-done"); });
    delete state.cache[state.visit]; // that slot is now taken
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(function () { $("#success-title").focus({ preventScroll: true }); }, 50);
  }

  function resetForm() {
    form.reset();
    state.service = ""; state.time = ""; state.date = ""; state.visit = "new";
    $$(".field").forEach(function (f) { f.classList.remove("is-invalid"); });
    $$(".field-error, .group-error").forEach(function (e) { e.textContent = ""; });
    $("#guardian-field").hidden = true;
    $$("[data-counter-for]").forEach(function (c) { c.textContent = "0 / " + $("#" + c.dataset.counterFor).maxLength; });
    $("#success").hidden = true;
    $(".stepper").hidden = false;
    $("#demo-banner").hidden = LIVE;
    loadAvailability();
    goTo(1);
  }

  /* ---------------------------------------------------------------- */
  /* Wiring                                                           */
  /* ---------------------------------------------------------------- */
  function bind() {
    form.addEventListener("change", function (e) {
      var t = e.target;
      if (t.name === "visit") { state.visit = t.value; updateSummary(); loadAvailability(); }
      if (t.name === "service") { state.service = t.value; setGroupError("service", ""); updateSummary(); }
      if (t.name === "date") { state.date = t.value; state.time = ""; setGroupError("date", ""); renderTimes(); }
      if (t.name === "time") { state.time = t.value; setGroupError("time", ""); updateSummary(); }
      if (t.id === "consent" && t.checked) $(".consent-error").textContent = "";
      if (t.id === "dob" && t.value) {
        var minor = ageFrom(t.value) < 18;
        $("#guardian-field").hidden = !minor;
        $("#guardian").required = minor;
      }
    });

    form.addEventListener("blur", function (e) {
      var t = e.target;
      if (t.matches(".field input[required], .field textarea[required]") && t.value) validateField(t);
    }, true);
    form.addEventListener("input", function (e) {
      var f = e.target.closest(".field.is-invalid");
      if (f) validateField(e.target);
      var counter = $('[data-counter-for="' + e.target.id + '"]');
      if (counter) counter.textContent = e.target.value.length + " / " + e.target.maxLength;
    });

    $$("[data-next]").forEach(function (b) {
      b.addEventListener("click", function () { if (validateStep(state.step)) goTo(state.step + 1); });
    });
    $$("[data-back]").forEach(function (b) { b.addEventListener("click", function () { goTo(state.step - 1); }); });
    $$("[data-strip]").forEach(function (b) {
      b.addEventListener("click", function () {
        var strip = $("#date-strip");
        strip.scrollBy({ left: +b.dataset.strip * strip.clientWidth * 0.8, behavior: "smooth" });
      });
    });
    form.addEventListener("submit", onSubmit);
    $("#book-another").addEventListener("click", resetForm);

    var header = $(".site-header");
    var onScroll = function () { header.classList.toggle("is-solid", window.scrollY > 40); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  function init() {
    fillClinicDetails();
    renderOptions();
    $("#dob").max = todayInClinic();
    var only = C.bookableDates || [];
    if (only.length) {
      $("#date-note").textContent = "· Online booking is open for " +
        only.map(function (d) { return fmt(d, { weekday: "long", day: "numeric", month: "long" }); }).join(", ") + " only";
    }
    $("#demo-banner").hidden = LIVE;
    bind();
    updateSummary();
    loadAvailability();
  }

  init();
})();
