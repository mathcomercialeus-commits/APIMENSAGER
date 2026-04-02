export function JsonBox({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="json-box">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
