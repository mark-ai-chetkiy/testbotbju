/* Static Telegram Mini App: no backend, all data in localStorage. */
(function () {
  "use strict";

  const KEYS = {
    diary: "bju_diary_v1",
    profile: "bju_profile_v1",
    petName: "bju_pet_name_v1",
    source: "bju_source_v1",
    club: "bju_club_v1",
    checkins: "bju_checkins_v1",
  };

  // Фото-ИИ работает через уже задеплоенный бот: ключ Gemini остаётся на сервере.
  const AI_ENDPOINT = "https://bju-bot-cnjz.onrender.com/api/recognize";
  const AI_WARMUP = "https://bju-bot-cnjz.onrender.com/health";

  const ACTIVITY = {
    1: 1.20, 2: 1.375, 3: 1.55, 4: 1.725, 5: 1.90,
  };
  const GOALS = {
    lose: { coef: 0.82, proteinPerKg: 2.0, fatRatio: 0.25 },
    keep: { coef: 1.00, proteinPerKg: 1.6, fatRatio: 0.28 },
    gain: { coef: 1.12, proteinPerKg: 1.8, fatRatio: 0.30 },
  };
  const STAGES = [
    { min: 1, emoji: "\u{1F95A}", title: "Яйцо" },
    { min: 3, emoji: "\u{1F423}", title: "Цыплёнок" },
    { min: 5, emoji: "\u{1F425}", title: "Птенец" },
    { min: 8, emoji: "\u{1F424}", title: "Птенец-крепыш" },
    { min: 12, emoji: "\u{1F414}", title: "Взрослый" },
    { min: 17, emoji: "\u{1F985}", title: "Орёл" },
    { min: 22, emoji: "\u{1F432}", title: "Легенда" },
  ];

  const tg = window.Telegram && window.Telegram.WebApp;
  const state = {
    products: [], recipes: [], diary: [], profile: null,
    club: null, checkins: [], aiItems: [],
    petName: "Тёма", source: "", selected: null, tab: "calc",
  };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (x) => {
    x = Number(x);
    if (!isFinite(x)) return "0";
    return Math.abs(x - Math.round(x)) < 0.05 ? String(Math.round(x)) : x.toFixed(1).replace(".", ",");
  };
  const norm = (s) => String(s).toLowerCase().replace(/ё/g, "е").trim();

  function load(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* no storage */ }
  }

  function dayKey(d) {
    d = d || new Date();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }
  function dateFromKey(key) {
    const p = key.split("-").map(Number);
    return new Date(p[0], p[1] - 1, p[2]);
  }
  function shiftDay(key, delta) {
    const d = dateFromKey(key);
    d.setDate(d.getDate() + delta);
    return dayKey(d);
  }

  /* ---- calculations (ported from nutrition.py) ---- */
  function calcTargets(profile) {
    if (!profile) return null;
    const w = Number(profile.weight), h = Number(profile.height), a = Number(profile.age);
    const bmr = 10 * w + 6.25 * h - 5 * a + (profile.gender === "m" ? 5 : -161);
    const tdee = bmr * ACTIVITY[profile.activity];
    const goal = GOALS[profile.goal] || GOALS.keep;
    const calories = Math.round(tdee * goal.coef);
    const protein = Math.round(w * goal.proteinPerKg);
    const fat = Math.round(calories * goal.fatRatio / 9);
    const carbs = Math.max(30, Math.round((calories - protein * 4 - fat * 9) / 4));
    return { bmr: Math.round(bmr), tdee: Math.round(tdee), calories, protein, fat, carbs };
  }

  function searchProducts(query, limit) {
    limit = limit || 12;
    const q = norm(query);
    if (!q) return [];
    const toks = q.split(/[^a-zа-я0-9]+/).filter((t) => t && !/^\d+$/.test(t));
    const exact = [], partial = [];
    state.products.forEach((p) => {
      const n = norm(p.n);
      if (q === n) { exact.push({ p, len: 0 }); return; }
      if (n.indexOf(q) !== -1 || (n.length >= 4 && q.indexOf(n) !== -1)) {
        partial.push({ p, len: n.length }); return;
      }
      if (toks.length && toks.every((t) =>
        t.length <= 2 || n.indexOf(t) !== -1 || (t.length >= 5 && n.indexOf(t.slice(0, 5)) === 0))) {
        partial.push({ p, len: n.length });
      }
    });
    partial.sort((a, b) => a.len - b.len);
    return exact.concat(partial.slice(0, limit)).map((x) => x.p);
  }

  function scaleProduct(p, grams) {
    const k = grams / 100;
    return { p: p.p * k, f: p.f * k, c: p.c * k, k: p.k * k };
  }

  /* ---- diary ---- */
  function groupDays() {
    const days = {};
    state.diary.forEach((r) => {
      const d = days[r.day] || { items: 0, protein: 0, fat: 0, carbs: 0, calories: 0 };
      d.items += 1;
      d.protein += Number(r.p) || 0;
      d.fat += Number(r.f) || 0;
      d.carbs += Number(r.c) || 0;
      d.calories += Number(r.k) || 0;
      days[r.day] = d;
    });
    return days;
  }

  function addEntry(name, grams, macros) {
    state.diary.push({
      day: dayKey(),
      time: new Date().toTimeString().slice(0, 5),
      name: name,
      grams: grams,
      p: macros.p, f: macros.f, c: macros.c, k: macros.k,
    });
    save(KEYS.diary, state.diary);
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    renderAll();
    setTab("diary");
  }

  /* ---- pet (ported from pet.py) ---- */
  function levelInfo(xp) {
    let lvl = 1, need = 100, cum = 0;
    while (xp >= cum + need) { cum += need; lvl += 1; need = 100 * lvl; }
    return { level: lvl, into: xp - cum, need: need };
  }
  function stageFor(level) {
    let stage = STAGES[0];
    STAGES.forEach((s) => { if (level >= s.min) stage = s; });
    return stage;
  }
  function qualifies(tot, target) {
    if (!tot || tot.calories <= 0) return false;
    if (!target) return true;
    return tot.calories >= 0.85 * target.calories &&
      tot.calories <= 1.15 * target.calories &&
      tot.protein >= 0.7 * target.protein;
  }
  function moodFor(tdy, target) {
    if (tdy.items === 0) return ["\u{1F61A}", "Голодный — покорми меня, запиши еду!"];
    if (!target) return ["\u{1F642}", "Сыт и доволен. Заполни профиль — и я начну следить за нормой!"];
    const ratio = target.calories ? tdy.calories / target.calories : 1;
    const proteinOk = tdy.protein >= 0.8 * target.protein;
    if (ratio < 0.5) return ["\u{1F61A}", "Ещё мало еды — я не наелся"];
    if (ratio < 0.85) return ["\u{1F642}", "Неплохо, но можно добрать калорий"];
    if (ratio <= 1.05 && proteinOk) return ["\u{1F600}", "Сыт, счастлив и в норме!"];
    if (ratio <= 1.15) return ["\u{1F60E}", "Отличный день, держим курс"];
    if (ratio <= 1.35) return ["\u{1F605}", "Меня слегка перекормили"];
    return ["\u{1F922}", "Перекорм! Завтра полегче, ладно?"];
  }
  function petStats() {
    const days = groupDays();
    const target = calcTargets(state.profile);
    let xp = 0;
    Object.keys(days).forEach((day) => {
      const d = days[day];
      xp += 5 * d.items;
      if (!target) { xp += 10; return; }
      if (d.calories >= 0.85 * target.calories && d.calories <= 1.15 * target.calories) xp += 30;
      if (d.protein >= 0.8 * target.protein) xp += 20;
      if (d.protein >= target.protein && d.calories <= 1.15 * target.calories) xp += 10;
    });

    const today = dayKey();
    let cur = today;
    if (!qualifies(days[cur], target)) cur = shiftDay(cur, -1);
    let streak = 0;
    while (days[cur] && qualifies(days[cur], target)) { streak += 1; cur = shiftDay(cur, -1); }

    let best = 0, run = 0, prev = null;
    Object.keys(days).sort().forEach((day) => {
      if (qualifies(days[day], target)) {
        const consecutive = prev &&
          Math.round((dateFromKey(day) - dateFromKey(prev)) / 86400000) === 1;
        run = consecutive ? run + 1 : 1;
        best = Math.max(best, run);
      } else { run = 0; }
      prev = day;
    });
    xp += Math.min(5 * streak, 50);

    // Чекины в зале тоже кормят питомца: +15 XP за визит, +5 если в тот же день был дневник.
    (state.checkins || []).forEach((day) => {
      xp += 15;
      if (days[day] && days[day].items) xp += 5;
    });

    const li = levelInfo(xp);
    const tdy = days[today] || { items: 0, protein: 0, fat: 0, calories: 0 };
    const m = moodFor(tdy, target);
    return {
      xp: xp, level: li.level, into: li.into, need: li.need,
      stage: stageFor(li.level), streak: streak, best: best,
      today: tdy, target: target, mood: m,
    };
  }

  /* ---- AI photo recognition ---- */
  function renderAiResult() {
    const box = $("ai-result");
    const items = state.aiItems || [];
    if (!items.length) { box.hidden = true; box.innerHTML = ""; return; }
    box.hidden = false;
    box.innerHTML = '<h2>🤖 Что увидел ИИ</h2>' +
      '<p class="hint">Проверь порции — ИИ может ошибаться. Нажми на блюдо, чтобы добавить в дневник.</p>' +
      items.map((it, i) =>
        '<div class="ai-item"><div class="result-name">' + esc(it.name) + '</div>' +
        '<div class="result-meta">' + fmt(it.grams) + ' г · ИИ-оценка порции</div>' +
        '<div class="macro-row">' +
          '<span class="macro-pill">Б ' + fmt(it.protein) + ' г</span>' +
          '<span class="macro-pill">Ж ' + fmt(it.fat) + ' г</span>' +
          '<span class="macro-pill">У ' + fmt(it.carbs) + ' г</span>' +
          '<span class="macro-pill k">' + fmt(it.calories) + ' ккал</span>' +
        '</div><button class="link-btn" data-ai-add="' + i + '">＋ В дневник</button></div>').join("") +
      '<button class="primary" id="ai-add-all">Добавить всё в дневник</button>';

    box.querySelectorAll("[data-ai-add]").forEach((el) => {
      el.addEventListener("click", () => {
        const it = state.aiItems[Number(el.dataset.aiAdd)];
        addAiItems([it]);
      });
    });
    $("ai-add-all").addEventListener("click", () => addAiItems(state.aiItems.slice()));
  }

  function addAiItems(items) {
    const copy = items.slice();
    state.aiItems = [];
    renderAiResult();
    copy.forEach((it) => addEntry(
      it.name, it.grams,
      { p: it.protein, f: it.fat, c: it.carbs, k: it.calories }
    ));
  }

  function fileToJpegDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => {
        const img = new Image();
        img.onerror = reject;
        img.onload = () => {
          const max = 1600;
          let w = img.width || max, h = img.height || max;
          const scale = Math.min(1, max / Math.max(w, h));
          w = Math.round(w * scale); h = Math.round(h * scale);
          const canvas = document.createElement("canvas");
          canvas.width = w; canvas.height = h;
          canvas.getContext("2d").drawImage(img, 0, 0, w, h);
          resolve(canvas.toDataURL("image/jpeg", 0.8));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function handleAiFile(file) {
    if (!file) return;
    const box = $("ai-result");
    state.aiItems = [];
    box.hidden = false;
    box.innerHTML = '<div class="ai-loading">🔍 Анализирую фото… при первом запросе сервис может просыпаться до минуты.</div>';
    try {
      const dataUrl = await fileToJpegDataUrl(file);
      const resp = await fetch(AI_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl, mime: "image/jpeg" }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) throw new Error(data.error || "Ошибка сервиса");
      state.aiItems = (data.items || []).map((it) => ({
        name: String(it.name || "Блюдо").slice(0, 80),
        grams: Number(it.grams) || 100,
        protein: Number(it.protein) || 0,
        fat: Number(it.fat) || 0,
        carbs: Number(it.carbs) || 0,
        calories: Number(it.calories) || 0,
      }));
      if (!state.aiItems.length) throw new Error("Не удалось распознать блюдо на фото");
      renderAiResult();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (e) {
      state.aiItems = [];
      const msg = String(e.message || e);
      const text = /временно недоступен|high demand|overload|rate limit|429|503/i.test(msg)
        ? "Сервис распознавания сейчас перегружен. Попробуй ещё раз через минуту."
        : "Не получилось посчитать фото. Проверь, что на снимке видна еда, и попробуй снова.";
      box.innerHTML = '<p class="ai-error">' + text +
        '</p><button class="primary" id="ai-retry">Попробовать другое фото</button>';
      $("ai-retry").addEventListener("click", () => $("ai-file").click());
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
    }
  }

  /* ---- club challenge ---- */
  function clubStats() {
    const club = state.club || { name: "Мой зал", days: 30, start: dayKey() };
    const days = groupDays();
    const visited = {};
    (state.checkins || []).forEach((d) => { visited[d] = true; });
    const today = dayKey();
    const start = dateFromKey(club.start);
    const now = dateFromKey(today);
    const total = Number(club.days) || 30;
    const elapsed = Math.max(1, Math.min(total, Math.round((now - start) / 86400000) + 1));

    let done = 0, visits = 0, logged = 0;
    for (let i = 0; i < elapsed; i++) {
      const key = shiftDay(club.start, i);
      const hasVisit = !!visited[key];
      const hasLog = !!(days[key] && days[key].items);
      if (hasVisit) visits += 1;
      if (hasLog) logged += 1;
      if (hasVisit || hasLog) done += 1;
    }

    let cur = today;
    const active = (key) => !!visited[key] || !!(days[key] && days[key].items);
    if (!active(cur)) cur = shiftDay(cur, -1);
    let streak = 0;
    while (active(cur)) { streak += 1; cur = shiftDay(cur, -1); }

    return {
      club: club, elapsed: elapsed, total: total, done: done,
      visits: visits, logged: logged, streak: streak,
      pct: elapsed ? Math.round(done / elapsed * 100) : 0,
      checkedToday: !!visited[today],
    };
  }

  /* ---- rendering ---- */
  function progress(label, value, target, cls) {
    const pct = target ? Math.min(100, Math.round(value / target * 100)) : 0;
    const over = target && value > target * 1.15;
    return '<div class="progress-block">' +
      '<div class="progress-label"><span>' + esc(label) + '</span><span>' +
      fmt(value) + (target ? " / " + fmt(target) : "") + '</span></div>' +
      '<div class="progress-track"><div class="progress-fill ' + (over ? "over " : "") +
      (cls || "") + '" style="width:' + pct + '%"></div></div></div>';
  }

  function renderResults() {
    const q = $("search").value.trim();
    const box = $("results");
    if (!q) { box.innerHTML = '<p class="empty">Начни вводить название продукта 👆</p>'; return; }
    const found = searchProducts(q, 20);
    if (!found.length) { box.innerHTML = '<p class="empty">Ничего не найдено. Попробуй другое слово.</p>'; return; }
    box.innerHTML = found.map((p, i) =>
      '<div class="result-item" data-product="' + i + '">' +
      '<div class="result-name">' + esc(p.n) + '</div>' +
      '<div class="result-meta">на 100 г · Б ' + fmt(p.p) + ' / Ж ' + fmt(p.f) +
      ' / У ' + fmt(p.c) + ' · ' + fmt(p.k) + ' ккал</div></div>').join("");
    box.querySelectorAll("[data-product]").forEach((el) => {
      el.addEventListener("click", () => openPortion(found[Number(el.dataset.product)]));
    });
  }

  function openPortion(product) {
    state.selected = product;
    $("portion-title").textContent = product.n;
    $("grams").value = "100";
    $("portion-overlay").hidden = false;
    renderPortionPreview();
  }
  function closePortion() {
    $("portion-overlay").hidden = true;
    state.selected = null;
  }
  function renderPortionPreview() {
    if (!state.selected) return;
    const grams = Math.max(1, Number($("grams").value) || 100);
    const m = scaleProduct(state.selected, grams);
    $("portion-preview").innerHTML =
      '<div class="macro-row">' +
      '<span class="macro-pill">Б ' + fmt(m.p) + ' г</span>' +
      '<span class="macro-pill">Ж ' + fmt(m.f) + ' г</span>' +
      '<span class="macro-pill">У ' + fmt(m.c) + ' г</span>' +
      '<span class="macro-pill k">' + fmt(m.k) + ' ккал</span></div>';
  }

  function renderDiary() {
    const target = calcTargets(state.profile);
    const tdy = groupDays()[dayKey()] || { items: 0, protein: 0, fat: 0, carbs: 0, calories: 0 };
    let html = '<div class="section-head"><h2>Сегодня</h2></div>' + "<h2>" + fmt(tdy.calories) + " ккал</h2>";
    if (target) {
      html += progress("Калории", tdy.calories, target.calories) +
        progress("Белок", tdy.protein, target.protein) +
        progress("Жиры", tdy.fat, target.fat) +
        progress("Углеводы", tdy.carbs, target.carbs);
    } else {
      html += '<p class="hint">Заполни профиль во вкладке «Профиль», чтобы видеть личную норму и прогресс.</p>';
    }
    html += '<div class="stat-grid">' +
      '<div class="stat-box"><div class="stat-value">' + tdy.items + '</div><div class="stat-label">записей</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + fmt(tdy.protein) + '</div><div class="stat-label">белок, г</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + fmt(tdy.carbs) + '</div><div class="stat-label">углеводы, г</div></div></div>';
    $("diary-summary").innerHTML = html;

    const today = state.diary.filter((r) => r.day === dayKey()).slice().reverse();
    $("diary-list").innerHTML = today.length ? today.map((r) => {
      const idx = state.diary.indexOf(r);
      return '<div class="list-item"><div class="rowline"><span><b>' + esc(r.name) + '</b>' +
        '<div class="list-meta">' + fmt(r.grams) + ' г · ' + esc(r.time) + '</div></span>' +
        '<button class="del-btn" data-del="' + idx + '" title="Удалить">×</button></div>' +
        '<div class="macro-row"><span class="macro-pill">Б ' + fmt(r.p) + '</span>' +
        '<span class="macro-pill">Ж ' + fmt(r.f) + '</span>' +
        '<span class="macro-pill">У ' + fmt(r.c) + '</span>' +
        '<span class="macro-pill k">' + fmt(r.k) + ' ккал</span></div></div>';
    }).join("") : '<p class="empty">Пока пусто. Найди продукт во вкладке «БЖУ» и добавь порцию.</p>';
    $("diary-list").querySelectorAll("[data-del]").forEach((el) => {
      el.addEventListener("click", () => {
        state.diary.splice(Number(el.dataset.del), 1);
        save(KEYS.diary, state.diary);
        renderAll();
      });
    });

    const days = groupDays();
    const labels = ["Сегодня", "Вчера"];
    let hist = "";
    for (let i = 0; i < 7; i++) {
      const key = shiftDay(dayKey(), -i);
      const d = days[key];
      if (!d) continue;
      const label = labels[i] || dateFromKey(key).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
      hist += '<div class="list-item"><div class="rowline"><span><b>' + label + '</b>' +
        '<div class="list-meta">' + d.items + ' записей' +
        (target ? ' · ' + Math.round(d.calories / target.calories * 100) + '% нормы' : "") +
        ' · ' + (qualifies(d, target) ? "✅ норма" : "⚠️ мимо нормы") + '</div></span>' +
        '<b>' + fmt(d.calories) + ' ккал</b></div></div>';
    }
    $("history").innerHTML = hist || '<p class="empty">Заполняй дневник — здесь появится история.</p>';
  }

  function renderPet() {
    const s = petStats();
    const pct = Math.min(100, Math.round(s.into / s.need * 100));
    $("pet-chip").innerHTML = s.stage.emoji + ' <span>Lv.' + s.level + '</span>';
    $("pet-card").innerHTML =
      '<div class="pet-hero">' +
      '<div class="pet-emoji">' + s.stage.emoji + '</div>' +
      '<div class="pet-name">' + esc(state.petName) + ' · ' + esc(s.stage.title) + '</div>' +
      '<div class="pet-mood">' + s.mood[0] + ' ' + esc(s.mood[1]) + '</div>' +
      '<div class="pet-level"><div class="progress-label"><span>Уровень ' + s.level +
      '</span><span>' + s.into + ' / ' + s.need + ' XP</span></div>' +
      '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div></div>' +
      '<div class="stage-line">' + STAGES.map((st) =>
        '<span class="stage' + (s.level >= st.min ? " reached" : "") + '" title="' +
        esc(st.title) + '">' + st.emoji + '</span>').join("") + '</div></div>' +
      '<div class="card"><div class="stat-grid">' +
      '<div class="stat-box"><div class="stat-value">' + s.streak + '</div><div class="stat-label">стрик, дней</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + s.best + '</div><div class="stat-label">лучший стрик</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + s.xp + '</div><div class="stat-label">всего XP</div></div></div>' +
      '<p class="hint">Питомец растёт от записей в дневнике и чекинов в зале: +5 XP за порцию, +15 XP за визит в зал, бонусы за день в цели и за серию дней.</p></div>';
  }

  function renderRecipes() {
    const q = norm($("recipe-search").value.trim());
    const found = state.recipes.map((r, i) => ({ r, i })).filter((x) => !q || norm(x.r.n).indexOf(q) !== -1);
    $("recipes-list").innerHTML = found.length ? found.map(({ r, i }) =>
      '<div class="list-item"><div class="rowline"><b>' + esc(r.n) + '</b><span class="macro-pill k">' +
      fmt(r.k) + ' ккал</span></div>' +
      '<div class="result-meta">Б ' + fmt(r.p) + ' / Ж ' + fmt(r.f) + ' / У ' + fmt(r.c) + '</div>' +
      '<p class="hint">' + esc(r.d || "") + '</p>' +
      '<button class="link-btn" data-recipe="' + i + '">＋ В дневник (1 порция)</button></div>').join("")
      : '<p class="empty">Рецепт не найден.</p>';
    $("recipes-list").querySelectorAll("[data-recipe]").forEach((el) => {
      el.addEventListener("click", () => {
        const r = state.recipes[Number(el.dataset.recipe)];
        addEntry(r.n, "1 порция", { p: r.p, f: r.f, c: r.c, k: r.k });
      });
    });
  }

  function renderProfile() {
    const p = state.profile;
    if (p) {
      $("gender").value = p.gender; $("age").value = p.age;
      $("height").value = p.height; $("weight").value = p.weight;
      $("activity").value = String(p.activity); $("goal").value = p.goal;
    }
    const t = calcTargets(p);
    $("target-card").innerHTML = t ?
      '<h2>Твоя норма</h2>' +
      '<div class="stat-grid"><div class="stat-box"><div class="stat-value">' + t.calories +
      '</div><div class="stat-label">ккал/день</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + t.protein + '</div><div class="stat-label">белок, г</div></div>' +
      '<div class="stat-box"><div class="stat-value">' + t.fat + '</div><div class="stat-label">жиры, г</div></div></div>' +
      '<p class="hint">Углеводы: ' + t.carbs + ' г · базовый обмен: ' + t.bmr +
      ' ккал · с активностью: ' + t.tdee + ' ккал</p>'
      : '<p class="empty">Норма ещё не посчитана — заполни данные выше.</p>';
    $("pet-name").value = state.petName;
    if (state.source) {
      $("source-note").textContent = "Источник: " + state.source + " · данные хранятся только на этом устройстве";
    }
  }

  function renderClub() {
    const s = clubStats();
    const box = $("club-card");
    box.innerHTML =
      '<div class="card">' +
        '<h2>🏋️ Челлендж клуба</h2>' +
        '<p class="hint">Прогресс хранится на этом устройстве. Покажи результат тренеру — он засчитает его в клубе.</p>' +
        '<div class="field"><label class="label" for="club-name">Название клуба</label>' +
        '<input id="club-name" type="text" maxlength="30" value="' + esc(s.club.name) + '"></div>' +
        '<div class="field"><label class="label" for="club-days">Длительность челленджа</label>' +
        '<select id="club-days">' +
          [7, 14, 30, 60].map((n) => '<option value="' + n + '"' +
            (s.total === n ? " selected" : "") + '>' + n + ' дней</option>').join("") +
        '</select></div>' +
        '<button class="primary" id="save-club">Сохранить настройки</button>' +
      '</div>' +
      '<div class="card">' +
        '<h2>День ' + s.elapsed + ' из ' + s.total + '</h2>' +
        progress("Успешных дней", s.done, s.elapsed) +
        '<div class="stat-grid">' +
          '<div class="stat-box"><div class="stat-value">' + s.visits + '</div><div class="stat-label">тренировок</div></div>' +
          '<div class="stat-box"><div class="stat-value">' + s.logged + '</div><div class="stat-label">дней с дневником</div></div>' +
          '<div class="stat-box"><div class="stat-value">' + s.streak + '</div><div class="stat-label">серия, дней</div></div>' +
        '</div>' +
        '<p class="hint">Успешным считается день с чекином в зале или записью в дневнике. Серия — подряд, считая сегодня или вчера.</p>' +
      '</div>' +
      '<div class="card">' +
        '<button class="primary" id="checkin">' +
          (s.checkedToday ? "✅ Ты уже в зале сегодня — нажми, чтобы отменить" : "🏋️ Я в зале — отметить тренировку") +
        '</button>' +
        '<p class="hint">За каждый визит питомец получает +15 XP, а если в этот день есть запись в дневнике — ещё +5.</p>' +
        '<div class="row actions">' +
          '<button class="ghost" id="share-club">Поделиться</button>' +
          '<button class="ghost" id="reset-club">Заново</button>' +
        '</div>' +
      '</div>';

    $("save-club").addEventListener("click", () => {
      state.club = {
        name: $("club-name").value.trim().slice(0, 30) || "Мой зал",
        days: Number($("club-days").value) || 30,
        start: (state.club && state.club.start) || dayKey(),
      };
      save(KEYS.club, state.club);
      renderAll();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    });
    $("checkin").addEventListener("click", () => {
      const today = dayKey();
      const i = state.checkins.indexOf(today);
      if (i === -1) state.checkins.push(today);
      else state.checkins.splice(i, 1);
      save(KEYS.checkins, state.checkins);
      renderAll();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
    });
    $("reset-club").addEventListener("click", () => {
      if (!window.confirm("Начать челлендж заново? Отметки тренировок будут очищены.")) return;
      state.checkins = [];
      state.club = { name: (state.club && state.club.name) || "Мой зал", days: (state.club && state.club.days) || 30, start: dayKey() };
      save(KEYS.checkins, state.checkins);
      save(KEYS.club, state.club);
      renderAll();
    });
    $("share-club").addEventListener("click", () => {
      const text = "🏋️ Челлендж «" + s.club.name + "»: день " + s.elapsed + "/" + s.total +
        ", тренировок " + s.visits + ", серия " + s.streak + " дн. Считаю БЖУ в @GymTamagotchi_bot";
      const url = "https://t.me/GymTamagotchi_bot?startapp=channel";
      if (tg && tg.openTelegramLink) {
        tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(text));
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(text + " " + url);
        window.alert("Результат скопирован");
      } else {
        window.prompt("Скопируй результат:", text + " " + url);
      }
    });
  }

  function renderAll() {
    renderResults(); renderDiary(); renderPet(); renderClub(); renderProfile(); renderRecipes();
    renderAiResult(); renderPortionPreview();
  }

  function setTab(name) {
    state.tab = name;
    document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("active", el.id === "tab-" + name));
    document.querySelectorAll(".bottom-nav button").forEach((el) => el.classList.toggle("active", el.dataset.tab === name));
    if (tg && tg.BackButton) { /* tabs are the navigation */ }
    window.scrollTo(0, 0);
  }

  function applyTheme(theme) {
    if (!theme) return;
    const root = document.documentElement;
    if (theme.bg_color) root.style.setProperty("--bg", theme.bg_color);
    if (theme.secondary_bg_color) root.style.setProperty("--card", theme.secondary_bg_color);
    if (theme.text_color) root.style.setProperty("--text", theme.text_color);
    if (theme.hint_color) root.style.setProperty("--muted", theme.hint_color);
    if (theme.button_color) root.style.setProperty("--accent", theme.button_color);
  }

  function initEvents() {
    document.querySelectorAll(".bottom-nav button").forEach((el) => {
      el.addEventListener("click", () => setTab(el.dataset.tab));
    });
    $("search").addEventListener("input", renderResults);
    $("ai-photo-btn").addEventListener("click", () => $("ai-file").click());
    $("ai-file").addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      handleAiFile(file);
    });
    $("recipe-search").addEventListener("input", renderRecipes);
    $("grams").addEventListener("input", renderPortionPreview);
    $("portion-overlay").addEventListener("click", (e) => {
      if (e.target === $("portion-overlay")) closePortion();
    });
    $("cancel-portion").addEventListener("click", closePortion);
    document.querySelectorAll("[data-grams]").forEach((el) => {
      el.addEventListener("click", () => { $("grams").value = el.dataset.grams; renderPortionPreview(); });
    });
    $("add-to-diary").addEventListener("click", () => {
      if (!state.selected) return;
      const grams = Math.max(1, Number($("grams").value) || 100);
      addEntry(state.selected.n, grams, scaleProduct(state.selected, grams));
      closePortion();
    });
    $("clear-day").addEventListener("click", () => {
      const ok = window.confirm("Очистить все записи за сегодня?");
      if (!ok) return;
      state.diary = state.diary.filter((r) => r.day !== dayKey());
      save(KEYS.diary, state.diary);
      renderAll();
    });
    $("profile-form").addEventListener("submit", (e) => {
      e.preventDefault();
      state.profile = {
        gender: $("gender").value,
        age: Number($("age").value),
        height: Number($("height").value),
        weight: Number($("weight").value),
        activity: Number($("activity").value),
        goal: $("goal").value,
      };
      save(KEYS.profile, state.profile);
      renderAll();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    });
    $("save-pet-name").addEventListener("click", () => {
      const v = $("pet-name").value.trim().slice(0, 20);
      state.petName = v || "Тёма";
      save(KEYS.petName, state.petName);
      renderAll();
    });
  }

  async function init() {
    if (tg) {
      tg.ready();
      tg.expand();
      applyTheme(tg.themeParams);
      const startParam = tg.initDataUnsafe && tg.initDataUnsafe.start_param;
      if (startParam) { state.source = startParam; save(KEYS.source, startParam); }
    } else {
      state.source = load(KEYS.source, "");
    }

    // Разогреваем сервис фото-ИИ заранее: холодный старт Render не будет заметен.
    fetch(AI_WARMUP, { mode: "no-cors", cache: "no-store" }).catch(() => {});

    state.diary = load(KEYS.diary, []);
    state.profile = load(KEYS.profile, null);
    state.club = load(KEYS.club, null);
    state.checkins = load(KEYS.checkins, []);
    state.petName = load(KEYS.petName, "Тёма");

    try {
      const [products, recipes] = await Promise.all([
        fetch("data/products.json").then((r) => r.json()),
        fetch("data/recipes.json").then((r) => r.json()),
      ]);
      state.products = products; state.recipes = recipes;
    } catch (e) {
      $("results").innerHTML = '<p class="empty">Не удалось загрузить базу продуктов. Обнови страницу.</p>';
    }
    initEvents();
    renderAll();
  }

  init();
})();
