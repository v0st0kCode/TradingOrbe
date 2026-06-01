# Indicadores Pine Script

## Estructura de Archivos

```
indicators/
├── README.md           # Este archivo
├── crt-detector.pine   # Detector de patrones CRT
├── ob-fvg-zones.pine   # Order Blocks y FVGs automáticos
├── liquidity-map.pine  # Mapa de liquidez (BSL/SSL)
└── ema-system.pine     # Sistema de EMAs (9/21/50/200)
```

## Cómo Cargar en TradingView (via MCP)

```javascript
// 1. Leer el archivo Pine Script
const code = fs.readFileSync('indicators/crt-detector.pine', 'utf8');

// 2. Cargar en TradingView via MCP
await pine_set_source({ source: code });
await pine_smart_compile();

// 3. Verificar errores
const errors = await pine_get_errors();
```

## Convenciones

- Versión: `// @version=5` siempre en la primera línea
- Nombre descriptivo en `indicator("Nombre", overlay=true/false)`
- Colores: bullish = `color.new(color.teal, 0)`, bearish = `color.new(color.red, 0)`
- Inputs siempre con `input.int()` / `input.float()` / `input.bool()`
