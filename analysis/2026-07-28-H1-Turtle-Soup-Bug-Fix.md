# H1 Turtle Soup — Bug Real Encontrado y Corregido

**Fecha:** 2026-07-28
**Contexto:** Validación de valor real antes de comprometerse a usar TradingOrbe. El backtest anterior (2025-06-02) reportó 0 trades en EURUSD y lo atribuyó a "estrategia muy selectiva". Esa conclusión no estaba verificada.

## Validación en TradingView (datos reales)

| Par | Periodo M15 | Trades |
|---|---|---|
| EURUSD | Ene 2024–Jun 2025 (backtest previo) | 0 |
| XAUUSD | Abr–Jul 2026 (~3 meses) | 0 |
| GBPUSD | Abr–Jul 2026 (~3 meses) | 0 |

0 trades en 3 pares distintos, incluyendo XAUUSD (el más volátil, recomendado explícitamente por el propio análisis anterior). Eso descarta "selectividad por diseño" como única explicación.

## Bug encontrado

Consultado directamente el notebook de metodología CRT (`02763094-8e89-4408-a18e-d96fa67eef7d`) para no adivinar. Protocolo real de confirmación H1 Turtle Soup:

1. Mientras se forma la vela H4 C2, localizar la vela H1 **concreta** que perfora el nivel de C1 — esa vela se convierte en la nueva referencia (LTF C1).
2. La confirmación es que una vela H1 **posterior** barra el extremo de **esa vela de contacto específica** y cierre de vuelta dentro de su rango.

**Lo que hacía el código (`crt-ob-backtest.pine` y `crt-unified.pine`):**
- Usaba la vela H1 *inmediatamente anterior* (rolling `h1_prev_high/low`) como referencia a barrer — no la vela de contacto específica.
- Exigía además que la vela quedara **dentro del rango C1 completo** (`ts_inside_c1`), que ya está desactualizado en cuanto arranca C2 (el setup existe precisamente porque el precio ya salió de ese rango).

Combinación que hacía la confirmación casi geométricamente imposible: pedía que el precio, ya en fase de expansión fuera del rango C1, volviera a quedar contenido dentro de ese mismo rango. Coincide exactamente con el patrón observado: el estado se quedaba siempre en `H1 CONF: ✗`.

## Fix aplicado

Reescrita la sección H1 Turtle Soup en ambos indicadores (`crt-ob-backtest.pine`, `crt-unified.pine`):
- Nuevo tracking: `contact_found` / `ltf_c1_high` / `ltf_c1_low` — detecta la vela H1 de contacto durante `h4_state==2` (formación de C2).
- La confirmación ahora barre y reclama el extremo de esa vela de contacto específica, no la vela H1 genérica anterior ni el rango C1 completo.
- Compilado en TradingView sin errores (solo warning de versión Pine v5→v6, no bloqueante).

## Estado de la validación — honesto

**No se pudo re-testear con volumen estadístico suficiente.** La API de TradingView usada en la automatización limitó el historial M15 cargable a ~5 días (~500 barras) en esta sesión, pese a que en un intento aislado sí cargó ~3 meses de XAUUSD. No es un límite del código corregido — es una limitación de la sesión de datos.

En los ~5 días disponibles tras el fix (XAUUSD, tendencia sostenida sin estructura de rango-barrido clara), no se formó ningún setup completo — resultado esperado dado que ni siquiera se completó un ciclo C1→C2→C3 en esa ventana, no indica que el fix no funcione.

## Próximo paso real

Validación estadística pendiente. Dos caminos:
1. **Dejarlo correr en real** — el indicador ya está en el chart de TradingView (XAUUSD M15) con el fix aplicado. Revisar en unos días/semana si `H1 CONF` pasa a `✓` alguna vez y si se acumulan trades.
2. **Cargar más historial manualmente** en la app (scroll manual suele traer más barras que la automatización) y re-consultar la tabla de stats.

No se declara esto "arreglado y validado" — se declara "bug real identificado y corregido contra la fuente de metodología, pendiente de confirmar con datos que de verdad produce setups viables".
