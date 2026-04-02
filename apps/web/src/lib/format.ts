export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(new Date(value));
}

export function formatCurrency(value: number | null | undefined): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(value || 0);
}

export function formatStatus(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  const total = Math.max(seconds, 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}min`;
  }
  if (minutes > 0) {
    return `${minutes}min ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

export function truncate(value: string | null | undefined, max = 80): string {
  if (!value) {
    return "-";
  }
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, max - 1)}...`;
}
