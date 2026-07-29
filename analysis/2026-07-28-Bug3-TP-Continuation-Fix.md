# Bug 3 — Fix del modelo TP/SL de continuación (28 jul 2026, sesión 2)

**Contexto:** continuación de `2026-07-28-H1-Turtle-Soup-Bug-Fix.md`. Bugs 1 y 2 ya resueltos. Bug 3 (contradicción de diseño TP/SL vs modelo de entrada) quedó documentado sin resolver.

## Consulta a la metodología

Antes de tocar código se consultó el notebook CRT (`02763094-8e89-4408-a18e-d96fa67eef7d`) específicamente sobre el modelo de TP/SL correcto para una **entrada de continuación** (C3 confirma displacement fuera de C1 + pullback a Order Block M15).

Confirmado: para esta entrada, los objetivos se proyectan **en la dirección del displacement (extensión)**, nunca de vuelta al rango C1 — eso es lógica de reversión al 50%, que solo aplica a un Turtle Soup puro desde los extremos del rango, no a una entrada de continuación tras el escape.

Modelo correcto:
- **SL:** ligeramente por debajo (long) / por encima (short) del Order Block M15 real que disparó la entrada — no la mecha H4 de C2.
- **TP:** proyección de extensión de la mecha de manipulación C2 (desde el nivel barrido hasta su cierre), usando esa altura como unidad — múltiplos ~2.0x/2.5x como puntos de "agotamiento algorítmico" — o la liquidez HTF más cercana (high/low del día previo) si es más realista que la extensión matemática pura.

## Cambios aplicados

En `indicators/crt-ob-backtest.pine` y `indicators/crt-unified.pine` (bloques de display y de backtest engine, ambos):

- Añadida variable `c2_close` (cierre de la vela H4 de C2), capturada junto con `c2_wick_ext`.
- `crt-ob-backtest.pine`: añadidas `saved_ob_high`/`saved_ob_low` para persistir el Order Block M15 real en el momento del trigger (antes no se guardaba, solo se usaba inline para el engulfing check).
- SL: `saved_ob_low - 3*pip_size` (long) / `saved_ob_high + 3*pip_size` (short) — antes `c2_wick_ext ± 3*pip_size`.
- TP1: `c2_close + ext_leg*2.0` (long) / `c2_close - ext_leg*2.0` (short), donde `ext_leg = |c2_close - c2_wick_ext|`.
- TP2: liquidez HTF (`d_prev_high`/`d_prev_low`) si cae entre TP1 y la extensión 2.5x; si no, `c2_close ± ext_leg*2.5`.

## Resultado tras el fix (XAUUSD M15, ~3 meses, mismo dataset que la validación anterior)

| Métrica | Antes (bug 3) | Después |
|---|---|---|
| Trades | 7 | 7 |
| Win rate | 0% | 42.9% (3/7) |
| Dirección TP vs entrada | Contradictoria (TP por debajo en un long) | Correcta (TP1 5013.07 / TP2 5072.71, ambos > entrada 5012.24 en el último long) |
| Total pips | imposible (-13444 avg, -20007 min) | -30302 total, avg -4328.9 |

La contradicción estructural está resuelta — el sistema ahora opera con un modelo TP/SL coherente con su propio modelo de entrada. **Sigue siendo negativo en conjunto** con esta muestra de 7 trades: eso ya es una señal real de rendimiento, no un bug, y hace falta más volumen/optimización antes de sacar conclusiones de rentabilidad.

## Hallazgo adicional (sin resolver, no bloqueante)

El valor mostrado de `PIPSIZE` (0.01) no coincide con el pip estándar de XAUUSD (~$0.1) — `pip_size = syminfo.mintick * 10` puede estar mal calibrado para este símbolo, lo que infla las magnitudes en "pips" mostradas en el panel (miles en vez de decenas/cientos). No afecta la lógica de entrada/SL/TP en precio real (que sí es correcta), solo la lectura de las estadísticas. No corregido en esta sesión — pendiente confirmar antes de tocarlo.

## Estado real — honesto

Bug 3 resuelto: modelo TP/SL ahora es internamente coherente con el modelo de entrada de continuación. El sistema de detección (H4+H1+M15) y el de gestión (SL/TP) ya no se contradicen. Con todo, 7 trades es muestra insuficiente para validar rentabilidad — antes de comprometerse a usar el indicador para operar falta: (1) corregir/verificar la unidad de "pips", (2) correr sobre más historial (limitado a ~3 meses por techo de la API de datos), (3) revisar visualmente cada trade en el chart para confirmar que la lógica de SL/TP se comporta como se espera candle a candle.

