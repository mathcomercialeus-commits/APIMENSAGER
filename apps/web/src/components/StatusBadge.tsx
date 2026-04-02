import { formatStatus } from "@/src/lib/format";

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const normalized = (status || "unknown").toLowerCase().replace(/\s+/g, "_");
  return <span className={`status-pill status-pill--${normalized}`}>{formatStatus(status)}</span>;
}
