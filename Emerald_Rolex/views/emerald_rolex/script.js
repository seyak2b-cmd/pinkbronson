/*  Emerald Rolex v4 — OBS Chat Viewer (WebSocket + Firebase settings)  */

const WS_URL   = "ws://localhost:8765";
const MAX_MSGS = 20;
const container = document.getElementById("chat-container");

// ── Firebase 設定同期 ──────────────────────────────────
const firebaseConfig = {
    apiKey:      "AIzaSyAjkMsdvypCH4BsoNcjSNp8GX6_bLbKsA8",
    authDomain:  "seya-chat-trans.firebaseapp.com",
    databaseURL: "https://seya-chat-trans-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId:   "seya-chat-trans"
};
if (!firebase.apps.length) firebase.initializeApp(firebaseConfig);
const db      = firebase.database();
const styleEl = document.getElementById("dynamic-style");

// OBS 設定: Firebase /emerald_rolex/settings から動的CSS生成
db.ref('emerald_rolex/settings').on('value', snap => {
    if (!snap.exists()) return;
    const s = snap.val();

    const px   = (v, d, mn, mx) => { const n = parseInt(v,10); return (isNaN(n)||n<mn||n>mx) ? d : n; };
    const bool = (v, d) => typeof v === 'boolean' ? v : d;
    const enm  = (v, ok, d) => ok.includes(v) ? v : d;

    const fontSize   = px(s.fontSize,  20, 8,  72);
    const iconSize   = px(s.iconSize,  34, 16, 120);
    const alignDir   = enm(s.alignDir, ['left','right'], 'left');
    const showName   = bool(s.showName,    true);
    const showIcons  = bool(s.showIcons,   true);
    const showBadges = bool(s.showBadges,  true);
    const showMsg    = bool(s.showComment, true);
    const showJa     = bool(s.showJa,      false);  // 日本語訳を表示するか

    let css = `
        :root {
            --er-font-size: ${fontSize}px;
            --er-icon-size: ${iconSize}px;
        }
        .message { font-size: var(--er-font-size) !important; }
        .avatar, .avatar-ph, .avatar-wrap { width: var(--er-icon-size) !important; height: var(--er-icon-size) !important; }
        .avatar-ph { font-size: calc(var(--er-icon-size) * 0.45) !important; }
    `;

    if (alignDir === 'right') css += `
        #chat-container { align-items: flex-end; }
        .chat-msg { align-self: flex-end; }
        .user-row { flex-direction: row-reverse; }
        .message, .ja-message { text-align: right; }
    `;

    if (!showName)    css += `.username { display: none !important; }`;
    if (!showIcons)   css += `.avatar-wrap { display: none !important; }`;
    if (!showBadges)  css += `.badge-wrap { display: none !important; }`;
    if (!showMsg)     css += `.message { display: none !important; }`;
    if (!showJa)      css += `.ja-message { display: none !important; }`;

    // アイコンのみモード
    if (showIcons && !showMsg) css += `
        .chat-msg { background:transparent; border:1px solid var(--accent); border-radius:50px;
                    padding:4px 10px 4px 4px; box-shadow:none; min-width:0; }
        .user-row { border:none; margin:0; padding:0; }
        .ja-message { display: none !important; }
    `;

    if (styleEl) styleEl.textContent = css;
});

// ── WebSocket ─────────────────────────────────────────
async function connect() {
    let token = "";
    try {
        const res  = await fetch("ws_token.json?_=" + Date.now());
        const data = await res.json();
        token = data.token || "";
    } catch (e) {
        console.warn("[ER] ws_token.json 読込失敗。3秒後リトライ。", e);
        setTimeout(connect, 3000);
        return;
    }

    let socket;
    try { socket = new WebSocket(WS_URL); }
    catch (e) { setTimeout(connect, 3000); return; }

    socket.onopen    = () => { console.log("[ER] WS OK"); socket.send(JSON.stringify({ auth: token })); };
    socket.onclose   = () => setTimeout(connect, 3000);
    socket.onerror   = (e) => console.error("[ER] WS error:", e);
    socket.onmessage = (ev) => {
        try { addMessage(JSON.parse(ev.data)); }
        catch (e) { console.error("[ER] parse error:", e); }
    };
}

