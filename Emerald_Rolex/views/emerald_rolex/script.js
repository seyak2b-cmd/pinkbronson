/*  Emerald Rolex - script.js  (OBS Chat Viewer) */

const WS_URL = "ws://localhost:8765";
const MAX_MSGS = 20;
const container = document.getElementById("chat-container");

// ── Twitch 公開 CDN バッジ (Client-ID 不要・フォールバック用) ──
const BADGE_CDN = {
    broadcaster: "https://static-cdn.jtvnw.net/badges/v1/5527c58c-fb7d-422d-b71b-f309dcb85cc1/2",
    moderator: "https://static-cdn.jtvnw.net/badges/v1/3267646d-33f0-4b17-b3df-f923a41db1d6/2",
    vip: "https://static-cdn.jtvnw.net/badges/v1/b817aba4-fad8-49e2-b88a-7cc744dfa6ec/2",
    subscriber: "https://static-cdn.jtvnw.net/badges/v1/86828e5e-d523-4f80-8a42-c4f7c9171b58/2",
    partner: "https://static-cdn.jtvnw.net/badges/v1/d12a2e27-16f6-41d0-ab77-b780518f00a3/2",
};

// ══════════════════════════════════════════════
// Firebase 同期 (リアルタイムデザイン反映)
// ══════════════════════════════════════════════
const firebaseConfig = {
    apiKey: "AIzaSyAjkMsdvypCH4BsoNcjSNp8GX6_bLbKsA8",
    authDomain: "seya-chat-trans.firebaseapp.com",
    databaseURL: "https://seya-chat-trans-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "seya-chat-trans"
};
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
}

const db = firebase.database();
const styleEl = document.getElementById("dynamic-style");

// Firebase値をCSSに安全に挿入するためのサニタイズ関数
function sanitizePx(val, def, min, max) {
    const n = parseInt(val, 10);
    return (isNaN(n) || n < min || n > max) ? def : n;
}
function sanitizeBool(val, def) {
    return typeof val === 'boolean' ? val : def;
}
function sanitizeEnum(val, allowed, def) {
    return allowed.includes(val) ? val : def;
}

db.ref('emerald_rolex/settings').on('value', snap => {
    if (!snap.exists()) return;
    const s = snap.val();

    const fontSize  = sanitizePx(s.fontSize,  20, 8, 72);
    const iconSize  = sanitizePx(s.iconSize,   34, 16, 120);
    const alignDir  = sanitizeEnum(s.alignDir, ['left', 'right'], 'left');
    const showName  = sanitizeBool(s.showName,    true);
    const showIcons = sanitizeBool(s.showIcons,   true);
    const showBadges= sanitizeBool(s.showBadges,  true);
    const showComment=sanitizeBool(s.showComment, true);

    let css = `
        :root {
            --er-font-size: ${fontSize}px;
            --er-icon-size: ${iconSize}px;
        }
        .message { font-size: var(--er-font-size) !important; }
        .avatar, .avatar-ph, .avatar-wrap { width: var(--er-icon-size) !important; height: var(--er-icon-size) !important; }
        .avatar-ph { font-size: calc(var(--er-icon-size) * 0.45) !important; }
    `;

    if (alignDir === 'right') {
        css += `
            #chat-container { align-items: flex-end; }
            .chat-msg { align-self: flex-end; }
            .user-row { flex-direction: row-reverse; }
            .message { text-align: right; }
        `;
    }

    if (!showName)    css += ` .username { display: none !important; } `;
    if (!showIcons)   css += ` .avatar-wrap { display: none !important; } `;
    if (!showBadges)  css += ` .badge-wrap { display: none !important; } `;
    if (!showComment) css += ` .message { display: none !important; } `;

    if (showIcons && !showComment) {
        css += `
            .chat-msg { background:transparent; border:1px solid var(--accent); border-radius:50px; padding:4px 10px 4px 4px; box-shadow:none; min-width:0; }
            .user-row { border:none; margin:0; padding:0; }
        `;
    }

    if (styleEl) styleEl.textContent = css;
});

