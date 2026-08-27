export type TemperatureUnit = "F" | "C";

export const TEMPERATURE_LIMITS: Record<
  TemperatureUnit,
  { min: number; max: number; defaultValue: string }
> = {
  F: { min: 95, max: 110, defaultValue: "98.6" },
  C: { min: 35, max: 43.3, defaultValue: "37.0" },
};

function roundToOneDecimal(value: number): number {
  return Math.round((value + Number.EPSILON) * 10) / 10;
}

export function celsiusToFahrenheit(value: number): number {
  return roundToOneDecimal((value * 9) / 5 + 32);
}

export function fahrenheitToCelsius(value: number): number {
  return roundToOneDecimal(((value - 32) * 5) / 9);
}

export function toFahrenheit(value: number, unit: TemperatureUnit): number {
  return unit === "C" ? celsiusToFahrenheit(value) : roundToOneDecimal(value);
}

export function convertTemperatureInput(
  rawValue: string,
  from: TemperatureUnit,
  to: TemperatureUnit,
): string {
  if (from === to) return rawValue;
  const value = Number.parseFloat(rawValue);
  if (!Number.isFinite(value)) return TEMPERATURE_LIMITS[to].defaultValue;
  const converted = from === "C" ? celsiusToFahrenheit(value) : fahrenheitToCelsius(value);
  return converted.toFixed(1);
}

export function isTemperatureInRange(value: number, unit: TemperatureUnit): boolean {
  const { min, max } = TEMPERATURE_LIMITS[unit];
  return Number.isFinite(value) && value >= min && value <= max;
}
