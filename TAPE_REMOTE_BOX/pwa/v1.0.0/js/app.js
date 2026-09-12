/**
 * AAIQ TAPE Remote PWA — Application Core
 * Connects to AAIQ Relay Box Pico / TAPERC Public Gateway (/api/v1/...)
 */

// Service Worker Registration
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch((err) => {
    console.debug('ServiceWorker registration skipped:', err);
  });
}

// PWA Install Prompt Handling
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('btnInstall');
  if (btn) btn.style.display = 'inline-block';
});

function getBrowserEnv() {
  const ua = navigator.userAgent || '';
  const isIos = (/iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) && !window.MSStream;
  const isMac = /Macintosh|Mac OS X/i.test(ua) && !isIos;
  const isAndroid = /Android/i.test(ua);
  const isWindows = /Windows/i.test(ua);

  let browser = 'other';
  if (/FxiOS/i.test(ua)) browser = 'ios-firefox';
  else if (/CriOS/i.test(ua)) browser = 'ios-chrome';
  else if (/EdgiOS/i.test(ua)) browser = 'ios-edge';
  else if (/Firefox/i.test(ua)) browser = 'firefox';
  else if (/Edg/i.test(ua)) browser = 'edge';
  else if (/Chrome/i.test(ua)) browser = 'chrome';
  else if (/Safari/i.test(ua) && (isIos || isMac)) browser = 'safari';

  return { isIos, isMac, isAndroid, isWindows, browser };
}

function updateIosModalContent() {
  const titleEl = document.getElementById('iosModalTitle');
  const bodyEl = document.getElementById('iosModalBody');
  if (!bodyEl) return;

  const env = getBrowserEnv();
  if (env.isIos) {
    if (env.browser === 'ios-firefox') {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Firefox op iOS</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
        'Firefox op iOS ondersteunt PWA-installatie niet zoals Safari.<br>' +
        '1. Tik in Firefox op het menu (<b>&#8943;</b>).<br>' +
        '2. Kies <b>Openen in Safari</b>.<br>' +
        '3. Tik in Safari op de <b>Deel-knop</b> (Share) en kies <b>Zet op beginscherm</b> (+).</p>';
    } else if (env.browser === 'ios-chrome') {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Chrome op iOS</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
        'Chrome op iOS ondersteunt PWA-installatie niet zoals Safari.<br>' +
        '1. Tik op het <b>Deel-icoon</b> in de adresbalk of menu.<br>' +
        '2. Tik op <b>Zet op beginscherm</b> (of open in Safari &rarr; Deel &rarr; Zet op beginscherm).<br>' +
        '3. Tik op <b>Voeg toe</b>.</p>';
    } else if (env.browser === 'ios-edge' || /OPiOS/i.test(navigator.userAgent)) {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;color:#cbd5e1;">Deze browser op iOS ondersteunt PWA-installatie niet zoals Safari. Open deze pagina in Safari om TAPE aan het beginscherm toe te voegen.</p>';
    } else {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Open in Safari en kies Share &rarr; Add to Home Screen.</p>' +
        '<p style="font-size:12px;color:#94a3b8;text-align:left;line-height:1.6;">' +
        '1. Tik op de <b>Deel-knop</b> (Share) in Safari.<br>' +
        '2. Scroll naar beneden en tik op <b>Zet op beginscherm</b> (+).<br>' +
        '3. Tik rechtsboven op <b>Voeg toe</b>.</p>';
    }
  } else if (env.isMac && env.browser === 'safari') {
    if (titleEl) titleEl.textContent = 'Installatie op Mac (Safari)';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Safari Web App op macOS</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      '1. Open het Safari-menu bovenaan.<br>' +
      '2. Kies <b>Archief &rarr; Voeg toe aan Dock...</b> (File &rarr; Add to Dock).<br>' +
      '3. Klik op <b>Voeg toe</b> om de app direct vanuit je Dock te openen.</p>';
  } else if (env.browser === 'firefox') {
    if (titleEl) titleEl.textContent = 'Web App op Firefox';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Firefox Desktop</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      'Firefox ondersteunt deze pagina direct als snelle Web App.<br>' +
      '• Druk op <b>Ctrl + D</b> om een bladwijzer te maken.<br>' +
      '• Of sleep het slot-icoontje uit de adresbalk naar je bureaublad.</p>';
  } else {
    if (titleEl) titleEl.textContent = 'App Installeren';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Web App Installatie</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      '• <b>Chrome / Edge:</b> Klik op het installatie-icoontje in de adresbalk.<br>' +
      '• <b>Mobiel:</b> Kies via het browsermenu <i>Toevoegen aan startscherm</i>.</p>';
  }
}

function promptInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
      deferredPrompt = null;
      const btn = document.getElementById('btnInstall');
      if (btn) btn.style.display = 'none';
    });
  } else {
    toggleIosModal(true);
  }
}

function toggleIosModal(show) {
  const m = document.getElementById('iosModal');
  if (m) {
    if (show) updateIosModalContent();
    m.style.display = show ? 'flex' : 'none';
  }
}

function toggleInfoModal(show) {
  const m = document.getElementById('infoModal');
  if (m) m.style.display = show ? 'flex' : 'none';
}

