#!/usr/bin/env python3
"""Construye y despliega el workflow n8n "Macro Brief" (Newsquawk -> Groq -> email + Telegram).

Uso:
    python3 deploy.py            # crea/actualiza el workflow de producción (sin webhook)
    python3 deploy.py --test     # añade un webhook de prueba con path aleatorio
    python3 deploy.py --fail-test  # como --test pero con RSS roto, para probar el aviso de error

Lee N8N_BASE_URL, N8N_API_KEY y TELEGRAM_ALLOWED_CHAT_ID de ~/Documents/GitHub/kai/.env.
No escribe secretos a disco ni a stdout.
"""
import json
import os
import secrets
import sys
import urllib.request

ENV_PATH = os.path.expanduser("~/Documents/GitHub/kai/.env")
WORKFLOW_NAME = "Macro Brief — Newsquawk → Groq (Londres + NY)"
EMAIL_TO = "ivan.thomas@gmail.com"
ERROR_WORKFLOW_NAME = "Macro Brief — Error alert"

CRED_GROQ = {"id": "QFhLubUBbDaRx5ky", "name": "Groq - macro-brief"}
CRED_TELEGRAM = {"id": "AdID3yxDFdaVbI6f", "name": "Telegram - K.A.I. bot"}
CRED_GMAIL = {"id": "zkp9Vjcue4DoUav6", "name": "Gmail account"}

MODEL_CLASSIFY = "openai/gpt-oss-120b"
MODEL_SYNTH = "openai/gpt-oss-120b"

# --------------------------------------------------------------------------- JS

JS_SESSION = r"""
const q = $input.first().json.query || {};
let session = q.session;
if (!session) session = $now.setZone('Europe/Madrid').hour < 11 ? 'london' : 'ny';
return [{ json: { session } }];
"""

JS_PICK = r"""
const session = $('Session').first().json.session;
const rss = $('RSS').first().json.data;
const list = $('Daily list').first().json.data;
const dec = s => s.replace(/<!\[CDATA\[|\]\]>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").trim();

const items = [...rss.matchAll(/<item>([\s\S]*?)<\/item>/g)].map(m => {
  const b = m[1];
  const g = t => { const x = b.match(new RegExp('<' + t + '>([\\s\\S]*?)</' + t + '>')); return x ? dec(x[1]) : ''; };
  return { title: g('title'), ts: Date.parse(g('pubDate')) };
}).filter(x => x.title && !isNaN(x.ts));

const cutoff = Date.now() - (session === 'ny' ? 8 : 30) * 3600e3;
const heads = items.filter(x => x.ts >= cutoff).slice(0, 60)
  .map((x, i) => ({ i: i + 1, ts: x.ts, title: x.title.slice(0, 180) }));

const links = [...new Set([...list.matchAll(/href="(\/daily\/\d+-[^"]+)"/g)].map(m => m[1]))];
const pick = k => links.find(l => l.includes(k));
const art = session === 'ny' ? (pick('-us-market-open') || pick('-eu-market-open')) : pick('-eu-market-open');
if (!art) throw new Error('No se encontró briefing en /daily');
const week = pick('-week-in-focus');
const weekTitle = week ? week.replace(/^\/daily\/\d+-/, '').replace(/-/g, ' ') : '';

return [{ json: { session, heads, articleUrl: 'https://www.newsquawk.com' + art, weekTitle } }];
"""

