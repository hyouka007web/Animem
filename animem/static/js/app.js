/* Animem – Frontend. Reines JavaScript ohne Build-Schritt; alle Widgets hängen an data-Attributen. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "value") node.value = v;
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) if (c != null) node.append(c.nodeType ? c : document.createTextNode(c));
    return node;
  }

  async function api(method, url, body) {
    try {
      const res = await fetch(url, {
        method,
        credentials: "same-origin",
        headers: body !== undefined ? { "Content-Type": "application/json" } : {},
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      const data = await res.json().catch(() => null);
      return { ok: res.ok, status: res.status, data };
    } catch {
      return { ok: false, status: 0, data: { error: "Keine Verbindung zum Server." } };
    }
  }
  const errText = (r) => (r.data && r.data.error) || "Etwas ist schiefgelaufen.";

  function toast(message, kind = "") {
    const t = el("div", { class: `toast ${kind}`, role: "status", text: message });
    document.body.append(t);
    setTimeout(() => t.remove(), 3200);
  }

  function say(node, message, kind = "") {
    if (!node) return;
    node.textContent = message || "";
    node.classList.remove("err", "good");
    if (kind) node.classList.add(kind);
  }

  // ---------------------------------------------------------------- Anmeldung / Registrierung
  $$("[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const kind = form.dataset.authForm;
      const msg = $("[data-msg]", form);
      const btn = $("button[type=submit]", form);
      const data = Object.fromEntries(new FormData(form).entries());
      const next = data.next || "/";
      delete data.next;
      if (kind === "login" && (!data.email || !data.password)) return say(msg, "Bitte E-Mail und Passwort eingeben.", "err");
      btn.disabled = true;
      say(msg, "");
      const url = { login: "/api/auth/login", register: "/api/auth/register", totp: "/api/auth/totp" }[kind];
      const r = await api("POST", url, data);
      btn.disabled = false;
      if (!r.ok) return say(msg, errText(r), "err");
      if (r.data && r.data.requiresTotp) {
        location.href = "/login?step=totp&next=" + encodeURIComponent(next);
        return;
      }
      location.href = kind === "register" ? "/" : next;
    });
  });

  // ---------------------------------------------------------------- Ein/Aus-Buttons (Watchlist, Abo)
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-toggle]");
    if (!btn) return;
    btn.disabled = true;
    const on = btn.dataset.on === "1";
    const r = await api(on ? "DELETE" : "POST", btn.dataset.toggle, JSON.parse(btn.dataset.body));
    btn.disabled = false;
    if (!r.ok) return toast(errText(r), "err");
    btn.dataset.on = on ? "0" : "1";
    btn.classList.toggle("on", !on);
    btn.textContent = on ? btn.dataset.labelOff : btn.dataset.labelOn;
  });

  // ---------------------------------------------------------------- Bewertung & Rezensionen
  const TARGET_KEY = { SEASON: "seasonId", MOVIE: "movieId", EPISODE: "episodeId" };

  $$("[data-rating]").forEach((box) => {
    const buttons = $$(".stars button", box);
    const paint = () => {
      const v = Number(box.dataset.value) || 0;
      buttons.forEach((b) => b.classList.toggle("on", Number(b.dataset.v) <= v));
    };
    buttons.forEach((b) => b.addEventListener("click", () => { box.dataset.value = b.dataset.v; paint(); }));
    // Wird vom Staffel-Umschalter benutzt: Widget auf eine andere Staffel umstellen
    box.addEventListener("rating:set", (e) => {
      box.dataset.id = e.detail.id;
      box.dataset.value = e.detail.value || 0;
      $("textarea", box).value = e.detail.comment || "";
      const title = $("[data-rating-title]", box);
      if (title && e.detail.title) title.textContent = e.detail.title;
      say($("[data-msg]", box), "");
      paint();
    });
    $("[data-save]", box).addEventListener("click", async () => {
      const msg = $("[data-msg]", box);
      const value = Number(box.dataset.value) || 0;
      if (!value) return say(msg, "Bitte zuerst eine Bewertung von 1 bis 10 wählen.", "err");
      const comment = $("textarea", box).value;
      const r = await api("POST", "/api/ratings", {
        targetType: box.dataset.target, [TARGET_KEY[box.dataset.target]]: box.dataset.id, value, comment,
      });
      if (!r.ok) return say(msg, errText(r), "err");
      say(msg, "Gespeichert ✓", "good");
      document.dispatchEvent(new CustomEvent("ratings:saved", { detail: { id: box.dataset.id, value, comment, avg: r.data.avg, count: r.data.count } }));
      document.dispatchEvent(new CustomEvent("reviews:reload"));
    });
  });

  $$("[data-reviews]").forEach((box) => {
    const list = $("[data-list]", box);
    const load = async () => {
      const r = await api("GET", `/api/ratings?targetType=${box.dataset.target}&targetId=${encodeURIComponent(box.dataset.id)}`);
      list.replaceChildren();
      if (!r.ok) return list.append(el("p", { class: "muted small", text: "Bewertungen konnten nicht geladen werden." }));
      if (!r.data.length) return list.append(el("p", { class: "muted small", text: "Noch keine Kommentare." }));
      for (const rv of r.data) {
        const name = rv.displayName || rv.username || "Gelöschter Nutzer";
        list.append(el("article", { class: "review" },
          el("div", { class: "row small", style: "gap:8px;margin-bottom:6px" },
            rv.avatarUrl ? el("img", { class: "avatar", src: rv.avatarUrl, alt: "", referrerpolicy: "no-referrer" }) : el("span", { class: "avatar" }),
            rv.username ? el("a", { class: "mention", href: `/u/${rv.username}`, text: name, style: "font-weight:600" }) : el("span", { text: name }),
            el("span", { class: "star", text: `★ ${rv.value}/10` }),
            el("span", { class: "tiny muted", text: new Date(rv.createdAt).toLocaleDateString("de-DE") })),
          el("p", { class: "small pre muted-2", text: rv.comment })));
      }
    };
    document.addEventListener("reviews:reload", load);
    load();
  });

  // Serienseite: Staffeln umschalten (Bild, Folgen, Bewertung und Kommentare wechseln mit)
  const sp = $("[data-series-page]");
  if (sp && $("#season-data")) {
    const data = JSON.parse($("#season-data").textContent);
    const tabs = $$("[data-season]", sp), panels = $$("[data-panel]", sp);
    const cover = $("#season-cover"), meta = $("#season-meta");
    const showMeta = (s) => {
      meta.replaceChildren();
      if (s.avg != null && s.count) {
        meta.append(el("span", { class: "star", text: "★" }), ` ${Number(s.avg).toFixed(1)} · ${s.count} Bewertungen${data.length > 1 ? ` (Staffel ${s.number})` : ""}`);
      } else meta.append("Noch keine Bewertung");
    };
    const select = (n, push) => {
      const s = data.find((x) => x.number === n);
      if (!s) return;
      tabs.forEach((t) => t.classList.toggle("active", Number(t.dataset.season) === n));
      panels.forEach((p) => { p.hidden = Number(p.dataset.panel) !== n; });
      if (cover.getAttribute("src") !== s.cover) {
        cover.classList.add("swap");
        setTimeout(() => { cover.src = s.cover; cover.classList.remove("swap"); }, 180);
      }
      showMeta(s);
      const rating = $("[data-rating]", sp);
      if (rating) rating.dispatchEvent(new CustomEvent("rating:set", { detail: { id: s.id, value: s.myRating, comment: s.myComment, title: `Deine Bewertung · Staffel ${n}` } }));
      const rev = $("[data-reviews]", sp);
      if (rev) { rev.dataset.id = s.id; document.dispatchEvent(new CustomEvent("reviews:reload")); }
      if (push) history.replaceState(null, "", `?season=${n}`);
    };
    tabs.forEach((t) => t.addEventListener("click", (e) => { e.preventDefault(); select(Number(t.dataset.season), true); }));
    document.addEventListener("ratings:saved", (e) => {
      const s = data.find((x) => x.id === e.detail.id);
      if (!s) return;
      s.myRating = e.detail.value; s.myComment = e.detail.comment; s.avg = e.detail.avg; s.count = e.detail.count;
      showMeta(s);
    });
  }

  // ---------------------------------------------------------------- Sammlungen (Detailseiten)
  $$("[data-collections]").forEach((box) => {
    const field = box.dataset.field, id = box.dataset.id, msg = $("[data-msg]", box);
    const wire = (cb) => cb.addEventListener("change", async () => {
      const r = await api(cb.checked ? "POST" : "DELETE", "/api/collections/items", { collectionId: cb.dataset.col, [field]: id });
      if (!r.ok) { cb.checked = !cb.checked; say(msg, errText(r), "err"); } else say(msg, "");
    });
    $$("[data-col]", box).forEach(wire);
    $("[data-create]", box).addEventListener("click", async () => {
      const input = $("[data-newcol]", box);
      const title = input.value.trim();
      if (!title) return;
      const c = await api("POST", "/api/collections", { title });
      if (!c.ok) return say(msg, errText(c), "err");
      const add = await api("POST", "/api/collections/items", { collectionId: c.data.id, [field]: id });
      if (!add.ok) return say(msg, errText(add), "err");
      const cb = el("input", { type: "checkbox", "data-col": c.data.id, checked: true });
      $("[data-cols]", box).append(el("label", { class: "row small", style: "gap:8px" }, cb, " " + title));
      const none = $("[data-none]", box); if (none) none.remove();
      wire(cb);
      input.value = "";
      say(msg, "Sammlung angelegt ✓", "good");
    });
  });

  // Bibliothek: Sammlungen anlegen / löschen
  const newCol = $("[data-new-collection]");
  if (newCol) newCol.addEventListener("click", async () => {
    const input = $("#new-collection"), msg = $("#new-collection-msg");
    if (!input.value.trim()) return;
    const r = await api("POST", "/api/collections", { title: input.value.trim() });
    r.ok ? location.reload() : say(msg, errText(r), "err");
  });
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-delete-collection]");
    if (!btn || !confirm("Sammlung wirklich löschen?")) return;
    const r = await api("DELETE", `/api/collections/${btn.dataset.deleteCollection}`);
    r.ok ? location.reload() : toast(errText(r), "err");
  });

  // ---------------------------------------------------------------- Player: Sprache, Anbieter, Defekt-Meldung
  const authed = document.body.dataset.auth === "1";
  const saveLang = (lang) => {
    try { localStorage.setItem("animem_lang", lang); } catch { /* privater Modus */ }
    if (authed) api("PATCH", "/api/profile/preferences", { prefLang: lang });
  };
  const storedLang = () => { try { return localStorage.getItem("animem_lang") || ""; } catch { return ""; } };

  $$("[data-player]").forEach((box) => {
    const frame = $("iframe", box);
    if (!frame) return;
    const buttons = $$("[data-stream]", box), chips = $$("[data-lang-filter]", box), msg = $("[data-player-msg]", box);
    const tried = new Set();
    let filter = box.dataset.lang || "";
    const visible = () => buttons.filter((b) => !b.hidden);
    const current = () => buttons.find((b) => b.classList.contains("on"));
    const select = (b) => {
      if (!b || !/^https:\/\//i.test(b.dataset.stream)) return;
      frame.src = b.dataset.stream;
      buttons.forEach((x) => x.classList.toggle("on", x === b));
    };
    const best = (list) => list.find((b) => !b.classList.contains("dead") && !b.classList.contains("reported")) || list.find((b) => !b.classList.contains("dead")) || list[0];
    const applyFilter = (lang, remember) => {
      filter = lang;
      tried.clear();
      chips.forEach((c) => c.classList.toggle("on", c.dataset.langFilter === lang));
      buttons.forEach((b) => { b.hidden = !!lang && b.dataset.lang !== lang; });
      const cur = current();
      if (!cur || cur.hidden) select(best(visible()));
      say(msg, "");
      if (remember) saveLang(lang);
    };
    chips.forEach((c) => c.addEventListener("click", () => applyFilter(c.dataset.langFilter, true)));
    buttons.forEach((b) => b.addEventListener("click", () => select(b)));
    // Gemerkte Sprache anwenden (Konto: kommt vom Server; sonst aus dem Browser)
    const want = filter || storedLang();
    if (want && chips.some((c) => c.dataset.langFilter === want)) applyFilter(want, false);

    const next = (reason) => {
      const cur = current();
      if (cur) tried.add(cur.dataset.stream);
      const pool = visible().filter((b) => !tried.has(b.dataset.stream));
      const pick = pool.find((b) => !b.classList.contains("dead")) || pool[0];
      if (!pick) {
        const others = buttons.filter((b) => b.hidden && !tried.has(b.dataset.stream)).length;
        say(msg, others ? "Kein weiterer Anbieter in dieser Sprache. Wähle oben „Alle“, um andere Sprachen zu sehen." : "Kein weiterer Anbieter verfügbar.", "err");
        return false;
      }
      select(pick);
      say(msg, (reason ? reason + " " : "") + `Anbieter gewechselt: ${pick.firstChild.textContent.trim()}`, "good");
      return true;
    };
    $("[data-next-stream]", box).addEventListener("click", () => next(""));
    $("[data-report-stream]", box).addEventListener("click", async (e) => {
      const cur = current(), btn = e.currentTarget;   // currentTarget ist nach einem await nicht mehr gesetzt
      if (!cur) return;
      btn.disabled = true;
      const r = await api("POST", "/api/streams/report", { targetType: box.dataset.targetType, targetId: box.dataset.targetId, url: cur.dataset.stream });
      btn.disabled = false;
      if (!r.ok) return say(msg, errText(r), "err");
      cur.classList.add("reported");
      const thanks = r.data.already ? "Das hattest du schon gemeldet." : "Danke für die Meldung!";
      if (!next(thanks)) say(msg, thanks + " Leider gibt es keinen weiteren Anbieter.", "good");
    });
  });
  $$("[data-watch-tracker]").forEach((t) => {
    // Nach 3 Minuten Seitenbesuch gilt Folge/Film als gesehen (der Server prüft die Zeit zusätzlich).
    setTimeout(() => api("POST", "/api/watch/progress", { targetType: t.dataset.type, [t.dataset.key]: t.dataset.id }), 180000);
  });

  // ---------------------------------------------------------------- Suche
  const search = $("[data-live-search]");
  if (search) {
    search.focus(); search.setSelectionRange(search.value.length, search.value.length);
    let timer;
    search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => search.form.requestSubmit(), 650); });
  }

  // ---------------------------------------------------------------- Uploads (Bildfelder)
  function wireUpload(box) {
    const file = $("[data-file]", box), url = $("[data-url]", box);
    file.addEventListener("change", async () => {
      if (!file.files[0]) return;
      const fd = new FormData(); fd.append("file", file.files[0]);
      const note = el("span", { class: "tiny muted", text: " Lade hoch …" }); file.after(note);
      try {
        const res = await fetch("/api/uploads", { method: "POST", body: fd, credentials: "same-origin" });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error((data && data.error) || "Upload fehlgeschlagen.");
        url.value = data.url; note.textContent = " Hochgeladen ✓";
      } catch (err) { note.textContent = " " + err.message; note.style.color = "var(--danger)"; }
      file.value = "";
    });
  }
  $$("[data-upload-field]").forEach(wireUpload);

  // ---------------------------------------------------------------- Profil
  const pf = $("[data-profile-form]");
  if (pf) $("[data-save-profile]", pf).addEventListener("click", async () => {
    const msg = $("[data-msg]", pf);
    const r = await api("PATCH", "/api/profile", {
      displayName: $("#p-name").value, bio: $("#p-bio").value,
      avatarUrl: $("[data-upload-field=avatar] [data-url]").value, bannerUrl: $("[data-upload-field=banner] [data-url]").value,
    });
    r.ok ? location.reload() : say(msg, errText(r), "err");
  });

  $$("[data-favorites] [data-pick]").forEach((sel) => sel.addEventListener("change", async () => {
    const rank = Number(sel.closest("[data-rank]").dataset.rank), msg = $("[data-msg]", sel.parentElement);
    let r;
    if (!sel.value) r = await api("DELETE", "/api/profile/favorites", { rank });
    else {
      const [type, id] = sel.value.split(":");
      r = await api("POST", "/api/profile/favorites", { rank, [type === "series" ? "seriesId" : "movieId"]: id });
    }
    r.ok ? location.reload() : say(msg, errText(r), "err");
  }));

  // ---------------------------------------------------------------- Sicherheit (2FA, Sitzungen)
  const sec = $("[data-security]");
  if (sec) {
    const msg = $("[data-2fa-msg]", sec);
    const start = $("[data-2fa-start]", sec);
    if (start) start.addEventListener("click", async () => {
      const r = await api("POST", "/api/profile/totp");
      if (!r.ok) return say(msg, errText(r), "err");
      $("[data-2fa-setup]", sec).hidden = false;
      $("[data-secret]", sec).textContent = r.data.secret;
      $("[data-recovery]", sec).textContent = r.data.recoveryCodes.join("\n");
      $("[data-otp-link]", sec).href = r.data.otpauthUri;
      start.hidden = true; say(msg, "");
    });
    const enable = $("[data-2fa-enable]", sec);
    if (enable) enable.addEventListener("click", async () => {
      const r = await api("PATCH", "/api/profile/totp", { code: $("[data-2fa-code]", sec).value });
      r.ok ? location.reload() : say(msg, errText(r), "err");
    });
    const disable = $("[data-2fa-disable]", sec);
    if (disable) disable.addEventListener("click", async () => {
      const r = await api("DELETE", "/api/profile/totp", { code: $("[data-2fa-off-code]", sec).value });
      r.ok ? location.reload() : say(msg, errText(r), "err");
    });

    const list = $("[data-sessions]", sec);
    const loadSessions = async () => {
      const r = await api("GET", "/api/profile/sessions");
      list.replaceChildren();
      if (!r.ok) return list.append(el("p", { class: "muted small", text: "Sitzungen konnten nicht geladen werden." }));
      for (const s of r.data) {
        const row = el("div", { class: "list-item" },
          el("div", {},
            el("p", { class: "small", text: (s.userAgent || "Unbekanntes Gerät").slice(0, 70) + (s.current ? " (dieses Gerät)" : "") }),
            el("p", { class: "tiny muted", text: `${s.ip || "?"} · zuletzt aktiv ${new Date(s.lastSeen).toLocaleString("de-DE")}` })),
          s.current ? null : el("button", { class: "btn btn-ghost btn-sm", type: "button", text: "Abmelden" }));
        const b = $("button", row);
        if (b) b.addEventListener("click", async () => { await api("DELETE", `/api/profile/sessions?id=${encodeURIComponent(s.id)}`); loadSessions(); });
        list.append(row);
      }
    };
    $("[data-revoke-others]", sec).addEventListener("click", async () => {
      const r = await api("DELETE", "/api/profile/sessions?all=others");
      toast(r.ok ? `${r.data.revoked} Sitzung(en) abgemeldet.` : errText(r), r.ok ? "good" : "err");
      loadSessions();
    });
    loadSessions();
  }

  // ---------------------------------------------------------------- Forum & Support
  $$("[data-new-thread]").forEach((box) => $("[data-submit]", box).addEventListener("click", async () => {
    const msg = $("[data-msg]", box);
    const r = await api("POST", "/api/forum/threads", { categoryId: box.dataset.category, title: $("[data-title]", box).value, content: $("[data-content]", box).value });
    r.ok ? (location.href = `/forum/${box.dataset.slug}/${r.data.id}`) : say(msg, errText(r), "err");
  }));
  $$("[data-reply]").forEach((box) => $("[data-submit]", box).addEventListener("click", async () => {
    const r = await api("POST", "/api/forum/posts", { threadId: box.dataset.thread, content: $("[data-content]", box).value });
    r.ok ? location.reload() : say($("[data-msg]", box), errText(r), "err");
  }));
  $$("[data-new-ticket]").forEach((box) => $("[data-submit]", box).addEventListener("click", async () => {
    const r = await api("POST", "/api/tickets", { subject: $("[data-subject]", box).value, priority: $("[data-priority]", box).value, message: $("[data-message]", box).value });
    r.ok ? (location.href = `/support/${r.data.id}`) : say($("[data-msg]", box), errText(r), "err");
  }));
  $$("[data-ticket-reply]").forEach((box) => $("[data-submit]", box).addEventListener("click", async () => {
    const r = await api("POST", `/api/tickets/${box.dataset.ticket}/messages`, { content: $("[data-content]", box).value });
    r.ok ? location.reload() : say($("[data-msg]", box), errText(r), "err");
  }));
  $$("[data-ticket-status]").forEach((sel) => sel.addEventListener("change", async () => {
    const r = await api("PATCH", `/api/tickets/${sel.dataset.ticketStatus}`, { status: sel.value });
    toast(r.ok ? "Status geändert ✓" : errText(r), r.ok ? "good" : "err");
  }));

  // ---------------------------------------------------------------- Admin: generische Aktionen
  document.addEventListener("click", async (e) => {
    const del = e.target.closest("[data-delete]");
    if (del) {
      if (!confirm(del.dataset.confirm || "Wirklich löschen?")) return;
      const r = await api("DELETE", del.dataset.delete);
      return r.ok ? location.reload() : toast(errText(r), "err");
    }
    const mod = e.target.closest("[data-moderate]");
    if (mod) {
      const r = await api("PATCH", `/api/admin/forum/threads/${mod.dataset.moderate}`, { [mod.dataset.field]: mod.dataset.value === "true" });
      return r.ok ? location.reload() : toast(errText(r), "err");
    }
    const ban = e.target.closest("[data-ban]");
    if (ban) {
      const banned = ban.dataset.value === "true";
      if (banned && !confirm("Nutzer wirklich sperren? Alle Sitzungen werden beendet.")) return;
      const r = await api("PATCH", `/api/users/${ban.dataset.ban}/status`, { isBanned: banned });
      return r.ok ? location.reload() : toast(errText(r), "err");
    }
  });
  $$("[data-role-select]").forEach((sel) => {
    let previous = sel.value;
    sel.addEventListener("change", async () => {
      const r = await api("PATCH", `/api/users/${sel.dataset.roleSelect}/role`, { role: sel.value });
      if (!r.ok) { sel.value = previous; return toast(errText(r), "err"); }
      previous = sel.value; toast("Rolle geändert ✓", "good");
    });
  });
  $$("[data-new-category]").forEach((box) => $("[data-submit]", box).addEventListener("click", async () => {
    const r = await api("POST", "/api/admin/forum/categories", { name: $("[data-name]", box).value, description: $("[data-desc]", box).value });
    r.ok ? location.reload() : say($("[data-msg]", box), errText(r), "err");
  }));
  $$("[data-settings]").forEach((box) => {
    const msg = $("[data-msg]", box);
    const save = async (key, value) => {
      const r = await api("PATCH", "/api/admin/settings", { key, value });
      say(msg, r.ok ? "Gespeichert ✓" : errText(r), r.ok ? "good" : "err");
    };
    $$("input[type=checkbox][data-setting]", box).forEach((cb) => cb.addEventListener("change", async () => {
      await save(cb.dataset.setting, cb.checked);
    }));
    $("[data-save-name]", box).addEventListener("click", () => save("site_name", $("[data-setting=site_name]", box).value));
  });

  // ---------------------------------------------------------------- Benachrichtigungen & Einstellungen
  $$("[data-sub-settings]").forEach((box) => {
    const msg = $("[data-msg]", box);
    $$("[data-sub-lang]", box).forEach((c) => c.addEventListener("change", () => { $("input[value=custom]", box).checked = true; }));
    $("[data-save-sub]", box).addEventListener("click", async () => {
      const mode = ($("input[name=submode]:checked", box) || {}).value;
      const langs = $$("[data-sub-lang]:checked", box).map((c) => c.value);
      const r = await api("PATCH", "/api/subscriptions/settings", { seriesId: box.dataset.series, mode, langs });
      say(msg, r.ok ? "Gespeichert ✓" : errText(r), r.ok ? "good" : "err");
    });
  });

  const prefs = $("[data-prefs]");
  if (prefs) $("[data-save-prefs]", prefs).addEventListener("click", async () => {
    const msg = $("[data-msg]", prefs);
    const langs = $$("[data-pref-lang]:checked", prefs).map((c) => c.value);
    const r = await api("PATCH", "/api/profile/preferences", {
      notifyLangs: langs, notifyNewLangs: $("[data-pref-newlangs]", prefs).checked, prefLang: $("[data-pref-player]", prefs).value,
    });
    if (r.ok) { try { localStorage.setItem("animem_lang", $("[data-pref-player]", prefs).value); } catch { /* egal */ } }
    say(msg, r.ok ? (langs.length ? "Gespeichert ✓" : "Gespeichert ✓ – ohne Sprache bekommst du keine Meldungen.") : errText(r), r.ok ? "good" : "err");
  });

  const readAll = $("[data-notif-read-all]");
  if (readAll) readAll.addEventListener("click", async () => { const r = await api("POST", "/api/notifications/read", {}); r.ok ? location.reload() : toast(errText(r), "err"); });
  const clearRead = $("[data-notif-clear]");
  if (clearRead) clearRead.addEventListener("click", async () => { const r = await api("DELETE", "/api/notifications", {}); r.ok ? location.reload() : toast(errText(r), "err"); });

  // ---------------------------------------------------------------- Admin: Stream-Meldungen & Link-Check
  document.addEventListener("click", async (e) => {
    const act = e.target.closest("[data-report-action]");
    if (act) {
      if (act.dataset.confirm && !confirm(act.dataset.confirm)) return;
      const card = act.closest("[data-report]");
      const r = await api("PATCH", `/api/admin/reports/${card.dataset.report}`, { action: act.dataset.reportAction });
      return r.ok ? location.reload() : say($("[data-msg]", card), errText(r), "err");
    }
    const chk = e.target.closest("[data-check-url]");
    if (chk) {
      chk.disabled = true;
      const r = await api("POST", "/api/admin/streams/check", { url: chk.dataset.checkUrl });
      chk.disabled = false;
      const names = { OK: "Link funktioniert ✓", DEAD: "Link ist tot ✗", SUSPECT: "Fehler – beim nächsten Fehlschlag gilt der Link als tot", UNKNOWN: "Nicht prüfbar (Anbieter blockt Automaten)" };
      toast(r.ok ? `${names[r.data.status] || r.data.status}${r.data.note ? " – " + r.data.note : ""}` : errText(r), r.ok && r.data.status === "OK" ? "good" : "err");
    }
  });
  const lc = $("[data-linkcheck]");
  if (lc) {
    const text = $("[data-lc-text]", lc), start = $("[data-lc-start]", lc);
    const poll = async () => {
      const r = await api("GET", "/api/admin/streams/check-status");
      if (!r.ok) return;
      if (r.data.running) { text.textContent = `Läuft … ${r.data.done || 0}/${r.data.total || 0} geprüft.`; start.disabled = true; setTimeout(poll, 2000); }
      else { location.reload(); }
    };
    start.addEventListener("click", async () => {
      start.disabled = true;
      const r = await api("POST", "/api/admin/streams/check-all", {});
      if (!r.ok) { start.disabled = false; return toast(errText(r), "err"); }
      if (!r.data.started) toast("Es läuft bereits eine Prüfung.");
      poll();
    });
    if (start.disabled) poll();
  }

  // ---------------------------------------------------------------- Admin: Serien-/Film-Editor
  const readJSON = () => JSON.parse($("#editor-data").textContent);
  const csv = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);
  const LIST_FIELDS = new Set(["genres", "tags", "altTitles"]);
  const LANG_OPTS = [["GERDUB", "GerDub (Synchro)"], ["GERSUB", "GerSub (dt. UT)"], ["OMU", "OmU (Original)"]];
  const lastLang = () => { try { return localStorage.getItem("animem_editor_lang") || "GERSUB"; } catch { return "GERSUB"; } };

  function fillCommon(form, data) {
    $$("[data-f]", form).forEach((f) => {
      const v = data[f.dataset.f];
      f.value = Array.isArray(v) ? v.join(", ") : (v ?? "");
    });
  }
  function readCommon(form) {
    const out = {};
    $$("[data-f]", form).forEach((f) => { out[f.dataset.f] = LIST_FIELDS.has(f.dataset.f) ? csv(f.value) : f.value.trim(); });
    return out;
  }
  const setField = (form, key, value) => {
    const f = $(`[data-f="${key}"]`, form);
    if (f) f.value = Array.isArray(value) ? value.join(", ") : (value ?? "");
  };

  function langSelect(value) {
    const sel = el("select", { class: "input", "data-sg": true, "aria-label": "Sprache" },
      ...LANG_OPTS.map(([v, label]) => el("option", { value: v, text: label })));
    sel.value = value || lastLang();
    sel.addEventListener("change", () => { try { localStorage.setItem("animem_editor_lang", sel.value); } catch { /* egal */ } });
    return sel;
  }
  function streamRow(container, s = {}) {
    const label = el("input", { class: "input", "data-sl": true, placeholder: "Anbieter (z. B. VOE)", maxlength: "60", value: s.label || "" });
    const url = el("input", { class: "input", "data-su": true, placeholder: "https://…", inputmode: "url", value: s.url || "" });
    const lang = langSelect(s.lang);
    const rm = el("button", { type: "button", class: "btn btn-ghost btn-sm", text: "✕", "aria-label": "Stream entfernen" });
    const row = el("div", { class: "stream-row" }, label, url, lang, rm);
    rm.addEventListener("click", () => { if ($$(".stream-row", container).length > 1) row.remove(); else { label.value = ""; url.value = ""; } });
    container.append(row);
    return row;
  }
  const readStreams = (container) => $$(".stream-row", container).map((r) => ({ label: $("[data-sl]", r).value.trim(), url: $("[data-su]", r).value.trim(), lang: $("[data-sg]", r).value }));

  // ---- Import (AniList / Jikan)
  $$("[data-import]").forEach((box) => {
    const kind = box.dataset.kind, results = $("[data-imp-results]", box), msg = $("[data-imp-msg]", box);
    $("[data-imp-search]", box).addEventListener("click", async () => {
      const q = $("[data-imp-q]", box).value.trim(), provider = $("[data-imp-provider]", box).value;
      results.replaceChildren(); say(msg, "Suche läuft …");
      const r = await api("GET", `/api/admin/import/search?provider=${provider}&kind=${kind}&q=${encodeURIComponent(q)}`);
      if (!r.ok) return say(msg, errText(r), "err");
      say(msg, r.data.length ? "" : "Nichts gefunden.", r.data.length ? "" : "err");
      for (const item of r.data) {
        const pick = el("button", { type: "button", class: "btn btn-sm", text: "Übernehmen" });
        results.append(el("div", { class: "list-item" },
          item.cover ? el("img", { src: item.cover, alt: "", style: "width:42px;height:58px;object-fit:cover;border-radius:6px", referrerpolicy: "no-referrer" }) : null,
          el("div", { class: "grow" }, el("b", { class: "small", text: item.title }),
            el("p", { class: "tiny muted", text: [item.year, item.format, item.episodes ? `${item.episodes} Folgen` : ""].filter(Boolean).join(" · ") })),
          pick));
        pick.addEventListener("click", async () => {
          pick.disabled = true; say(msg, "Lade Daten – bei mehreren Staffeln kann das einen Moment dauern …");
          const titles = $("[data-imp-titles]", box) && $("[data-imp-titles]", box).checked ? "1" : "0";
          const f = await api("GET", `/api/admin/import/fetch?provider=${item.provider}&id=${item.id}&kind=${kind}&titles=${titles}`);
          pick.disabled = false;
          if (!f.ok) return say(msg, errText(f), "err");
          document.dispatchEvent(new CustomEvent("editor:import", { detail: f.data }));
          say(msg, "Importiert ✓ – bitte prüfen, Streams ergänzen und speichern.", "good");
        });
      }
    });
  });

  const movieForm = $("[data-movie-editor]");
  if (movieForm) {
    const data = readJSON(), streams = $("[data-streams]", movieForm), msg = $("[data-msg]", movieForm);
    fillCommon(movieForm, data);
    (data.streams.length ? data.streams : [{}]).forEach((s) => streamRow(streams, s));
    $("[data-add-stream]", movieForm).addEventListener("click", () => streamRow(streams));
    document.addEventListener("editor:import", (e) => {
      const d = e.detail;
      ["title", "description", "thumbnailUrl", "bannerUrl", "genres", "tags", "altTitles", "year"].forEach((k) => setField(movieForm, k, d[k]));
    });
    movieForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = { ...readCommon(movieForm), streams: readStreams(streams).filter((s) => s.url) };
      const r = await api(data.id ? "PATCH" : "POST", data.id ? `/api/movies/${data.id}` : "/api/movies", payload);
      if (!r.ok) return say(msg, errText(r), "err");
      say(msg, "Gespeichert ✓", "good");
      if (!data.id) location.href = `/admin/movies/${r.data.id}/edit`;
    });
  }

  const seriesForm = $("[data-series-editor]");
  if (seriesForm) {
    const data = readJSON(), seasonsBox = $("[data-seasons]", seriesForm), msg = $("[data-msg]", seriesForm);
    fillCommon(seriesForm, data);
    const nextNumber = (nodes, attr) => Math.max(0, ...nodes.map((n) => Number($(`[${attr}]`, n).value) || 0)) + 1;
    const sortEpisodes = (eps) => $$(".ep-block", eps).sort((a, b) => Number($("[data-en]", a).value) - Number($("[data-en]", b).value)).forEach((b) => eps.append(b));
    const findEpisode = (eps, n) => $$(".ep-block", eps).find((b) => Number($("[data-en]", b).value) === n);
    const addStreamTo = (block, stream) => {
      const box = $("[data-es]", block);
      const rows = $$(".stream-row", box);
      if (rows.some((r) => $("[data-su]", r).value.trim() === stream.url && $("[data-sg]", r).value === stream.lang)) return false;
      const empty = rows.find((r) => !$("[data-su]", r).value.trim());
      const row = empty || streamRow(box, stream);
      if (empty) { $("[data-sl]", row).value = stream.label; $("[data-su]", row).value = stream.url; $("[data-sg]", row).value = stream.lang; }
      return true;
    };

    function episodeBlock(parent, ep = {}) {
      const num = el("input", { class: "input", "data-en": true, type: "number", min: "1", value: ep.number || nextNumber($$(".ep-block", parent), "data-en"), style: "width:80px" });
      const title = el("input", { class: "input", "data-et": true, maxlength: "200", placeholder: "Folgentitel", value: ep.title || "" });
      const aired = el("input", { class: "input", "data-ea": true, type: "date", value: (ep.airedAt || "").slice(0, 10), style: "width:auto", "aria-label": "Erscheinungsdatum" });
      const rm = el("button", { type: "button", class: "btn btn-danger btn-sm", text: "Folge entfernen" });
      const streams = el("div", { "data-es": true });
      const addStream = el("button", { type: "button", class: "btn btn-ghost btn-sm", text: "+ Stream" });
      const block = el("div", { class: "editor-block ep-block", "data-id": ep.id || "" },
        el("div", { class: "row", style: "flex-wrap:nowrap;margin-bottom:8px" }, el("span", { class: "small muted", text: "Folge" }), num, title),
        el("div", { class: "row small", style: "margin-bottom:8px;gap:8px" }, el("span", { class: "muted", text: "Erscheint am" }), aired, el("span", { class: "tiny muted", text: "ohne Stream = „angekündigt“" })),
        streams, el("div", { class: "row", style: "margin-top:6px" }, addStream, rm));
      (ep.streams && ep.streams.length ? ep.streams : [{}]).forEach((s) => streamRow(streams, s));
      addStream.addEventListener("click", () => streamRow(streams));
      rm.addEventListener("click", () => block.remove());
      parent.append(block);
      return block;
    }

    function bulkTools(eps) {
      const from = el("input", { class: "input", type: "number", min: "1", value: "1", style: "width:80px", "aria-label": "Von Folge" });
      const to = el("input", { class: "input", type: "number", min: "1", value: "12", style: "width:80px", "aria-label": "Bis Folge" });
      const tpl = el("input", { class: "input", value: "Folge {n}", "aria-label": "Titel-Vorlage" });
      const bulkMsg = el("p", { class: "msg small" });
      const create = el("button", { type: "button", class: "btn btn-sm", text: "Folgen anlegen" });
      create.addEventListener("click", () => {
        const a = Number(from.value), b = Number(to.value);
        if (!a || !b || b < a || b - a > 300) return say(bulkMsg, "Bitte einen gültigen Bereich angeben (höchstens 300 Folgen).", "err");
        let made = 0;
        for (let n = a; n <= b; n++) if (!findEpisode(eps, n)) { episodeBlock(eps, { number: n, title: tpl.value.replace("{n}", n) || `Folge ${n}` }); made++; }
        sortEpisodes(eps);
        say(bulkMsg, `${made} Folge(n) angelegt${made < b - a + 1 ? `, ${b - a + 1 - made} existierten schon` : ""}. Vergiss das Speichern nicht.`, "good");
      });
      const lang = langSelect(); const label = el("input", { class: "input", placeholder: "Anbieter (z. B. VOE)", maxlength: "60" });
      const start = el("input", { class: "input", type: "number", min: "1", value: "1", style: "width:80px", "aria-label": "Erste Folge" });
      const links = el("textarea", { class: "input", placeholder: "Ein Link pro Zeile – der Reihe nach Folge 1, 2, 3 …\nOptional mit Nummer:  5 | https://…", rows: "5" });
      const add = el("button", { type: "button", class: "btn btn-sm", text: "Links eintragen" });
      add.addEventListener("click", () => {
        let n = Number(start.value) || 1, ok = 0, dupes = 0, bad = 0;
        for (const raw of links.value.split("\n")) {
          const line = raw.trim(); if (!line) continue;
          let url = line, num = n;
          if (line.includes("|")) { const [a, ...rest] = line.split("|"); if (/^\d+$/.test(a.trim())) { num = Number(a.trim()); url = rest.join("|").trim(); } }
          if (!/^https:\/\/\S+$/i.test(url)) { bad++; continue; }
          let block = findEpisode(eps, num);
          if (!block) block = episodeBlock(eps, { number: num, title: `Folge ${num}` });
          addStreamTo(block, { label: label.value.trim(), url, lang: lang.value }) ? ok++ : dupes++;
          n = num + 1;
        }
        sortEpisodes(eps);
        say(bulkMsg, `${ok} Link(s) eingetragen${dupes ? `, ${dupes} Duplikat(e) übersprungen` : ""}${bad ? `, ${bad} ungültig (nur https://)` : ""}. Vergiss das Speichern nicht.`, bad ? "err" : "good");
      });
      return el("details", { class: "panel-solid", style: "margin-top:12px" },
        el("summary", { style: "cursor:pointer;font-weight:600", text: "⚡ Massen-Funktionen" }),
        el("div", { class: "stack", style: "margin-top:10px" },
          el("p", { class: "small muted", text: "1) Folgen in einem Rutsch anlegen (ohne Stream = angekündigt):" }),
          el("div", { class: "row", style: "gap:6px" }, el("span", { class: "small", text: "von" }), from, el("span", { class: "small", text: "bis" }), to, tpl, create),
          el("p", { class: "small muted", style: "margin-top:8px", text: "2) Links einer Sprache für viele Folgen auf einmal eintragen:" }),
          el("div", { class: "row", style: "gap:6px" }, lang, label, el("span", { class: "small", text: "ab Folge" }), start),
          links, add, bulkMsg));
    }

    function seasonBlock(s = {}) {
      const num = el("input", { class: "input", "data-sn": true, type: "number", min: "1", value: s.number || nextNumber($$(".season-block", seasonsBox), "data-sn"), style: "width:80px" });
      const title = el("input", { class: "input", "data-st": true, maxlength: "200", placeholder: "Titel (optional)", value: s.title || "" });
      const imgBox = el("div", { "data-upload-field": "season", style: "margin-top:10px" },
        el("label", { class: "f", text: "Staffel-Bild (optional – sonst das Serien-Poster)" }),
        el("input", { class: "input", "data-url": true, "data-sthumb": true, placeholder: "https://… oder Bild hochladen", value: s.thumbnailUrl || "" }),
        el("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/gif", "data-file": true, class: "small", style: "margin-top:6px" }));
      wireUpload(imgBox);
      const eps = el("div", { class: "stack", "data-eps": true, style: "margin-top:12px" });
      const addEp = el("button", { type: "button", class: "btn btn-ghost btn-sm", text: "+ Folge" });
      const rm = el("button", { type: "button", class: "btn btn-danger btn-sm", text: "Staffel entfernen" });
      const block = el("div", { class: "editor-block season-block", "data-id": s.id || "" },
        el("div", { class: "row", style: "flex-wrap:nowrap" }, el("b", { text: "Staffel" }), num, title),
        imgBox, bulkTools(eps), eps, el("div", { class: "row", style: "margin-top:12px" }, addEp, rm));
      (s.episodes || []).forEach((ep) => episodeBlock(eps, ep));
      addEp.addEventListener("click", () => episodeBlock(eps));
      rm.addEventListener("click", () => { if (confirm("Staffel samt aller Folgen entfernen? (Wird erst beim Speichern wirksam.)")) block.remove(); });
      seasonsBox.append(block);
      return block;
    }

    data.seasons.forEach(seasonBlock);
    $("[data-add-season]", seriesForm).addEventListener("click", () => seasonBlock());

    // Import: Stammdaten übernehmen und Staffeln/Folgen ergänzen (bestehende Folgen bleiben, Streams werden nie angefasst)
    document.addEventListener("editor:import", (e) => {
      const d = e.detail;
      const hasData = $("[data-f=title]", seriesForm).value.trim();
      if (!hasData || confirm("Titel, Beschreibung, Cover, Genres usw. mit den importierten Werten überschreiben?\n(Abbrechen = nur Staffeln und Folgen ergänzen)")) {
        ["title", "description", "thumbnailUrl", "bannerUrl", "genres", "tags", "altTitles", "year", "airStatus"].forEach((k) => setField(seriesForm, k, d[k]));
      }
      for (const imp of d.seasons) {
        const sb = $$(".season-block", seasonsBox).find((b) => Number($("[data-sn]", b).value) === imp.number) || seasonBlock({ number: imp.number });
        const img = $("[data-sthumb]", sb);
        if (!img.value.trim() && imp.thumbnailUrl) img.value = imp.thumbnailUrl;
        const eps = $("[data-eps]", sb);
        for (const ie of imp.episodes) {
          const blk = findEpisode(eps, ie.number);
          if (!blk) { episodeBlock(eps, { number: ie.number, title: ie.title, airedAt: ie.airedAt, streams: [] }); continue; }
          if (/^Folge \d+$/.test($("[data-et]", blk).value.trim()) && ie.title) $("[data-et]", blk).value = ie.title;
          if (!$("[data-ea]", blk).value && ie.airedAt) $("[data-ea]", blk).value = ie.airedAt.slice(0, 10);
        }
        sortEpisodes(eps);
      }
    });

    seriesForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        ...readCommon(seriesForm),
        seasons: $$(".season-block", seasonsBox).map((sb) => ({
          id: sb.dataset.id || undefined, number: Number($("[data-sn]", sb).value), title: $("[data-st]", sb).value.trim(),
          thumbnailUrl: $("[data-sthumb]", sb).value.trim(),
          episodes: $$(".ep-block", sb).map((eb) => ({
            id: eb.dataset.id || undefined, number: Number($("[data-en]", eb).value), title: $("[data-et]", eb).value.trim(),
            airedAt: $("[data-ea]", eb).value, streams: readStreams($("[data-es]", eb)).filter((s) => s.url),
          })),
        })),
      };
      const btn = $("button[type=submit]", seriesForm); btn.disabled = true;
      const r = await api(data.id ? "PATCH" : "POST", data.id ? `/api/series/${data.id}` : "/api/series", payload);
      btn.disabled = false;
      if (!r.ok) return say(msg, errText(r), "err");
      say(msg, "Gespeichert ✓", "good");
      location.href = `/admin/series/${r.data.id}/edit`;
    });
  }
})();
