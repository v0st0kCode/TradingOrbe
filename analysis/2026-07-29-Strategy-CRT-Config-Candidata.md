# Config candidata — CRT Multi-TF Strategy (29 jul 2026)

**Fichero:** `indicators/crt-strategy.pine`. Estrategia nativa (`strategy()`, Strategy Tester de TradingView), no motor de backtest manual.

## Contexto

Sesión larga de iteración sobre el modelo de entrada/SL/TP, corrigiendo varios bugs de interpretación por el camino (ver más abajo). Este es el primer resultado que el usuario considera bueno — se guarda como punto de referencia antes de seguir ajustando, para no perderlo si las siguientes pruebas empeoran.

## Modelo final (a fecha de este checkpoint)

- **Entrada:** H4 mitigado (C2 barre C1 y cierra dentro) + H1 mitigado en la misma dirección (Turtle Soup H1 autocontenido) → entrada **early** (Turtle Soup, justo tras el barrido H1, sin esperar C3 ni pullback OB M15). M15 solo afina el *momento* de la entrada, no da niveles.
- **SL:** mecha de la vela H4 (C2) que mitigó el rango, ± 3 pips buffer. Nunca H1, nunca un mínimo fijo en pips.
- **TP final (TP2):** `c1_low + (c1_high - c1_low) * tp_pct_range` (o simétrico para bajista) — **90% del rango H4** a mitigar por defecto, aunque el test bueno usó **75%** (`tp_pct_range=0.75`).
- **TP1:** 50% del camino entre entrada y TP final.
- **Filtro de calidad:** `use_min_rr=true`, `min_rr=1` (RR mínimo 1:1 — nota: el usuario habló en algún momento de 1:3 y 1:2.5 antes de asentarse en 1, ver hallazgos más abajo).
- **Cierre:** EOD activado (`use_eod_close=true`, `eod_close_hour=21`).

## Inputs exactos de la config candidata

| Input | Valor |
|---|---|
| C3 confirm window (H4 bars) | 10 |
| Setup persistence (H4 bars) | 4 |
| Require Daily Bias | false |
| Early entry (Turtle Soup) | true |
| Forzar cierre EOD | true |
| EOD close hour | 21 |
| Aplicar filtro RR mínimo | true |
| RR mínimo para entrar | 1 |
| TP final — % del rango H4 a mitigar | 0.75 |

(Nota: en el momento de esta captura el panel también mostraba `TP1 RR multiple`, `TP2 RR multiple` y `Cap TP2 at dol_level` — esos inputs quedaron **muertos** de una iteración anterior del modelo y ya no afectan al resultado. Se eliminaron del código inmediatamente después de este checkpoint.)

## Resultado (EURUSD M15, rango de fechas completo probado por el usuario)

| Métrica | Valor |
|---|---|
| Total trades | 39 (22 largos, 17 cortos) |
| Ganadoras | 26 |
| Perdedoras | 9 |
| Win rate | 66.67% (largo 59.09%, corto 76.47%) |
| Beneficio medio / pérdida media | 1.534 (largo 1.653, corto 0.932) |
| Media de barras por operación | 11 (largo 13, corto 8) |
| Mayor pérdida en % de pérdida bruta | 22.80% |

## Caveat explícito — no dar por robusto todavía

- **39 trades es muestra pequeña.** 2-3 trades de diferencia mueven el win rate varios puntos.
- No probado todavía en periodo distinto (fuera de muestra) ni en otro par (XAUUSD, GBPUSD) — pendiente antes de confiar en el edge.
- `setup_max_bars=4` y `c3_window=10` son permisivos — vigilar sobreajuste a este dataset concreto.

## Hallazgos importantes del proceso (para no repetir errores)

1. **Bug de timeframe del chart:** en un punto de la sesión el chart estaba en H4 en vez de M15 — esto rompe la detección del pulso H1 (`h1_just_confirmed`), que necesita resolución más fina que H1 para no perderse 3 de cada 4 cierres H1. Producía resultados absurdos (766-1560 trades, win rate 12-26%, media de barras=2-3). **Siempre verificar timeframe del chart = M15 antes de confiar en cualquier resultado.**
2. El objetivo TP no es RR fijo ni equilibrio del rango C1 — es un **porcentaje configurable del rango H4** medido desde el extremo ya mitigado hacia el extremo por mitigar (SL en la mecha C2, TP final al 75-90% del rango).
3. El SL correcto es **siempre la mecha H4 (C2)**, nunca H1 ni un floor fijo en pips — intentos anteriores con SL basado en H1 o con floor de 15 pips dieron resultados peores/erráticos.

## ACTUALIZACIÓN — muestra grande revela que NO es robusta

Al repetir esta misma config exacta con un rango de fechas mayor (157 trades en vez de 39), el resultado se desploma:

| Métrica | 39 trades (ventana corta) | 157 trades (ventana larga) |
|---|---|---|
| Win rate | 66.67% | 36.94% |
| Beneficio medio / pérdida media | 1.534 | 0.807 |
| Media de barras por operación | 11 | 6 |

**Conclusión: los 39 trades eran una muestra pequeña y afortunada, no un edge real.** Con muestra grande el ratio cae por debajo de 1 (perdedor de media). Esta config NO debe tratarse como validada ni usarse como base para producción.

**Lección para el resto del desarrollo:** fijar un único rango de fechas grande y consistente (todo el histórico disponible) como ventana de test estándar desde ahora — cualquier resultado bueno en una ventana corta debe confirmarse en la ventana completa antes de considerarse una señal real, no una casualidad de muestra.

## Próximo paso

No hay config validada todavía. Antes de seguir ajustando parámetros a ciegas: fijar la ventana de test (histórico completo), y evaluar si el modelo de entrada (H4+H1+M15) tiene algún edge real de base, o si hace falta revisar la detección misma (no solo SL/TP) contra la teoría CRT.