JS_PREPARE = r"""
const { session, heads, articleUrl, weekTitle } = $('Pick sources').first().json;
const html = $input.first().json.data || '';
const dec = s => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#x27;|&#39;|&apos;/g, "'").replace(/&nbsp;/g, ' ');
let t = dec(html.replace(/<(script|style)[\s\S]*?<\/\1>/g, ' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ');
const pub = (t.match(/Published:\s*(\d+ \w+ \d{4},? [\d:]+ UTC)/) || [])[1] || 'fecha desconocida';
const i = t.indexOf('Newsquawk Desk');
if (i > 0) t = t.slice(i + 14);
const excerpt = t.slice(0, 8500);

const sys = 'Eres un filtro de noticias de mercado para un trader de EURUSD y XAUUSD. Recibes titulares numerados. ' +
  'Devuelve SOLO un JSON {"items":[{"i":n,"r":0|1,"u":"bull|bear|neutral","a":"USD|EUR|XAU|OIL|ALL|NONE","w":1|2|3,"t":"tema en 1-3 palabras"}]}, un objeto por titular. ' +
  'RÚBRICA. r=1 solo si mueve de verdad USD, EUR, oro, yields de EE.UU./Alemania, petróleo o apetito de riesgo global. ' +
  'r=0 para ruido: datos menores de economías pequeñas o emergentes (Turquía, Sudáfrica, Polonia, Suecia, etc.), movers de acciones sueltas, M&A, corporativo, deportes. ' +
  'w=3 SOLO para: decisiones o discursos de Fed/BCE con señal de tipos, datos clave de EE.UU. o eurozona (NFP, CPI, PCE, PMI, GDP), escalada o desescalada real en Irán/Ormuz, shocks de petróleo o yields. ' +
  'w=2 para datos relevantes de Alemania/Francia/Reino Unido/China y geopolítica secundaria. w=1 el resto. La mayoría de titulares debe ser w1 o r=0; no marques todo como w2. ' +
  'u = efecto probable sobre el USD, NO sobre el activo del titular: Fed halcón, yields al alza, aversión al riesgo, datos débiles de eurozona/UK => bull (USD sube); Fed dovish, yields a la baja, apetito de riesgo, datos fuertes de eurozona => bear (USD baja); si no está claro => neutral. ' +
  'a = activo más afectado. No expliques nada fuera del JSON.';
const user = heads.map(h => h.i + '|' + h.title).join('\n');
const body1 = {
  model: '__MODEL_CLASSIFY__', temperature: 0.1, max_completion_tokens: 3500, reasoning_effort: 'low',
  response_format: { type: 'json_object' },
  messages: [{ role: 'system', content: sys }, { role: 'user', content: user }],
};
return [{ json: { session, heads, articleUrl, weekTitle, pub, excerpt, body1 } }];
"""


JS_MARKET = r"""
const prev = $input.first().json;
const syms = [['DXY', 'DX-Y.NYB'], ['US10Y', '^TNX'], ['VIX', '^VIX'], ['EURUSD', 'EURUSD=X'], ['XAUUSD', 'GC=F']];
const rsi = (c, n = 14) => {
  if (c.length < n + 1) return null;
  let g = 0, l = 0;
  for (let i = 1; i <= n; i++) { const d = c[i] - c[i - 1]; if (d >= 0) g += d; else l -= d; }
  g /= n; l /= n;
  for (let i = n + 1; i < c.length; i++) {
    const d = c[i] - c[i - 1];
    g = (g * (n - 1) + Math.max(d, 0)) / n; l = (l * (n - 1) + Math.max(-d, 0)) / n;
  }
  return l === 0 ? 100 : 100 - 100 / (1 + g / l);
};
const market = [];
for (const [name, sym] of syms) {
  try {
    const r = await this.helpers.httpRequest({
      url: 'https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(sym) + '?range=6mo&interval=1d',
      headers: { 'User-Agent': 'Mozilla/5.0' }, json: true, timeout: 15000,
    });
    const c = r.chart.result[0].indicators.quote[0].close.filter(x => x != null);
    const last = c[c.length - 1], p1 = c[c.length - 2], p5 = c[c.length - 6];
    const sma20 = c.slice(-20).reduce((a, b) => a + b, 0) / 20;
    market.push({ name, last, d1: (last / p1 - 1) * 100, d5: (last / p5 - 1) * 100,
      d1bps: (last - p1) * 100, d5bps: (last - p5) * 100, rsi: rsi(c), vsSma: last >= sma20 ? 'sobre' : 'bajo' });
  } catch (e) { /* sin dato: se omite ese instrumento */ }
}
return [{ json: { ...prev, market } }];
"""