// ── メッセージ追加 ────────────────────────────────────
function addMessage({ name="?", message="", ja="", en="", lang="",
                      badge="none", badge_img="", avatar="", color="#AAFF00",
                      is_first=false, bits=null }) {

    // アバター
    const initial = (name||"?")[0].toUpperCase();
    const avatarHtml = avatar
        ? `<div class="avatar-wrap">
               <img class="avatar" src="${esc(avatar)}" alt="${esc(name)}"
                   onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
               <div class="avatar-ph" style="display:none">${esc(initial)}</div>
           </div>`
        : `<div class="avatar-wrap"><div class="avatar-ph">${esc(initial)}</div></div>`;

    // バッジ
    const BADGE_CDN = {
        broadcaster: "https://static-cdn.jtvnw.net/badges/v1/5527c58c-fb7d-422d-b71b-f309dcb85cc1/2",
        moderator:   "https://static-cdn.jtvnw.net/badges/v1/3267646d-33f0-4b17-b3df-f923a41db1d6/2",
        vip:         "https://static-cdn.jtvnw.net/badges/v1/b817aba4-fad8-49e2-b88a-7cc744dfa6ec/2",
        subscriber:  "https://static-cdn.jtvnw.net/badges/v1/86828e5e-d523-4f80-8a42-c4f7c9171b58/2",
        partner:     "https://static-cdn.jtvnw.net/badges/v1/d12a2e27-16f6-41d0-ab77-b780518f00a3/2",
    };
    let badgeHtml = "";
    if (badge && badge !== "none") {
        const src = (badge_img && badge_img !== "") ? badge_img : (BADGE_CDN[badge] || "");
        badgeHtml = src
            ? `<div class="badge-wrap">
                   <img class="badge-img" src="${esc(src)}" alt="${esc(badge)}"
                       onerror="this.style.display='none';this.nextElementSibling.style.display='inline-block'">
                   <span class="badge-txt ${esc(badge)}" style="display:none">${badge[0].toUpperCase()}</span>
               </div>`
            : `<div class="badge-wrap"><span class="badge-txt ${esc(badge)}">${badge[0].toUpperCase()}</span></div>`;
    }

    // ユーザー名カラー
    const nameStyle = /^#[0-9a-fA-F]{6}$/.test(color)
        ? `style="color:${color}; text-shadow:1px 1px 0 #000,0 0 8px ${color};"`
        : `style="color:#CCFF88;"`;

    // first-msg / bits バッジ
    const extraBadges =
        (is_first ? `<span class="badge-txt" style="background:#3388FF;color:#fff;font-size:8px;padding:1px 4px;border-radius:2px;">NEW</span>` : "") +
        (bits     ? `<span class="badge-txt" style="background:#FFD700;color:#000;font-size:8px;padding:1px 4px;border-radius:2px;">💎${bits}</span>` : "");

    // 日本語訳 (非日本語発言のみ表示)
    const jaHtml = (ja && lang !== "ja")
        ? `<div class="ja-message">${esc(ja)}</div>`
        : "";

    const el = document.createElement("div");
    el.className = "chat-msg";
    el.innerHTML = `
        <div class="user-row">
            ${avatarHtml}${badgeHtml}${extraBadges}
            <span class="username" ${nameStyle}>${esc(name)}</span>
        </div>
        <div class="message">${esc(message)}</div>
        ${jaHtml}`;

    el.addEventListener("animationend", () => {
        el.style.animation = "none";
        el.style.opacity   = "1";
        el.style.transform = "none";
    }, { once: true });

    requestAnimationFrame(() => {
        while (container.children.length >= MAX_MSGS)
            container.removeChild(container.firstChild);
        container.appendChild(el);
    });
}

function esc(s) {
    return String(s ?? "")
        .replace(/&/g,"&amp;").replace(/</g,"&lt;")
        .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

connect();