## Validación cruzada — EURUSD M15 (mismo periodo, ~3 meses)

Decisión: dejar de usar XAUUSD como par de referencia para el backtesting — la lógica CRT opera sobre rangos relativos (universales), no sobre el activo concreto, y XAUUSD tenía el problema de calibración de `pip_size` que ensuciaba la lectura. EURUSD da magnitudes de pips normales y sirve de referencia limpia; si la estrategia funciona ahí, es transferible.

| Métrica | XAUUSD | EURUSD |
|---|---|---|
| Trades | 7 | 13 |
| Wins | 3 | 7 |
| Win rate | 42.9% | 53.8% |
| Avg pips | -4328.9 (escala rota) | -18 |
| Max pips | 4935.5 (escala rota) | +10.7 |
| Min pips | -12969.5 (escala rota) | -56 |
| Total pips | -30302 (escala rota) | -234.1 |
| Funnel C3#/H1#/OB# | 51/2/7 | 47/4/20 |

En EURUSD los pips tienen magnitud legible (confirma que el problema de escala era específico de XAUUSD, no un bug de la lógica de entrada/SL/TP arreglada arriba). Win rate >50% pero expectativa negativa: las pérdidas (-56 máx) pesan más que las ganancias (+10.7 máx) — desequilibrio de RR a revisar, no un bug estructural.

## Cambio de modelo — mitigación multi-TF sin gate de continuación (29 jul 2026, sesión 3)

13 trades en 3 meses se consideró insuficiente frente a la expectativa de setups casi diarios. A petición del usuario, se replanteó la rigidez de la estrategia: en vez de exigir C3 (confirmación de displacement/continuación) para operar, el modelo pasa a ser de **mitigación multi-timeframe pura**:

1. H4 mitigado (C2 formado: barre C1 y cierra dentro) — ya no hace falta esperar a C3.
2. H1 también mitigado en la misma dirección — versión simplificada: Turtle Soup H1 autocontenido (la vela H1 actual barre el extremo de la H1 anterior y cierra de vuelta dentro), sin anclarse a la vela de contacto exacta con C1 (eso era el cuello de botella: solo 4 H1# de 47 C3# en el modelo anterior).
3. Entrada en el siguiente Order Block M15 a favor de la dirección.
4. SL: mecha del H4 mitigado (C2) ± buffer — vuelve al modelo pre-fix, pero ahora sí es coherente porque el gate ya no exige continuación.
5. TP: RR fijo 1:1 (TP1) y 1:1.5 (TP2), capado por `dol_level` (extremo opuesto del rango H4, el nivel "por mitigar") si ese nivel cae más cerca que el 1.5R.

### Resultado — EURUSD M15, mismo periodo ~3 meses

| Métrica | Modelo continuación (anterior) | Modelo mitigación multi-TF |
|---|---|---|
| Trades | 13 | **293** |
| Win rate | 53.8% | **75.4%** |
| Avg pips | -18 | **+4.8** |
| Max pips | +10.7 | +63.7 |
| Min pips | -56 | -53.9 |
| Total pips | -234.1 | **+1397.85** |
| Funnel C3#/H1#/OB# | 47/4/20 | 47/92/423 |

Salto grande: de 13 a 293 trades (~3.2/día, coincide con la expectativa de setups casi diarios) y de negativo a positivo neto. El cuello de botella era efectivamente el gate H1 anclado a la vela de contacto exacta — al simplificarlo, el funnel se destapa completamente (H1# pasó de 4 a 92).

**Sin verificar todavía — no tomar como resultado final:**
- 75.4% de win rate es alto para este tipo de setup; falta revisión visual de una muestra de trades candle a candle para descartar que el gate H1 (ahora más laxo) esté disparando en momentos que en la práctica no serían operables.
- Sin comisión ni spread modelados — resultado en pips brutos, sin fricción de ejecución real.
- 3 meses sigue siendo el techo de datos de la API; sigue siendo poco para afirmar robustez.

## Próximo paso

Verificar visualmente una muestra de trades del modelo de mitigación multi-TF en el chart real (no solo el panel de stats), antes de dar por bueno el 75.4%. Si se sostiene, ampliar el periodo de datos y evaluar coste de comisión/spread. Seguir trabajando sobre EURUSD como referencia.