JS_CALENDAR = r"""
const prev = $input.first().json;
const calendar = [];
try {
  const raw = await this.helpers.httpRequest({
    url: 'https://nfs.faireconomy.media/ff_calendar_thisweek.json',
    headers: { 'User-Agent': 'Mozilla/5.0' }, json: true, timeout: 15000,
  });
  const tz = 'Europe/Madrid';
  const day = d => d.toLocaleDateString('sv-SE', { timeZone: tz });
  const hm = d => d.toLocaleTimeString('es-ES', { timeZone: tz, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const now = new Date();
  const today = day(now), tomorrow = day(new Date(now.getTime() + 864e5));
  const lvl = { High: 'alto', Medium: 'medio', Low: 'bajo' };
  const all = raw
    .filter(x => ['USD', 'EUR'].includes(x.country) && lvl[x.impact])
    .map(x => { const d = new Date(x.date); return { ts: d.getTime(), day: day(d), time: hm(d), cur: x.country,
      impact: lvl[x.impact], title: x.title, forecast: x.forecast || '', previous: x.previous || '' }; });
  // hoy: todo USD (cualquier impacto) y EUR medio/alto; mañana: solo impacto alto
  const ev = all.filter(e => e.day === today ? (e.cur === 'USD' || e.impact !== 'bajo') : (e.day === tomorrow && e.impact === 'alto'));
  const rank = e => ({ alto: 0, medio: 1, bajo: 2 })[e.impact];
  const todayEv = ev.filter(e => e.day === today).sort((a, b) => rank(a) - rank(b) || a.ts - b.ts).slice(0, 16);
  const tomEv = ev.filter(e => e.day === tomorrow).sort((a, b) => a.ts - b.ts).slice(0, 3);
  [...todayEv, ...tomEv].sort((a, b) => a.ts - b.ts).forEach((e, i) => calendar.push({
    id: i + 1, when: e.day === today ? 'hoy' : 'mañana', published: e.ts < now.getTime(),
    time: e.time, cur: e.cur, impact: e.impact, title: e.title, forecast: e.forecast, previous: e.previous }));
} catch (e) { /* sin calendario: el informe sale igual */ }
return [{ json: { ...prev, calendar } }];
"""

