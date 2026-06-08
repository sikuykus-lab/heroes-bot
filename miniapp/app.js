(function () {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#0e0e10");
    tg.setBackgroundColor("#0e0e10");
  }

  const params = new URLSearchParams(window.location.search);
  const chatId = params.get("chat_id");
  const chatToken = params.get("token");

  const HERO_INITIALS = {
    loh: "Л",
    homelander: "Х",
    starlight: "З",
    soldier_boy: "С",
    stormfront: "Ш",
    butcher: "Б",
  };

  const els = {
    balance: document.querySelector(".currency__value"),
    userAvatar: document.getElementById("user-avatar"),
    userName: document.getElementById("user-name"),
    userRole: document.getElementById("user-role"),
    userTier: document.getElementById("user-tier"),
    userVirus: document.getElementById("user-virus"),
    pageStatus: document.getElementById("page-status"),
    serverStatus: document.getElementById("server-status"),
    lockBanner: document.getElementById("lock-banner"),
    toast: document.getElementById("toast"),
    v24FreeSub: document.getElementById("v24-free-sub"),
    priceV24Paid: document.getElementById("price-v24-paid"),
    priceV: document.getElementById("price-v"),
    priceV1: document.getElementById("price-v1"),
    priceVirus: document.getElementById("price-virus"),
    virusHint: document.getElementById("virus-hint"),
    switchHint: document.getElementById("switch-hint"),
    charList: document.getElementById("char-list"),
    charactersSection: document.getElementById("characters-section"),
    purchaseButtons: document.querySelectorAll("[data-action]"),
  };

  let state = null;
  let busy = false;
  let cooldownTimer = null;

  function initData() {
    return tg?.initData || "";
  }

  function showToast(text, ok) {
    els.toast.textContent = text;
    els.toast.className = "toast " + (ok ? "ok" : "err");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => els.toast.classList.add("hidden"), 3500);
  }

  function setServerStatus(mode, text) {
    const dotClass =
      mode === "ok" ? "status-dot--ok" : mode === "err" ? "status-dot--err" : "status-dot--load";
    els.serverStatus.innerHTML = `<span class="status-dot ${dotClass}"></span>${text}`;
  }

  function tierLabel(tier) {
    if (!tier || tier === "none") return "Лох";
    return tier.toUpperCase();
  }

  function roleLabel(tier) {
    if (!tier || tier === "none") return "Гражданский";
    if (tier === "v24") return "Пробный супер";
    if (tier === "v") return "Супергерой";
    return "Элита V1";
  }

  function renderUserWidget(p) {
    const tier = p.v_tier || "none";
    const initial = HERO_INITIALS[p.active_character] || p.active_character_name?.[0] || "?";
    els.userAvatar.textContent = initial;
    els.userName.textContent = p.active_character_name || "Игрок";
    els.userRole.textContent = roleLabel(tier);
    els.userTier.textContent = `V: ${tierLabel(tier)}`;
    if (tier === "v24") {
      els.userTier.textContent += ` · ${p.v24_battles_left} боя`;
    }
    els.userVirus.textContent = `вирус ${p.virus_count}`;
  }

  function formatCooldown(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}м ${s}с`;
  }

  function setLocked(locked) {
    els.lockBanner.classList.toggle("hidden", !locked);
    els.purchaseButtons.forEach((btn) => {
      btn.disabled = locked || busy;
    });
    if (locked) {
      els.pageStatus.textContent = "Магазин закрыт — идёт бой";
      els.pageStatus.className = "page-head__status page-head__status--warn";
    }
  }

  function renderCharacters(characters, switchPrice, locked) {
    els.charList.innerHTML = "";
    if (!characters.length) {
      els.charactersSection.classList.add("hidden");
      return;
    }
    els.charactersSection.classList.remove("hidden");
    els.switchHint.textContent = `Смена — ${switchPrice} coin · при активном V`;

    characters.forEach((ch) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "char-btn" + (ch.active ? " active" : "");
      btn.dataset.character = ch.id;
      btn.innerHTML = `<span>${ch.name}</span><span class="badge">${ch.active ? "Активен" : "Выбрать"}</span>`;
      btn.disabled = locked || busy || ch.active;
      btn.addEventListener("click", () => purchase("switch_character", ch.id));
      els.charList.appendChild(btn);
    });
  }

  function updateV24FreeButton(remaining) {
    const btn = document.getElementById("btn-v24-free");
    if (remaining > 0) {
      btn.disabled = true;
      els.v24FreeSub.textContent = `через ${formatCooldown(remaining)}`;
    } else {
      if (!state?.locked && !busy) btn.disabled = false;
      els.v24FreeSub.textContent = "раз в 5 мин";
    }
  }

  function render(data) {
    state = data;
    const p = data.player;
    const unit = data.currency_symbol || "V";
    const shown = p.coins_display != null ? p.coins_display : p.coins;
    els.balance.textContent = shown;
    const coinEl = document.querySelector(".currency__coin");
    if (coinEl) coinEl.textContent = unit;
    renderUserWidget(p);

    if (!data.locked) {
      els.pageStatus.textContent = "Compound V · готов к покупке";
      els.pageStatus.className = "page-head__status page-head__status--ok";
    }

    const u = data.currency_symbol || "V";
    els.priceV24Paid.textContent = `${data.prices.v24_paid} ${u} · 2 боя`;
    els.priceV.textContent = `${data.prices.v} ${u}`;
    els.priceV1.textContent = `${data.prices.v1} ${u}`;
    els.priceVirus.textContent = `${data.prices.virus} ${u}`;
    els.virusHint.textContent = "Предмет в бою";

    updateV24FreeButton(data.v24_free_remaining_sec || 0);
    setLocked(!!data.locked);
    els.charactersSection.classList.add("hidden");
    setServerStatus("ok", "Соединение с сервером / надёжно");

    if (cooldownTimer) clearInterval(cooldownTimer);
    if (data.v24_free_remaining_sec > 0) {
      let left = data.v24_free_remaining_sec;
      cooldownTimer = setInterval(() => {
        left -= 1;
        if (left <= 0) {
          clearInterval(cooldownTimer);
          updateV24FreeButton(0);
        } else {
          updateV24FreeButton(left);
        }
      }, 1000);
    }
  }

  async function api(path, options) {
    const url = new URL(path, window.location.origin);
    url.searchParams.set("chat_id", chatId);
    url.searchParams.set("token", chatToken);

    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData(),
        ...(options?.headers || {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && !data.message) {
      throw new Error("Ошибка сети");
    }
    return data;
  }

  async function loadShop() {
    if (!chatId || !chatToken) {
      els.pageStatus.textContent = "Откройте из чата — /shop";
      els.pageStatus.className = "page-head__status page-head__status--warn";
      setServerStatus("err", "Нет привязки к чату");
      setLocked(true);
      return;
    }
    if (!initData()) {
      els.pageStatus.textContent = "Откройте через Telegram";
      els.pageStatus.className = "page-head__status page-head__status--warn";
      setServerStatus("err", "Нет авторизации Telegram");
      setLocked(true);
      return;
    }
    try {
      const data = await api("/api/shop");
      if (!data.ok) throw new Error(data.message || "Ошибка");
      render(data);
    } catch (e) {
      els.pageStatus.textContent = e.message || "Ошибка загрузки";
      els.pageStatus.className = "page-head__status page-head__status--warn";
      setServerStatus("err", "Соединение / ненадёжно");
      setLocked(true);
    }
  }

  async function purchase(action, character) {
    if (busy || state?.locked) return;
    busy = true;
    setLocked(state?.locked);
    try {
      const body = { action, token: chatToken };
      if (character) body.character = character;
      const data = await api("/api/purchase", {
        method: "POST",
        body: JSON.stringify(body),
      });
      showToast(data.message || (data.ok ? "Готово" : "Ошибка"), !!data.ok);
      if (data.player) {
        render({
          ...state,
          ok: true,
          locked: state?.locked,
          player: data.player,
          v24_free_remaining_sec: data.v24_free_remaining_sec ?? 0,
          characters: data.characters ?? state?.characters ?? [],
          prices: state?.prices,
        });
      }
    } catch (e) {
      showToast(e.message || "Ошибка", false);
    } finally {
      busy = false;
      setLocked(!!state?.locked);
    }
  }

  els.purchaseButtons.forEach((btn) => {
    btn.addEventListener("click", () => purchase(btn.dataset.action));
  });

  loadShop();
})();
