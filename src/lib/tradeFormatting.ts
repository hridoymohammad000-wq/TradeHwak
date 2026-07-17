import { CanonicalTradingMode } from '../api/types';

export function modeLabel(mode: CanonicalTradingMode): 'Scalping' | 'Intraday' | 'Unknown' {
  if (mode === 'scalping') return 'Scalping';
  if (mode === 'intraday') return 'Intraday';
  return 'Unknown';
}

export function formatTimestamp(value: string | null): string {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function formatMoney(value: number | null, signed = false): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(value: number | null, maximumFractionDigits = 4): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return value.toLocaleString(undefined, { maximumFractionDigits });
}

export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return `${value.toFixed(2)}%`;
}

export function formatRiskReward(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return `1:${value.toFixed(2)}`;
}