JS_SYNTH_REQ = r"""
const { session, heads, articleUrl, weekTitle, pub, excerpt } = $('Prepare LLM inputs').first().json;
let cls = {};
try { cls = JSON.parse($input.first().json.choices[0].message.content); } catch (e) { cls = { items: [] }; }
const tag = new Map((cls.items || []).map(x => [x.i, x]));
let sel = heads.map(h => ({ ...h, c: tag.get(h.i) }));
const tagged = sel.some(h => h.c);
if (tagged) sel = sel.filter(h => h.c && h.c.r === 1);
sel.sort((a, b) => ((b.c && b.c.w) || 0) - ((a.c && a.c.w) || 0) || b.ts - a.ts);
sel = sel.filter(h => !h.c || h.c.w >= 2).slice(0, 18);
const hhmm = ts => new Date(ts).toISOString().slice(11, 16);
const lines = sel.map(h => (h.c ? '[' + h.c.a + '|' + h.c.u + '|w' + h.c.w + '] ' : '') + h.title + ' (' + hhmm(h.ts) + ' UTC)').join('\n');

const market = $('Market data').first().json.market || [];
const mline = m => m.name + ': ' + m.last.toFixed(m.name === 'EURUSD' ? 4 : 2) + ' | 1d ' +
  (m.name === 'US10Y' ? m.d1bps.toFixed(0) + 'pb' : m.d1.toFixed(2) + '%') + ' | 5d ' +
  (m.name === 'US10Y' ? m.d5bps.toFixed(0) + 'pb' : m.d5.toFixed(2) + '%') + ' | RSI14 diario ' +
  (m.rsi == null ? 'n/d' : m.rsi.toFixed(0)) + ' | ' + m.vsSma + ' SMA20';
const mtxt = market.map(mline).join('\n');
const cal = $('Economic calendar').first().json.calendar || [];
const ctxt = cal.map(e => e.id + '| ' + e.when + ' ' + e.time + ' (hora España) ' + e.cur + ' [' + e.impact + '] ' + e.title +
  ' | prevista ' + (e.forecast || 'n/d') + ' | anterior ' + (e.previous || 'n/d') + (e.published ? ' | YA PUBLICADO' : '')).join('\n');
const sd = $getWorkflowStaticData('global');
const today = $now.setZone('Europe/Madrid').toFormat('yyyy-MM-dd');
const prev = session === 'ny' && sd.london && sd.london.date === today ? sd.london.report : null;

const sys = 'Eres analista macro para un trader retail de EURUSD y XAUUSD (opera CRT/SMC, sesiones Londres y NY). ' +
  'Con los titulares y el briefing recibidos, estima el sesgo del dólar para la sesión. Reglas: ' +
  '1) Usa SOLO información de los textos recibidos; no inventes cifras, niveles ni eventos. ' +
  '2) Si las señales se contradicen, di "mixto". No fuerces una dirección. ' +
  '3) No des señales de entrada ni niveles de precio. ' +
  '4) Pondera sobre todo: señales de Fed/BCE (tipos, discursos), yields de EE.UU., petróleo/Irán-Ormuz, DXY y oro tal como los describe el briefing. Un movimiento pequeño del DXY no basta para un sesgo. ' +
  '5) "eventos": rellénalo siempre que el briefing liste datos u oradores; SOLO los de la línea "Looking ahead"/"Speakers" del briefing y de la semana; NO inventes horas ni uses la hora de publicación de un titular como hora del evento; si no consta hora, no la pongas. ' +
  '6) Responde en español, conciso. ' +
  '8) "calendario": una entrada {"id","sube","escenarios","publicado"} por cada evento del CALENDARIO, con su mismo id. ' +
  '"sube" = efecto sobre el USD si el dato supera la previsión: "+" (USD sube), "-" (USD baja) o "0" (sin dirección, p. ej. oradores sin cifra). Pautas: inflación (IPC, PCE, deflactor y índices de precios del PIB), empleo, PIB, gasto/ingresos y PMI de EE.UU. superiores a la previsión suelen fortalecer al USD (sube "+"; los precios altos elevan las expectativas de tipos de la Fed); paro, peticiones de subsidio, déficit comercial mayor o inventarios de crudo mayores suelen debilitarlo ("-"); datos de la eurozona fuertes debilitan al USD ("-") y flojos lo fortalecen. ' +
  '"escenarios" = 1-2 frases con el efecto si supera y si decepciona, teniendo en cuenta el contexto del briefing (expectativas de Fed/BCE), SOLO para eventos de impacto alto o medio; vacío para los de impacto bajo. No pronostiques la cifra. ' +
  '"publicado" (solo eventos YA PUBLICADOS) = resultado frente a previsión y su efecto en el USD SOLO si consta en los titulares o el briefing; si no consta, "no consta en los titulares". Vacío en pendientes. ' +
  'Los de impacto bajo salen junto a otros: trátalos como parte del mismo bloque de datos. Si hay eventos de impacto alto en USD, menciónalos en riesgos (volatilidad a esa hora). ' +
  '7) Si hay DATOS DE MERCADO, úsalos como hechos: relaciona DXY, yields y VIX con el sesgo. Menciona el RSI solo si está en sobrecompra (>70), sobreventa (<30) o contradice claramente el sesgo; un RSI extremo en la dirección del sesgo es riesgo de agotamiento o rebote (ponlo en riesgos), no confirmación. No inventes otros niveles. ' +
  'Devuelve SOLO JSON con esta forma: {"sesgo_usd":"alcista|bajista|neutral|mixto","confianza":"baja|media|alta",' +
  '"resumen":"2-3 frases","drivers":["3-5 puntos"],"eventos":["evento con hora UTC si consta"],' +
  '"eurusd":"1-2 frases","xauusd":"1-2 frases","riesgos":["1-3 puntos"],"calendario":[{"id":1,"sube":"+","escenarios":"","publicado":""}],"cambios":"solo si hay informe previo: qué cambió desde Londres; si no, cadena vacía"}.';
const user = 'SESIÓN: ' + (session === 'ny' ? 'pre-Nueva York' : 'apertura Londres') + '\n' +
  'BRIEFING NEWSQUAWK (publicado ' + pub + '):\n' + excerpt + '\n\n' +
  'CALENDARIO ECONÓMICO (Forex Factory, hora de España):\n' + (ctxt || 'no disponible') + '\n\n' +
  'DATOS DE MERCADO (Yahoo Finance, diario, última vela en curso):\n' + (mtxt || 'no disponibles') + '\n\n' +
  'SEMANA: ' + weekTitle + '\n\n' +
  'TITULARES FILTRADOS (formato [activo|efecto USD|impacto]):\n' + lines +
  (prev ? '\n\nINFORME PREVIO DE LONDRES (para comparar):\n' + JSON.stringify(prev) : '');
const body2 = {
  model: '__MODEL_SYNTH__', temperature: 0.2, max_completion_tokens: 3200, reasoning_effort: 'medium',
  response_format: { type: 'json_object' },
  messages: [{ role: 'system', content: sys }, { role: 'user', content: user }],
};
return [{ json: { session, articleUrl, pub, body2, nSel: sel.length, nAll: heads.length } }];
"""

