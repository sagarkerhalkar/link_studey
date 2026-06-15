(() => {
  'use strict';
  const root = document.querySelector('[data-tracker-root]');
  if (!root) return;

  const destination = root.dataset.destination;
  const collectUrl = root.dataset.collectUrl;
  let redirected = false;

  const redirectNow = () => {
    if (redirected) return;
    redirected = true;
    window.location.replace(destination);
  };

  // Redirect reliability remains primary. The collector gets a bounded window
  // to finish so the dashboard normally receives enriched device information.
  const hardTimeout = window.setTimeout(redirectNow, 1200);

  const safeStorageId = () => {
    try {
      const key = 'la-device-v4';
      let value = window.localStorage.getItem(key);
      if (!value) {
        value = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`)
          .replace(/[^a-zA-Z0-9-]/g, '')
          .slice(0, 96);
        window.localStorage.setItem(key, value);
      }
      return value;
    } catch (_error) {
      return '';
    }
  };

  const digest = async (value) => {
    try {
      const bytes = new TextEncoder().encode(value);
      const hash = await crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(hash))
        .map((byte) => byte.toString(16).padStart(2, '0'))
        .join('');
    } catch (_error) {
      return '';
    }
  };

  const getClientHints = async () => {
    const uaData = navigator.userAgentData;
    let high = {};
    if (uaData && uaData.getHighEntropyValues) {
      try {
        high = await uaData.getHighEntropyValues([
          'architecture', 'bitness', 'model', 'platform', 'platformVersion',
          'uaFullVersion', 'fullVersionList', 'wow64',
        ]);
      } catch (_error) {
        high = {};
      }
    }
    return {
      userAgent: navigator.userAgent || '',
      platform: high.platform || (uaData && uaData.platform) || navigator.platform || '',
      platformVersion: high.platformVersion || '',
      model: high.model || '',
      mobile: uaData ? Boolean(uaData.mobile) : /Mobile|Android|iPhone|iPad/i.test(navigator.userAgent || ''),
      brands: high.fullVersionList || (uaData && uaData.brands) || [],
      architecture: high.architecture || '',
      bitness: high.bitness || '',
      uaFullVersion: high.uaFullVersion || '',
      language: navigator.language || '',
      languages: Array.isArray(navigator.languages) ? navigator.languages.slice(0, 8) : [],
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
      screenWidth: window.screen ? window.screen.width : 0,
      screenHeight: window.screen ? window.screen.height : 0,
      colorDepth: window.screen ? window.screen.colorDepth : 0,
      pixelRatio: window.devicePixelRatio || 1,
      maxTouchPoints: navigator.maxTouchPoints || 0,
      hardwareConcurrency: navigator.hardwareConcurrency || 0,
      deviceMemory: navigator.deviceMemory || 0,
      standalone: Boolean(window.navigator.standalone || window.matchMedia('(display-mode: standalone)').matches),
    };
  };

  const sendWithFetch = async (payload) => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 750);
    try {
      const response = await fetch(collectUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        credentials: 'same-origin',
        keepalive: true,
        cache: 'no-store',
        signal: controller.signal,
      });
      return response.ok;
    } catch (_error) {
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  };

  const send = async () => {
    const localStorageId = safeStorageId();
    const client = await getClientHints();
    const fingerprintSource = JSON.stringify({
      localStorageId,
      platform: client.platform,
      model: client.model,
      screenWidth: client.screenWidth,
      screenHeight: client.screenHeight,
      pixelRatio: client.pixelRatio,
      maxTouchPoints: client.maxTouchPoints,
      timezone: client.timezone,
      language: client.language,
      userAgent: client.userAgent,
    });
    const deviceSignatureSource = JSON.stringify({
      screenShort: Math.min(client.screenWidth || 0, client.screenHeight || 0),
      screenLong: Math.max(client.screenWidth || 0, client.screenHeight || 0),
      colorDepth: client.colorDepth || 0,
      pixelRatio: Number(client.pixelRatio || 0).toFixed(2),
      maxTouchPoints: client.maxTouchPoints || 0,
      hardwareConcurrency: client.hardwareConcurrency || 0,
      deviceMemory: Number(client.deviceMemory || 0).toFixed(1),
      timezone: client.timezone || '',
      language: client.language || '',
    });
    const [fingerprintHash, deviceSignatureHash] = await Promise.all([
      digest(fingerprintSource),
      digest(deviceSignatureSource),
    ]);
    client.deviceSignatureHash = deviceSignatureHash;
    const payload = JSON.stringify({
      localStorageId,
      fingerprintHash,
      deviceSignatureHash,
      documentReferrer: document.referrer || '',
      client,
    });

    const fetched = await sendWithFetch(payload);
    if (fetched) return;

    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(collectUrl, new Blob([payload], { type: 'application/json' }));
      }
    } catch (_error) {
      // The server-only event remains valid and explicitly labelled as such.
    }
  };

  send().finally(() => {
    window.clearTimeout(hardTimeout);
    redirectNow();
  });
})();
