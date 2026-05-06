/* Celestial helpers — planet metadata, JSON loader, and an in-browser
   ephemeris (NASA JPL approximate orbital elements + Kepler solve)
   so any page can ask "where is each planet today?" without a backend. */
(function (global) {
  // ===== Metadata =================================================
  const PLANETS = [
    { key: 'sun',        zh: '太陽',   symbol: '☉', color: '#f59e0b' },
    { key: 'mercury',    zh: '水星',   symbol: '☿', color: '#facc15' },
    { key: 'venus',      zh: '金星',   symbol: '♀', color: '#10b981' },
    { key: 'mars',       zh: '火星',   symbol: '♂', color: '#ef4444' },
    { key: 'jupiter',    zh: '木星',   symbol: '♃', color: '#3b82f6' },
    { key: 'saturn',     zh: '土星',   symbol: '♄', color: '#a16207' },
    { key: 'uranus',     zh: '天王星', symbol: '♅', color: '#06b6d4' },
    { key: 'neptune',    zh: '海王星', symbol: '♆', color: '#6366f1' },
    { key: 'pluto',      zh: '冥王星', symbol: '♇', color: '#be185d' },
    { key: 'north_node', zh: '北交點', symbol: '☊', color: '#a855f7' },
  ];
  const ZH_TO_META  = Object.fromEntries(PLANETS.map(p => [p.zh,  p]));
  const KEY_TO_META = Object.fromEntries(PLANETS.map(p => [p.key, p]));
  function planetMeta(zhOrKey) {
    return ZH_TO_META[zhOrKey] || KEY_TO_META[zhOrKey] || null;
  }

  const ZODIAC = ['白羊座','金牛座','雙子座','巨蟹座','獅子座','處女座',
                  '天秤座','天蠍座','射手座','摩羯座','水瓶座','雙魚座'];

  // ===== Ephemeris (NASA JPL approx_pos, J2000) ===================
  const J2000 = 2451545.0;
  const DEG = Math.PI / 180;

  // Each: [a0, a/cy, e0, e/cy, I0, I/cy, L0, L/cy, peri0, peri/cy, node0, node/cy]
  const ELEMENTS = {
    mercury: [0.38709927, 0.00000037, 0.20563593, 0.00001906,
              7.00497902, -0.00594749, 252.25032350, 149472.67411175,
              77.45779628, 0.16047689, 48.33076593, -0.12534081],
    venus:   [0.72333566, 0.00000390, 0.00677672, -0.00004107,
              3.39467605, -0.00078890, 181.97909950, 58517.81538729,
              131.60246718, 0.00268329, 76.67984255, -0.27769418],
    earth:   [1.00000261, 0.00000562, 0.01671123, -0.00004392,
              -0.00001531, -0.01294668, 100.46457166, 35999.37244981,
              102.93768193, 0.32327364, 0.0, 0.0],
    mars:    [1.52371034, 0.00001847, 0.09339410, 0.00007882,
              1.84969142, -0.00813131, -4.55343205, 19140.30268499,
              -23.94362959, 0.44441088, 49.55953891, -0.29257343],
    jupiter: [5.20288700, -0.00011607, 0.04838624, -0.00013253,
              1.30439695, -0.00183714, 34.39644051, 3034.74612775,
              14.72847983, 0.21252668, 100.47390909, 0.20469106],
    saturn:  [9.53667594, -0.00125060, 0.05386179, -0.00050991,
              2.48599187, 0.00193609, 49.95424423, 1222.49362201,
              92.59887831, -0.41897216, 113.66242448, -0.28867794],
    uranus:  [19.18916464, -0.00196176, 0.04725744, -0.00004397,
              0.77263783, -0.00242939, 313.23810451, 428.48202785,
              170.95427630, 0.40805281, 74.01692503, 0.04240589],
    neptune: [30.06992276, 0.00026291, 0.00859048, 0.00005105,
              1.77004347, 0.00035372, -55.12002969, 218.45945325,
              44.96476227, -0.32241464, 131.78422574, -0.00508664],
    pluto:   [39.48211675, -0.00031596, 0.24882730, 0.00005170,
              17.14001206, 0.00004818, 238.92903833, 145.20780515,
              224.06891629, -0.04062942, 110.30393684, -0.01183482],
  };

  function jdOf(date) {
    let y = date.getUTCFullYear();
    let m = date.getUTCMonth() + 1;
    const d = date.getUTCDate()
            + (date.getUTCHours() + date.getUTCMinutes() / 60) / 24;
    if (m <= 2) { y -= 1; m += 12; }
    const A = Math.floor(y / 100);
    const B = 2 - A + Math.floor(A / 4);
    return Math.floor(365.25 * (y + 4716))
         + Math.floor(30.6001 * (m + 1))
         + d + B - 1524.5;
  }

  function kepler(M, e) {
    let E = M;
    for (let i = 0; i < 60; i++) {
      const f = E - e * Math.sin(E) - M;
      const dE = f / (1 - e * Math.cos(E));
      E -= dE;
      if (Math.abs(dE) < 1e-9) break;
    }
    return E;
  }

  function helioPos(body, T) {
    const el = ELEMENTS[body];
    const a    = el[0]  + el[1]  * T;
    const e    = el[2]  + el[3]  * T;
    const I    = el[4]  + el[5]  * T;
    const L    = el[6]  + el[7]  * T;
    const peri = el[8]  + el[9]  * T;
    const node = el[10] + el[11] * T;
    const om = peri - node;
    let M = ((L - peri) % 360 + 540) % 360 - 180;
    const E = kepler(M * DEG, e);
    const xp = a * (Math.cos(E) - e);
    const yp = a * Math.sqrt(Math.max(0, 1 - e * e)) * Math.sin(E);
    const cO = Math.cos(node * DEG), sO = Math.sin(node * DEG);
    const cw = Math.cos(om   * DEG), sw = Math.sin(om   * DEG);
    const cI = Math.cos(I    * DEG), sI = Math.sin(I    * DEG);
    return [
      (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp,
      (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp,
      (sw * sI)                 * xp + (cw * sI)                 * yp,
    ];
  }

  function geoLongitude(body, T) {
    const [xE, yE] = helioPos('earth', T);
    let x, y;
    if (body === 'sun') { x = -xE; y = -yE; }
    else { const [xP, yP] = helioPos(body, T); x = xP - xE; y = yP - yE; }
    return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
  }

  function northNodeLongitude(JD) {
    const T = (JD - J2000) / 36525;
    const O = 125.04452 - 1934.13626197 * T
            + 0.0020708 * T * T + T * T * T / 450000;
    return ((O % 360) + 360) % 360;
  }

  /** Compute geocentric ecliptic longitude (degrees) for a body at the
      given JS Date. body is internal key (eg 'mars') OR 'north_node'. */
  function bodyLongitude(bodyKey, jsDate) {
    const JD = jdOf(jsDate);
    if (bodyKey === 'north_node') return northNodeLongitude(JD);
    const T = (JD - J2000) / 36525;
    return geoLongitude(bodyKey, T);
  }

  /** Snapshot all 10 bodies at a given JS Date. */
  function positionsAt(jsDate) {
    const yesterday = new Date(jsDate.getTime() - 86400000);
    return PLANETS.map(p => {
      const lon  = bodyLongitude(p.key, jsDate);
      const lonY = bodyLongitude(p.key, yesterday);
      const delta = (((lon - lonY) % 360) + 540) % 360 - 180;
      const retrograde = p.key === 'north_node' ? true : delta < 0;
      const idx = Math.floor(((lon % 360) + 360) % 360 / 30);
      const within = ((lon % 360) + 360) % 360 - idx * 30;
      const deg = Math.floor(within);
      const min = Math.floor((within - deg) * 60);
      return {
        ...p,
        longitude: +lon.toFixed(3),
        sign: ZODIAC[idx],
        signIndex: idx,
        deg, min,
        retrograde,
        speedPerDay: +delta.toFixed(3),
      };
    });
  }

  // ===== JSON loader for prebuilt sign-change events ==============
  let cached = null;
  async function load(path) {
    if (cached) return cached;
    const url = path || (location.pathname.includes('/pages/')
      ? '../data/celestial.json'
      : 'data/celestial.json');
    const res = await fetch(url + '?t=' + Date.now(), { cache: 'no-cache' });
    const json = await res.json();
    const all = [];
    Object.keys(json.by_year || {}).sort().forEach(y => {
      (json.by_year[y] || []).forEach(e => all.push(e));
    });
    cached = { meta: json.meta, byYear: json.by_year || {}, all };
    return cached;
  }

  function filterEvents(events, opts = {}) {
    const start = opts.startDate || '0000-00-00';
    const end   = opts.endDate   || '9999-12-31';
    const allow = opts.planets ? new Set(opts.planets) : null;
    return events.filter(e =>
      e.date >= start && e.date <= end &&
      (!allow || allow.has(e.planet))
    );
  }

  function eventLabel(ev, opts = {}) {
    const meta = planetMeta(ev.planet);
    const sym = meta ? meta.symbol : ev.planet;
    const shortName = (ev.planet || '').replace(/星|交點/g, '');

    if (ev.type === 'station') {
      const dirText = ev.direction === 'R-start' ? '逆' : '順';
      const arrow   = ev.direction === 'R-start' ? '↙' : '↗';
      const tail    = opts.showRetro ? (opts.compact ? arrow : ' ' + arrow) : '';
      return `${shortName}${dirText}${tail}`;
    }

    const arrow = ev.retrograde ? '↙' : '↗';
    if (opts.compact) {
      return opts.showRetro ? `${sym}${arrow}` : sym;
    }
    const fromS = (ev.from || '').replace('座', '');
    const toS   = (ev.to   || '').replace('座', '');
    const dirChar = opts.showRetro ? arrow : '';
    return `${sym}${dirChar} ${fromS}→${toS}`;
  }

  global.Celestial = {
    PLANETS, ZODIAC, planetMeta,
    bodyLongitude, positionsAt,
    load, filterEvents, eventLabel,
  };
})(window);