JS_FORMAT = r"""
const { session, articleUrl, pub, nSel, nAll } = $('Build synthesis request').first().json;
let r;
try { r = JSON.parse($input.first().json.choices[0].message.content); }
catch (e) { throw new Error('Groq devolvió JSON inválido en la síntesis'); }
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const arr = a => Array.isArray(a) ? a : [];
const label = session === 'ny' ? 'Pre-Nueva York' : 'Apertura Londres';
const date = $now.setZone('Europe/Madrid').toFormat('dd/MM/yyyy');
const mark = { alcista: '▲', bajista: '▼', neutral: '■', mixto: '◆' }[r.sesgo_usd] || '■';
const market = $('Market data').first().json.market || [];
const fv = m => m.name === 'US10Y' ? m.last.toFixed(2) + '% (' + (m.d1bps >= 0 ? '+' : '') + m.d1bps.toFixed(0) + 'pb)'
  : m.last.toFixed(m.name === 'EURUSD' ? 4 : m.name === 'XAUUSD' ? 0 : 2) + ' (' + (m.d1 >= 0 ? '+' : '') + m.d1.toFixed(2) + '%)';
const rs = m => m.rsi == null ? 'n/d' : Math.round(m.rsi);
const mTg = !market.length ? '<i>Datos de mercado no disponibles esta vez (Yahoo)</i>\n\n' : market.length ? '<b>Mercado</b> (RSI14 diario)\n' + market.map(m => esc(m.name) + ' ' + esc(fv(m)) + ' · RSI ' + rs(m)).join('\n') + '\n\n' : '';
const mHtml = !market.length ? '<p style="color:#b45309">Datos de mercado no disponibles esta vez (Yahoo).</p>' : market.length ? '<h3>Mercado</h3><table style="border-collapse:collapse;font-size:14px"><tr style="color:#666;text-align:left"><th style="padding:2px 12px 2px 0">Activo</th><th style="padding:2px 12px 2px 0">Último (1d)</th><th style="padding:2px 12px 2px 0">5d</th><th style="padding:2px 12px 2px 0">RSI14</th><th>vs SMA20</th></tr>' +
  market.map(m => '<tr><td style="padding:2px 12px 2px 0"><b>' + esc(m.name) + '</b></td><td style="padding:2px 12px 2px 0">' + esc(fv(m)) + '</td><td style="padding:2px 12px 2px 0">' +
    (m.name === 'US10Y' ? (m.d5bps >= 0 ? '+' : '') + m.d5bps.toFixed(0) + 'pb' : (m.d5 >= 0 ? '+' : '') + m.d5.toFixed(2) + '%') +
    '</td><td style="padding:2px 12px 2px 0">' + rs(m) + '</td><td>' + m.vsSma + '</td></tr>').join('') + '</table>' : '';
const calendar = $('Economic calendar').first().json.calendar || [];
const cmap = new Map((Array.isArray(r.calendario) ? r.calendario : []).map(x => [Number(x.id), x]));
const rows = calendar.map(e => { const c = cmap.get(e.id) || {}; return { ...e, esc: c.escenarios || '', pub: c.publicado || '', sube: c.sube || '' }; });
const eff = e => e.pub ? '✓ ' + e.pub : e.esc ? '→ ' + e.esc
  : e.sube === '+' ? '→ si supera la previsión: USD ▲' : e.sube === '-' ? '→ si supera la previsión: USD ▼' : '';
const cut = t => t.length <= 3900 ? t : t.slice(0, t.lastIndexOf('\n', 3900));
const calTg = rows.length ? '<b>Calendario (hora España)</b>\n' + rows.map(e => e.time + ' ' + e.cur + ' ' + esc(e.title) + ' [' + e.impact + ']' +
    (e.when === 'mañana' ? ' (mañana)' : '') + (e.forecast ? ' · prevista ' + esc(e.forecast) : '') + (e.previous ? ' · anterior ' + esc(e.previous) : '') +
    (eff(e) ? '\n   ' + esc(eff(e)) : '')).join('\n') + '\n\n'
  : '<i>Calendario no disponible esta vez</i>\n\n';
const calHtml = rows.length ? '<h3>Calendario económico (hora España)</h3><table style="border-collapse:collapse;font-size:14px"><tr style="color:#666;text-align:left"><th style="padding:3px 10px 3px 0">Hora</th><th style="padding:3px 10px 3px 0">Evento</th><th style="padding:3px 10px 3px 0">Impacto</th><th style="padding:3px 10px 3px 0">Prevista</th><th style="padding:3px 10px 3px 0">Anterior</th><th>Efecto en el USD</th></tr>' +
  rows.map(e => '<tr style="vertical-align:top;border-top:1px solid #eee"><td style="padding:3px 10px 3px 0;white-space:nowrap">' + (e.when === 'mañana' ? 'mañana ' : '') + e.time + '</td><td style="padding:3px 10px 3px 0"><b>' + esc(e.cur) + '</b> ' + esc(e.title) +
    '</td><td style="padding:3px 10px 3px 0">' + e.impact + '</td><td style="padding:3px 10px 3px 0">' + esc(e.forecast) + '</td><td style="padding:3px 10px 3px 0">' + esc(e.previous) + '</td><td>' + esc(eff(e)) + '</td></tr>').join('') + '</table>'
  : '<p style="color:#b45309">Calendario no disponible esta vez.</p>';
const bullets = a => arr(a).map(x => '• ' + esc(x)).join('\n');

const tg = '<b>Macro Brief — ' + label + ' · ' + date + '</b>\n' +
  mark + ' USD <b>' + esc(r.sesgo_usd) + '</b> (confianza ' + esc(r.confianza) + ')\n\n' +
  esc(r.resumen) + '\n\n' +
  (r.cambios ? '<b>Cambios desde Londres</b>\n' + esc(r.cambios) + '\n\n' : '') +
  mTg + '<b>EURUSD</b> ' + esc(r.eurusd) + '\n<b>XAUUSD</b> ' + esc(r.xauusd) + '\n\n' +
  (!rows.length && arr(r.eventos).length ? '<b>Eventos</b>\n' + bullets(r.eventos) + '\n\n' : '') +
  (arr(r.riesgos).length ? '<b>Riesgos</b>\n' + bullets(r.riesgos) : '');

const li = a => arr(a).map(x => '<li>' + esc(x) + '</li>').join('');
const html = '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:640px;color:#1a1a1a;line-height:1.5">' +
  '<h2 style="margin:0 0 4px">Macro Brief — ' + label + '</h2>' +
  '<div style="color:#666;font-size:13px;margin-bottom:16px">' + date + ' · briefing Newsquawk ' + esc(pub) + ' · ' + nSel + ' de ' + nAll + ' titulares relevantes</div>' +
  '<p style="font-size:18px;margin:0 0 12px">' + mark + ' Sesgo USD: <b>' + esc(r.sesgo_usd) + '</b> · confianza ' + esc(r.confianza) + '</p>' +
  '<p>' + esc(r.resumen) + '</p>' +
  (r.cambios ? '<h3>Cambios desde Londres</h3><p>' + esc(r.cambios) + '</p>' : '') +
  mHtml + calHtml + '<h3>Drivers</h3><ul>' + li(r.drivers) + '</ul>' +
  '<h3>EURUSD</h3><p>' + esc(r.eurusd) + '</p>' +
  '<h3>XAUUSD</h3><p>' + esc(r.xauusd) + '</p>' +
  (!rows.length && arr(r.eventos).length ? '<h3>Eventos</h3><ul>' + li(r.eventos) + '</ul>' : '') +
  (arr(r.riesgos).length ? '<h3>Riesgos</h3><ul>' + li(r.riesgos) + '</ul>' : '') +
  '<p style="color:#888;font-size:12px;margin-top:24px">Sesgo orientativo generado por IA a partir de titulares públicos. No es una señal de entrada. Calendario: Forex Factory (previsiones pueden diferir de otras plataformas). Fuente: <a href="' + esc(articleUrl) + '">Newsquawk</a>.</p></div>';

if (session === 'london') {
  const sd = $getWorkflowStaticData('global');
  sd.london = { date: $now.setZone('Europe/Madrid').toFormat('yyyy-MM-dd'), report: r };
}
const subject = 'Macro Brief ' + label + ' · USD ' + r.sesgo_usd + ' · ' + date;
return [{ json: { subject, html, tg: cut(tg), tgCal: cut(calTg.trim()) } }];
"""


