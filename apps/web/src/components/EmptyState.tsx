export function EmptyState({
  title,
  description,
  tall = false
}: {
  title: string;
  description: string;
  tall?: boolean;
}) {
  return (
    <div className={tall ? "empty-state empty-state--tall" : "empty-state"}>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}
