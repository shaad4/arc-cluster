import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
export function pct(value: number | null | undefined) { return value == null ? '—' : `${value.toFixed(1)}%` }
export function number(value: number | null | undefined) { return value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 1 }) }
export function bytes(value: number | null | undefined) { if (value == null) return '—'; if (value < 1024) return `${value.toFixed(0)} B`; const i = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4); return `${(value / 1024 ** i).toFixed(1)} ${['B', 'KiB', 'MiB', 'GiB', 'TiB'][i]}` }
export function time(value: number | null | undefined) { return value ? new Date(value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Not sampled' }
export function duration(value: number | null | undefined) { if (value == null) return '—'; const hours = Math.floor(value / 3600); return hours > 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : `${hours}h ${Math.floor(value % 3600 / 60)}m` }