# ------------------------------------------------------------------------ build

def load_env():
    env = {}
    for line in open(ENV_PATH):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    return env


def code_node(id_, name, js, pos):
    js = js.replace("__MODEL_CLASSIFY__", MODEL_CLASSIFY).replace("__MODEL_SYNTH__", MODEL_SYNTH)
    return {"id": id_, "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2,
            "position": pos, "parameters": {"jsCode": js.strip()}}


def http_get(id_, name, url, pos):
    return {"id": id_, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": pos, "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 4000,
            "parameters": {
                "method": "GET", "url": url, "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "User-Agent", "value": "Mozilla/5.0 (compatible; TradingOrbe-MacroBrief/1.0)"}]},
                "options": {"response": {"response": {"responseFormat": "text", "outputPropertyName": "data"}}},
            }}


def groq_node(id_, name, body_expr, pos):
    return {"id": id_, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": pos, "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 65000,
            "credentials": {"httpHeaderAuth": CRED_GROQ},
            "parameters": {
                "method": "POST", "url": "https://api.groq.com/openai/v1/chat/completions",
                "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
                "sendBody": True, "specifyBody": "json", "jsonBody": body_expr, "options": {},
            }}


def build(chat_id, test_path=None, error_wf=None, fail=False):
    rss_url = "https://www.newsquawk.com/does-not-exist" if fail else "https://www.newsquawk.com/headlines-feed.xml"
    nodes = [
        {"id": "n1", "name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
         "position": [0, 0], "parameters": {"rule": {"interval": [
             {"field": "cronExpression", "expression": "0 8 * * 1-5"},
             {"field": "cronExpression", "expression": "30 13 * * 1-5"}]}}},
        code_node("n2", "Session", JS_SESSION, [220, 0]),
        http_get("n3", "RSS", rss_url, [440, 0]),
        http_get("n4", "Daily list", "https://www.newsquawk.com/daily", [660, 0]),
        code_node("n5", "Pick sources", JS_PICK, [880, 0]),
        {**http_get("n6", "Fetch briefing", "={{ $json.articleUrl }}", [1100, 0])},
        code_node("n7", "Prepare LLM inputs", JS_PREPARE, [1320, 0]),
        code_node("n7b", "Market data", JS_MARKET, [1430, -160]),
        code_node("n7c", "Economic calendar", JS_CALENDAR, [1430, 160]),
        groq_node("n8", "Groq classify", "={{ JSON.stringify($json.body1) }}", [1540, 0]),
        {"id": "n9", "name": "Wait 60s", "type": "n8n-nodes-base.wait", "typeVersion": 1.1,
         "position": [1760, 0], "parameters": {"resume": "timeInterval", "amount": 60, "unit": "seconds"}},
        code_node("n10", "Build synthesis request", JS_SYNTH_REQ, [1980, 0]),
        groq_node("n11", "Groq synthesize", "={{ JSON.stringify($json.body2) }}", [2200, 0]),
        code_node("n12", "Format report", JS_FORMAT, [2420, 0]),
        {"id": "n13", "name": "Send email", "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
         "position": [2660, -100], "credentials": {"gmailOAuth2": CRED_GMAIL},
         "parameters": {"resource": "message", "operation": "send", "sendTo": EMAIL_TO,
                        "subject": "={{ $json.subject }}", "emailType": "html", "message": "={{ $json.html }}",
                        "options": {"appendAttribution": False}}},
        {"id": "n15", "name": "Send Telegram calendar", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
         "position": [2900, 100], "credentials": {"telegramApi": CRED_TELEGRAM},
         "parameters": {"resource": "message", "operation": "sendMessage", "chatId": chat_id,
                        "text": "={{ $('Format report').first().json.tgCal }}",
                        "additionalFields": {"parse_mode": "HTML", "appendAttribution": False}}},
        {"id": "n14", "name": "Send Telegram", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
         "position": [2660, 100], "credentials": {"telegramApi": CRED_TELEGRAM},
         "parameters": {"resource": "message", "operation": "sendMessage", "chatId": chat_id,
                        "text": "={{ $json.tg }}",
                        "additionalFields": {"parse_mode": "HTML", "appendAttribution": False}}},
    ]
    chain = ["Session", "RSS", "Daily list", "Pick sources", "Fetch briefing", "Prepare LLM inputs",
             "Market data", "Economic calendar", "Groq classify", "Wait 60s", "Build synthesis request", "Groq synthesize", "Format report"]
    conns = {"Schedule": {"main": [[{"node": "Session", "type": "main", "index": 0}]]}}
    for a, b in zip(chain, chain[1:]):
        conns[a] = {"main": [[{"node": b, "type": "main", "index": 0}]]}
    conns["Format report"] = {"main": [[{"node": "Send email", "type": "main", "index": 0},
                                        {"node": "Send Telegram", "type": "main", "index": 0}]]}
    conns["Send Telegram"] = {"main": [[{"node": "Send Telegram calendar", "type": "main", "index": 0}]]}
    if test_path:
        nodes.append({"id": "n0", "name": "Test webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                      "position": [0, 200], "webhookId": secrets.token_hex(8),
                      "parameters": {"httpMethod": "GET", "path": test_path, "responseMode": "onReceived", "options": {}}})
        conns["Test webhook"] = {"main": [[{"node": "Session", "type": "main", "index": 0}]]}
    settings = {"executionOrder": "v1", "timezone": "Europe/Madrid"}
    if error_wf:
        settings["errorWorkflow"] = error_wf
    return {"name": WORKFLOW_NAME, "nodes": nodes, "connections": conns, "settings": settings}


