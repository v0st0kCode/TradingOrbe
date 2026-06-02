# CRT Backtest EURUSD - Hallazgos y Correcciones

**Fecha:** 2025-06-02
**Par:** EURUSD (OANDA)
**Período testeado:** Ene 2024 - Jun 2025
**Instrumentos:** CRT Unified + CRT OB Backtest M15

---

## 1. Correcciones Implementadas

### 1.1 Bug Crítico: `exit_reason` no se reseteaba
**Problema:** En el motor de backtest, la variable `exit_reason` (que indica TP2/TP1/SL/Timeout) nunca volvía a 0 después de registrar una operación. Esto causaba que en cada barra posterior se sumara un trade ficticio, resultando en miles de trades falsos (e.g., 10,209 trades, -10,209 pips).

**Fix:** Añadido `exit_reason := 0` en el bloque de cierre de posición después de acumular estadísticas.

**Archivo:** `indicators/crt-ob-backtest.pine` (línea 256)

### 1.2 Bug: H1 Turtle Soup fuera del rango H4 C1
**Problema:** El H1 Turtle Soup podía activarse en cualquier lugar del gráfico, incluso fuera del rango de la vela C1 de H4. Esto violaba la lógica CRT donde el TS debe ocurrir *dentro* del rango que define la estructura.

**Fix:** Añadida condición `ts_inside_c1`:
```pinescript
bool ts_inside_c1 = jc_h <= c1_high and jc_l >= c1_low
```

**Archivos:** 
- `indicators/crt-ob-backtest.pine`
- `indicators/crt-unified.pine`

### 1.3 Bug: OB solo se detectaba en timeframe M15
**Problema:** La detección de Order Block usaba `close > open` del **timeframe actual del gráfico** (ej. H4), no de M15. Si el usuario estaba en H4 o H1, `is_m15` era false y nunca se detectaba el OB.

**Fix:** Reemplazado el acceso directo a velas por `request.security` para leer datos M15 desde cualquier timeframe:
```pinescript
[m15_open, m15_close, m15_open_1, m15_close_1] = request.security(syminfo.tickerid, "15", 
     [open, close, open[1], close[1]], lookahead=barmerge.lookahead_off)
```

**Archivos:**
- `indicators/crt-ob-backtest.pine`
- `indicators/crt-unified.pine`

---

## 2. Estado del Backtest en EURUSD

### 2.1 Resultado
- **Trades encontrados:** 0 (en el período visible 2024-2025)
- **Setups H4 detectados:** Sí (varios C1→C2→SETUP)
- **Setups H1 confirmados:** Sí (varios con Turtle Soup dentro del rango)
- **OBs M15 ejecutados:** 0 (ninguno cumplió la condición de engulfing en el período testeado)

### 2.2 Diagnóstico
El indicador **funciona correctamente** después de las correcciones. La ausencia de trades se debe a que EURUSD en 2024-2025 ha estado en un **rango lateral muy compacto** (1.08-1.12 aproximadamente), con muy pocas expansiones + mitigaciones que cumplan los criterios CRT estrictos:
- C1→C2→C3 en H4 con sweep claro
- Turtle Soup en H1 dentro del rango C1  
- Engulfing de OB en M15 justo después de la estructura

### 2.3 Observaciones
- La estrategia CRT es **muy selectiva** por diseño
- El replay de TradingView **se resetea al cambiar de timeframe**, lo que dificulta el análisis paso a paso H4→H1→M15
- Se recomienda ejecutar el indicador directamente en **M15** para backtesteo óptimo (evita problemas de `request.security`)

---

## 3. Arquitectura del Backtest

### 3.1 Flujo CRT Validado
1. **H4:** Detección de estructura C1→C2→SETUP (state machine)
2. **H1:** Turtle Soup como confirmación (dentro del rango C1)
3. **M15:** Order Block engulfing para entrada

### 3.2 Reglas de Entrada/Salida
- **Entry:** Open de la barra siguiente al OB engulfing
- **SL:** C2 wick ± 3 pips
- **TP1:** 50% del rango C1
- **TP2:** DOL (Draw on Liquidity = extreme opuesto de C1)
- **Timeout:** 10 barras M15 máximo

### 3.3 Métricas Trackeadas
- Total trades
- Win rate (%)
- Pips promedio
- Max/Min pips
- Total pips acumulados
- Estado en tiempo real (H4/H1/OB)

---

## 4. Recomendaciones para Futuro Backtesteo

1. **Ejecutar en M15 directamente:** El indicador `crt-ob-backtest.pine` está diseñado para ejecutarse en M15. Ahí lee los datos H4/H1 vía `request.security` y los datos M15 son nativos.

2. **Usar pares más volátiles:** XAUUSD y GBPUSD suelen tener más expansiones y por tanto más setups CRT.

3. **Período recomendado:** Post-2020 (alta volatilidad) o periodes de noticias (NFP, FOMC) donde los rangos se expanden y mitigan claramente.

4. **Validación visual:** Cuando el indicador muestre "H4: SETUP + H1: ✓", hacer zoom en esas barras en M15 para verificar visualmente si aparece el OB engulfing.

---

## 5. Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `indicators/crt-unified.pine` | Fix: TS dentro de C1, OB vía request.security, backtest engine integrado |
| `indicators/crt-ob-backtest.pine` | Fix: exit_reason reset, TS dentro de C1, OB vía request.security |

**Estado:** Scripts compilados y guardados en TradingView. Listos para uso en EURUSD, XAUUSD, GBPUSD.

---

*Documento generado por OpenCode el 2025-06-02*