function toggleMenu(show) {
  const menu = document.getElementById('dropdownMenu');
  const btn = document.getElementById('btnMenu');
  if (!menu) return;
  const isVisible = menu.classList.contains('show');
  const next = show !== undefined ? show : !isVisible;
  if (next) {
    menu.classList.add('show');
    if (btn) btn.classList.add('active');
  } else {
    menu.classList.remove('show');
    if (btn) btn.classList.remove('active');
  }
}

function handleOutsideMenu(e) {
  const menuContainer = document.querySelector('.menu-container');
  if (menuContainer && !menuContainer.contains(e.target)) {
    toggleMenu(false);
  }
}
document.addEventListener('click', handleOutsideMenu);
document.addEventListener('touchstart', handleOutsideMenu, { passive: true });

// State
let isPowered = false;
let isSending = false;
let currentMotion = null;
let activeTransport = null;

function updateTransportUI(activeName) {
  activeTransport = activeName;
  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (!btn) return;
    btn.classList.remove('active-fn');
    const led = btn.querySelector('.led-indicator');
    if (led) led.classList.remove('on');
  });

  if (activeName) {
    const map = {
      'PLAY': 'btn-r1',
      'STOP': 'btn-r2',
      'RECORD': 'btn-r3',
      'PAUSE': 'btn-r4',
      'FF': 'btn-r5',
      'REW': 'btn-r6'
    };
    const id = map[activeName];
    if (id) {
      const activeBtn = document.getElementById(id);
      if (activeBtn) {
        activeBtn.classList.add('active-fn');
        const activeLed = activeBtn.querySelector('.led-indicator');
        if (activeLed) activeLed.classList.add('on');
      }
    }
  }
}

function updatePowerUI(powered) {
  isPowered = !!powered;
  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (btn) btn.disabled = !isPowered;
  });

  const btnPower = document.getElementById('btnPower');
  if (btnPower) {
    if (isPowered) {
      btnPower.classList.remove('off');
      btnPower.classList.add('on');
    } else {
      btnPower.classList.remove('on');
      btnPower.classList.add('off');
      updateTransportUI(null);
      setReelsMotion(null);
    }
  }
}

async function togglePower() {
  if (isSending) return;
  const targetState = !isPowered;

  // Power OFF block: only allow Power OFF when STOP is active (or no transport active yet).
  if (!targetState && activeTransport && activeTransport !== 'STOP') {
    console.warn('Power OFF blocked while transport function is active (' + activeTransport + ')');
    return;
  }

  isSending = true;
  try {
    const res = await fetch('/api/v1/relay/8', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({state: targetState})
    });
    if (res.ok) {
      const data = await res.json();
      const actualState = (data && data.state !== undefined) ? data.state : targetState;
      updatePowerUI(actualState);
    } else {
      checkInitialPower();
    }
  } catch(e) {
    console.error('Power API error:', e);
    checkInitialPower();
  } finally {
    isSending = false;
  }
}

async function checkInitialPower() {
  try {
    const res = await fetch('/api/v1/status', {cache: 'no-store'});
    if (res.ok) {
      const data = await res.json();
      const r8State = (data.relay && (data.relay[8] === 1 || data.relay['8'] === 1)) || (data.relay8 === true);
      updatePowerUI(!!r8State);
    }
  } catch(e) {
    console.debug('Status fetch error:', e);
  }
}

function setReelsMotion(motionClass) {
  const left = document.getElementById('reelLeft');
  const right = document.getElementById('reelRight');
  if (left) left.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  if (right) right.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  currentMotion = motionClass;
}

async function handleTransport(relayNum, name, motion) {
  if (!isPowered || isSending) return;
  isSending = true;

  if (navigator.vibrate) {
    try { navigator.vibrate(35); } catch(e){}
  }

  const btn = document.getElementById('btn-r' + relayNum);
  if (btn) btn.classList.add('pressed');

  try {
    const res = await fetch('/api/v1/relay/' + relayNum + '/pulse', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({duration_ms: 100})
    });
    if (res.ok) {
      updateTransportUI(name);
      if (motion !== undefined) setReelsMotion(motion);
    }
  } catch(e) {
    console.error('Transport command error:', e);
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove('pressed');
      isSending = false;
    }, 150);
  }
}

// Logo Handling
const GIT_LOGO_URL = 'https://raw.githubusercontent.com/ljvankempen/AAIQ-PWA-Assets/main/logo.png';
const LOGO_CACHE_KEY = 'aaiq_tape_logo_v1';

async function initLogo() {
  const logoImg = document.getElementById('headerLogo');
  if (!logoImg) return;

  function setLogoSrc(src) {
    if (src) logoImg.src = src;
  }

  try {
    const res = await fetch(GIT_LOGO_URL, { cache: 'no-cache' });
    if (res.ok) {
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = function() {
        const dataUrl = reader.result;
        try {
          localStorage.setItem(LOGO_CACHE_KEY, dataUrl);
        } catch(e) {}
        setLogoSrc(dataUrl);
      };
      reader.readAsDataURL(blob);
      return;
    }
  } catch(e) {
    // Offline / Git unreachable
  }

  try {
    const cached = localStorage.getItem(LOGO_CACHE_KEY);
    if (cached) {
      setLogoSrc(cached);
      return;
    }
  } catch(e) {}

  logoImg.onerror = function() {
    logoImg.style.display = 'none';
  };
}

window.addEventListener('DOMContentLoaded', () => {
  checkInitialPower();
  initLogo();
  // Periodically check power and status
  setInterval(checkInitialPower, 5000);
});
