# CRT OB Backtest — 3 Bugs Reales Encontrados (28 jul 2026)

**Contexto:** Validación de valor real antes de comprometerse a usar TradingOrbe. El backtest anterior (2025-06-02) reportó 0 trades en EURUSD y lo atribuyó a "estrategia muy selectiva". Esa conclusión no estaba verificada — se auditó con datos reales.

## Validación inicial (post-fix H1, pre-fix stats)

| Par | Periodo M15 | Trades |
|---|---|---|
| EURUSD | Ene 2024–Jun 2025 (backtest previo) | 0 |
| XAUUSD | Abr–Jul 2026 (~3 meses, techo real de la API) | 0 → luego 7 tras fixes |
| GBPUSD | Abr–Jul 2026 (~5 días, datos limitados esa sesión) | 0 |

## Bug 1 — H1 Turtle Soup nunca confirmaba (RESUELTO)

Consultado el notebook de metodología CRT (`02763094-8e89-4408-a18e-d96fa67eef7d`) en vez de adivinar. Protocolo real: mientras se forma C2, localizar la vela H1 concreta que perfora C1 (nueva referencia LTF), y confirmar cuando una vela H1 posterior barre EL EXTREMO DE ESA VELA CONCRETA y cierra dentro.

El código usaba la vela H1 anterior genérica (`h1_prev_high/low`) + exigía quedar dentro del rango C1 completo (ya desactualizado en cuanto arranca C2) — combinación casi geométricamente imposible.

**Fix:** reescrita la detección de vela de contacto (`contact_found`, `ltf_c1_high/low`) en `crt-ob-backtest.pine` y `crt-unified.pine`. Confirmado con datos: 0 → 2 confirmaciones en 51 setups H4 completados (3 meses XAUUSD).

## Bug 2 — Stats nunca contaban los cierres (RESUELTO)

El bloque "cerrar posición" reseteaba `exit_reason := 0` **antes** de que el bloque de estadísticas lo leyera — mismo bar, orden de ejecución equivocado. Resultado: `total_trades` se quedaba en 0 aunque el motor sí abriera y cerrara posiciones (Order Block disparó 7 veces, trades mostraba 0).

**Fix:** reordenado — acumulación de stats ANTES del bloque de cierre. Confirmado: `total_trades` pasó de 0 a 7.

## Bug 3 — Contradicción de diseño TP/SL vs modelo de entrada (SIN RESOLVER)

Con los bugs 1 y 2 arreglados, los 7 trades cerrados dieron win rate 0% y magnitudes de pips imposibles (avg -13444, min -20007). Diagnóstico con datos reales del último trade:

- Entrada: 5012.24
- TP1: 4817.37 (punto medio del rango C1)
- TP2: 4875.25 (= high de C1)
- **La entrada está por encima de ambos take-profits.**

**Causa raíz:** el modelo de entrada (C3 confirma displacement fuera de C1 + pullback Order Block en M15) es una entrada de **continuación** — se compra después de que el precio ya rompió y se alejó de C1. Pero TP1/TP2 apuntan de vuelta hacia el rango C1 — eso es lógica de **reversión a la media**. Dos modelos de entrada distintos con objetivos contradictorios: para cuando se ejecuta la entrada de continuación, los "objetivos" de reversión ya quedaron atrás.

No es un typo — es una decisión de diseño de la estrategia sin resolver. Requiere definir el modelo de TP correcto para entradas de continuación (ej. extensión de Fibonacci desde C2, o un modelo de entrada de reversión distinto) contra el notebook de metodología.

## Instrumentación añadida

El indicador ahora expone en su panel de stats (además de trades/win%/pips):
- **C3 # / H1 # / OB #** — contador acumulado de cada fase del funnel en todo el histórico cargado (no solo el último bar)
- **ENTRY / SL / GAP** y **TP1/TP2 / PIPSIZE / DIR-EXIT** del último trade cerrado — para diagnóstico rápido sin tener que re-instrumentar cada vez

## Estado real — honesto

**No usar este indicador para operar todavía.** Los bugs 1 y 2 están arreglados y confirmados con datos. El bug 3 es estructural y necesita resolverse antes de que las cifras de rentabilidad signifiquen algo. El sistema de detección de setups (H4+H1+M15) funciona; el sistema de gestión de la operación (TP/SL) no está alineado con el modelo de entrada.

## Próximo paso

Resolver bug 3: definir el modelo de TP correcto para entrada de continuación, contra el notebook de metodología, y volver a correr el backtest.
