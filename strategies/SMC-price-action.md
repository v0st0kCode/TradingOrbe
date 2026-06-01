# SMC / Price Action — Referencia Rápida

## Order Blocks (OB)

**Bullish OB**: última vela bajista antes de un BOS alcista
**Bearish OB**: última vela alcista antes de un BOS bajista

Validación:
- OB debe causar desplazamiento (mínimo 3 velas de impulso)
- Mejor si hay FVG encima/debajo del OB
- Priorizar OBs que no han sido mitigados

## Fair Value Gaps (FVG)

**Bullish FVG**: H(vela-1) < L(vela+1) — hueco entre shadow
**Bearish FVG**: L(vela-1) > H(vela+1)

- 50% del FVG = entrada óptima
- FVG en zona premium/discount = mayor probabilidad
- FVG en OB = confluencia máxima

## Estructura de Mercado

**BOS** (Break of Structure): continuación de tendencia
**CHoCH** (Change of Character): primera señal de reversión

Regla: solo operar en dirección del último BOS en HTF

## Liquidez

**BSL** (Buy Side Liquidity): equal highs, previos swing highs
**SSL** (Sell Side Liquidity): equal lows, previos swing lows

Orden de operativa:
1. Precio se acerca a pool de liquidez HTF
2. Sweep de liquidez (wick o cierre breve fuera)
3. Rechazo → BOS en LTF → entrada

## Premium / Discount

- **Premium** (>50% del rango): buscar ventas
- **Discount** (<50% del rango): buscar compras
- OTE (Optimal Trade Entry): 0.618–0.705 Fibonacci del swing