// ══════════════════════════════════════════════
// WebSocket 接続 (トークン認証付き)
// ══════════════════════════════════════════════
async function connect() {
    let token = "";
    try {
        const res = await fetch("ws_token.json?_=" + Date.now());
        const data = await res.json();
        token = data.token || "";
    } catch (e) {
        console.warn("[ER] ws_token.json 読み込み失敗。3秒後にリトライ。", e);
        setTimeout(connect, 3000);
        return;
    }

    let socket;
    try { socket = new WebSocket(WS_URL); }
    catch (e) { setTimeout(connect, 3000); return; }

    socket.onopen = () => {
        console.log("[ER] Bridge 接続 OK");
        socket.send(JSON.stringify({ auth: token }));
    };
    socket.onclose = () => setTimeout(connect, 3000);
    socket.onerror = (e) => console.error("[ER] Error:", e);
    socket.onmessage = (ev) => {
        try { addMessage(JSON.parse(ev.data)); }
        catch (e) { console.error("[ER] parse error:", e); }
    };
}

// ══════════════════════════════════════════════
// メッセージ追加
// OBS 対策:
//   - requestAnimationFrame でフレームに同期
//   - animationend 後に animation を解除して GPU を解放
//   - 古いノードを先に削除（DOM を軽量に保つ）
// ══════════════════════════════════════════════
function addMessage({ name = "?", message = "", badge = "none", badge_img = "", avatar = "", color = "#AAFF00" }) {

    // ── アバター ──
    const initial = (name || "?")[0].toUpperCase();
    let avatarHtml;
    if (avatar && avatar !== "") {
        avatarHtml = `<div class="avatar-wrap">
            <img class="avatar" src="${esc(avatar)}" alt="${esc(name)}"
                onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
            <div class="avatar-ph" style="display:none">${esc(initial)}</div>
        </div>`;
    } else {
        avatarHtml = `<div class="avatar-wrap"><div class="avatar-ph">${esc(initial)}</div></div>`;
    }

    // ── バッジ ──
    let badgeHtml = "";
    if (badge && badge !== "none") {
        const imgSrc = (badge_img && badge_img !== "") ? badge_img : (BADGE_CDN[badge] || "");
        if (imgSrc) {
            badgeHtml = `<div class="badge-wrap">
                <img class="badge-img" src="${esc(imgSrc)}" alt="${esc(badge)}"
                    onerror="this.style.display='none';this.nextElementSibling.style.display='inline-block'">
                <span class="badge-txt ${esc(badge)}" style="display:none">${badge[0].toUpperCase()}</span>
            </div>`;
        } else {
            badgeHtml = `<div class="badge-wrap"><span class="badge-txt ${esc(badge)}">${badge[0].toUpperCase()}</span></div>`;
        }
    }

    // ── ユーザー名 ──
    const nameStyle = /^#[0-9a-fA-F]{6}$/.test(color)
        ? `style="color:${color}; text-shadow:1px 1px 0 #000,0 0 8px ${color};"`
        : `style="color:#CCFF88;"`;

    const el = document.createElement("div");
    el.className = "chat-msg";
    el.innerHTML = `
        <div class="user-row">
            ${avatarHtml}
            ${badgeHtml}
            <span class="username" ${nameStyle}>${esc(name)}</span>
        </div>
        <div class="message">${esc(message)}</div>`;

    // アニメーション終了後に animation を解除 → GPU レイヤー解放
    el.addEventListener("animationend", () => {
        el.style.animation = "none";
        el.style.opacity = "1";
        el.style.transform = "none";
    }, { once: true });

    requestAnimationFrame(() => {
        while (container.children.length >= MAX_MSGS) {
            container.removeChild(container.firstChild);
        }
        container.appendChild(el);
    });
}

function esc(s) {
    return String(s ?? "")
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

connect();
