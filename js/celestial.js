/* Celestial data helper — loads data/celestial.json and exposes
   planet metadata + event filtering. Pure data layer; no DOM.        */
(function (global) {
  const PLANETS = [
    { key: 'mercury',    zh: '水星',   symbol: '☿', color: '#facc15' },
    { key: 'venus',      zh: '金星',   symbol: '♀', color: '#10b981' },
    { key: 'mars',       zh: '火星',   symbol: '♂', color: '#ef4444' },
    { key: 'jupiter',    zh: '木星',   symbol: '♃', color: '#3b82f6' },
    { key: 'saturn',     zh: '土星',   symbol: '♄', color: '#a16207' },
    { key: 'north_node', zh: '北交點', symbol: '☊', color: '#a855f7' },
  ];

  const ZH_TO_META = Object.fromEntries(PLANETS.map(p => [p.zh, p]));
  const KEY_TO_META = Object.fromEntries(PLANETS.map(p => [p.key, p]));

  function planetMeta(zhOrKey) {
    return ZH_TO_META[zhOrKey] || KEY_TO_META[zhOrKey] || null;
  }

  let cached = null;

  /** Returns: { meta, byYear: {YYYY: [event,...]}, all: [event,...] } */
  async function load(path) {
    if (cached) return cached;
    const url = path || (location.pathname.includes('/pages/')
      ? '../data/celestial.json'
      : 'data/celestial.json');
    const res = await fetch(url);
    const json = await res.json();
    const all = [];
    Object.keys(json.by_year || {}).sort().forEach(y => {
      (json.by_year[y] || []).forEach(e => all.push(e));
    });
    cached = { meta: json.meta, byYear: json.by_year || {}, all };
    return cached;
  }

  /** Filter events for given date window + selected planet zh names. */
  function filterEvents(events, opts = {}) {
    const start = opts.startDate || '0000-00-00';
    const end   = opts.endDate   || '9999-12-31';
    const allow = opts.planets ? new Set(opts.planets) : null;
    return events.filter(e =>
      e.date >= start && e.date <= end &&
      (!allow || allow.has(e.planet))
    );
  }

  /** Short label, e.g.  "♂↗ 白羊→金牛"  or  "♂"  if compact=true. */
  function eventLabel(ev, opts = {}) {
    const meta = planetMeta(ev.planet);
    const sym  = meta ? meta.symbol : ev.planet;
    const arrow = ev.retrograde ? '↙' : '↗';
    if (opts.compact) {
      return opts.showRetro ? `${sym}${arrow}` : sym;
    }
    const fromS = (ev.from || '').replace('座', '');
    const toS   = (ev.to   || '').replace('座', '');
    const dirChar = opts.showRetro ? arrow : '';
    return `${sym}${dirChar} ${fromS}→${toS}`;
  }

  global.Celestial = { PLANETS, planetMeta, load, filterEvents, eventLabel };
})(window);
