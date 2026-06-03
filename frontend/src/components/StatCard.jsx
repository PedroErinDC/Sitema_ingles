export default function StatCard({ label, value, hint, tone = "default" }) {
  const surfaceClass =
    tone === "accent"
      ? "border-green-200 bg-green-50"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50"
        : ""

  const valueClass =
    tone === "accent"
      ? "text-green-900"
      : tone === "warning"
        ? "text-amber-900"
        : "text-stone-900"

  return (
    <article className={`card p-6 ${surfaceClass}`}>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">{label}</p>
      <p className={`mt-4 text-5xl font-bold tabular-nums tracking-tight ${valueClass}`}>{value}</p>
      <p className="mt-2 text-xs leading-5 text-stone-400">{hint}</p>
    </article>
  )
}