def build_error_workflow(chat_id):
    text = ("={{ '⚠ Macro Brief falló\nNodo: ' + ($json.execution.lastNodeExecuted || '?') + '\nError: ' + "
            "String(($json.execution.error && $json.execution.error.message) || 'desconocido').slice(0, 300) + "
            "'\nEjecución: ' + ($json.execution.url || '') }}")
    text = text.replace("\n", "\\n")  # el salto va escapado dentro del literal JS de la expresión
    nodes = [
        {"id": "e1", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "typeVersion": 1,
         "position": [0, 0], "parameters": {}},
        {"id": "e2", "name": "Alert Telegram", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
         "position": [240, 0], "credentials": {"telegramApi": CRED_TELEGRAM},
         "parameters": {"resource": "message", "operation": "sendMessage", "chatId": chat_id, "text": text,
                        "additionalFields": {"appendAttribution": False}}},
    ]
    return {"name": ERROR_WORKFLOW_NAME, "nodes": nodes,
            "connections": {"Error Trigger": {"main": [[{"node": "Alert Telegram", "type": "main", "index": 0}]]}},
            "settings": {"executionOrder": "v1"}}


def api(env, method, path, body=None):
    base = env["N8N_BASE_URL"].rstrip("/") + "/api/v1"
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": env["N8N_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def upsert(env, wf):
    _, lst = api(env, "GET", "/workflows?limit=100")
    existing = next((w for w in lst.get("data", []) if w["name"] == wf["name"]), None)
    if existing:
        wid = existing["id"]
        api(env, "POST", f"/workflows/{wid}/deactivate")
        s, r = api(env, "PUT", f"/workflows/{wid}", wf)
    else:
        s, r = api(env, "POST", "/workflows", wf)
        wid = r.get("id") if isinstance(r, dict) else None
    if s != 200:
        print("error", wf["name"], s, r)
        sys.exit(1)
    return wid


def main():
    env = load_env()
    fail = "--fail-test" in sys.argv
    test = "--test" in sys.argv or fail
    test_path = "mb-test-" + secrets.token_hex(12) if test else None
    chat_id = env["TELEGRAM_ALLOWED_CHAT_ID"]

    err_id = upsert(env, build_error_workflow(chat_id))
    api(env, "POST", f"/workflows/{err_id}/activate")  # un Error Trigger solo dispara si está activo
    print("error workflow", err_id)
    wid = upsert(env, build(chat_id, test_path, err_id, fail))
    s, _ = api(env, "POST", f"/workflows/{wid}/activate")
    print("workflow", wid, "activate", s)
    if test:
        print("webhook_url", env["N8N_BASE_URL"].rstrip("/") + "/webhook/" + test_path)


if __name__ == "__main__":
    main()
