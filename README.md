# TradingOrbe

Sistema de análisis técnico con IA para operativa en Forex, XAU/USD e índices. Estrategia principal: **CRT (Candle Range Theory)** + **SMC/Price Action** + **Wyckoff**.

## Descripción

TradingOrbe es un entorno de análisis técnico diseñado para operar con alta probabilidad en mercados de alta liquidez. Combina la lectura de rangos de velas (CRT), la estructura de mercado (SMC) y la gestión de riesgo institucional.

## Instrumentos Principales

- **FX**: EURUSD, GBPUSD, USDJPY
- **Commodities**: XAUUSD
- **Sesiones**: Londres (08:00–12:00 CET), Nueva York (14:30–17:00 CET)
- **Timeframes**: D1 (bias) → H4/H1 (estructura) → M15/M5 (entrada)

## Estructura del Proyecto

```
TradingOrbe/
├── strategies/       # Documentación de estrategias (CRT, SMC, Wyckoff)
├── indicators/       # Indicadores custom en Pine Script
├── analysis/         # Análisis guardados por sesión
└── notebooks/        # Referencias e índice de NotebookLM
```

## Estrategia CRT (Candle Range Theory)

CRT analiza las velas como rangos de liquidez con 3 fases:
1. **Toma de liquidez** (wick — sweep del high o low previo)
2. **Desplazamiento** (cuerpo de la vela — expansión direccional)
3. **Cierre** (confirmación de dirección)

Ver [`strategies/CRT-methodology.md`](strategies/CRT-methodology.md) para detalles completos.

## Gestión de Riesgo

- Riesgo por operación: 0.5%–1% (challenge), 1%–2% (funded)
- R:R mínimo: 1:2
- Máximo 3 operaciones activas simultáneas

## Flujo de Trabajo

1. **Análisis gráfico** — lectura multi-timeframe con TradingView
2. **Consultar estrategia** — revisar documentación CRT/SMC
3. **Documentar setup** — guardar en `analysis/YYYY-MM-DD-SYMBOL.md`
4. **Crear indicador** — Pine Script en `indicators/`

## Licencia

Uso personal para análisis de trading.
