export function formatQuarter(yearQuarter: string): string {
  return yearQuarter.replace("-", " ");
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW" }).format(value);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
