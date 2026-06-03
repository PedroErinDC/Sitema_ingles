import StatCard from "./StatCard"

function WeakTopicRow({ item }) {
  const ratio = item.intentos ? Math.round((item.fallos / item.intentos) * 100) : 0
  const isHigh = ratio >= 60

  return (
    <article className="rounded-xl border border-stone-100 bg-stone-50 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-stone-900">{item.tema}</p>
          <p className="mt-0.5 text-xs text-stone-400">
            {item.fallos} fallo{item.fallos !== 1 ? "s" : ""} en {item.intentos} intento{item.intentos !== 1 ? "s" : ""}
          </p>
        </div>
        <span className={`flex-shrink-0 rounded-lg border px-3 py-1 text-sm font-bold tabular-nums ${
          isHigh
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-amber-200 bg-amber-50 text-amber-800"
        }`}>
          {ratio}%
        </span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-stone-200">
        <div
          className={`h-full rounded-full transition-all ${isHigh ? "bg-red-400" : "bg-amber-400"}`}
          style={{ width: `${ratio}%` }}
        />
      </div>
    </article>
  )
}

function WeakTopicSection({ title, subtitle, items, emptyMessage }) {
  return (
    <section className="card p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-stone-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-stone-400">{subtitle}</p>}
        </div>
        <span className="rounded-lg border border-stone-100 bg-stone-50 px-2.5 py-1 text-xs font-semibold text-stone-500">
          {items.length} tema{items.length !== 1 ? "s" : ""}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="mt-5 text-sm leading-6 text-stone-400">{emptyMessage}</p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <WeakTopicRow key={`${title}-${item.tema}`} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

function NextStepsBanner({ summary, onNavigate }) {
  const wordsPending =
    (summary.word_counts?.nueva ?? 0) +
    (summary.word_counts?.aprendiendo ?? 0) +
    (summary.word_counts?.mas_o_menos ?? 0)
  const dominated = summary.word_counts?.dominada ?? 0
  const graphNodes = summary.graph?.nodes ?? 0
  const weakTopics = summary.weak_topics ?? []

  if (wordsPending === 0 && dominated === 0) {
    return (
      <div className="banner-amber p-5">
        <p className="text-sm font-semibold text-amber-900">Sin vocabulario importado aún</p>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Ve a <strong>Material</strong>, selecciona un contenido y haz clic en <strong>Procesar</strong>.
        </p>
        <button onClick={() => onNavigate("content")} className="btn btn-amber mt-4 px-4 py-2 text-sm">
          Ir a Material →
        </button>
      </div>
    )
  }

  if (weakTopics.length > 0 && graphNodes > 0) {
    return (
      <div className="banner-blue p-5">
        <p className="text-sm font-semibold text-blue-900">
          Temas débiles detectados — refuérzalos con el LLM
        </p>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Tu tema más débil es <strong>{weakTopics[0].tema}</strong>. Ve a{" "}
          <strong>Explorar</strong> y pide una explicación con ejemplos de tu material.
        </p>
        <button onClick={() => onNavigate("graph")} className="btn btn-accent mt-4 px-4 py-2 text-sm">
          Consultar material →
        </button>
      </div>
    )
  }

  if (graphNodes === 0 && wordsPending > 0) {
    return (
      <div className="banner-amber p-5">
        <p className="text-sm font-semibold text-amber-900">El grafo de conocimiento está vacío</p>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Tienes {wordsPending} palabras en repaso. Ve a <strong>Material</strong> e indexa tu contenido.
        </p>
        <button onClick={() => onNavigate("content")} className="btn btn-amber mt-4 px-4 py-2 text-sm">
          Ir a Material →
        </button>
      </div>
    )
  }

  return (
    <div className="banner-green p-5">
      <p className="text-sm font-semibold text-green-900">Sistema funcionando correctamente</p>
      <p className="mt-2 text-sm leading-6 text-stone-500">
        {dominated} palabra{dominated !== 1 ? "s" : ""} dominada{dominated !== 1 ? "s" : ""} y{" "}
        {wordsPending} en repaso activo. Sigue estudiando cada día para avanzar.
      </p>
    </div>
  )
}

export default function DashboardView({ summary, onNavigate }) {
  if (!summary) {
    return (
      <div className="card p-10 text-center text-sm text-stone-400">
        Cargando datos del sistema...
      </div>
    )
  }

  const wc = summary.word_counts ?? {}
  const gc = summary.grammar_counts ?? {}
  const rank = summary.rank ?? {}

  return (
    <div className="space-y-7">
      {/* System state */}
      <section className="fade-up">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
          Estado del sistema
        </p>
        <NextStepsBanner summary={summary} onNavigate={onNavigate} />
      </section>

      {/* Vocabulary stats — bento row */}
      <section>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
          Vocabulario
        </p>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 stagger">
          <StatCard
            label="Nuevas"
            value={wc.nueva ?? 0}
            hint="Palabras que aún no has visto en sesión de repaso"
          />
          <StatCard
            label="Aprendiendo"
            value={wc.aprendiendo ?? 0}
            hint="Intervalo menor a 7 días — aún frágiles"
          />
          <StatCard
            label="Casi dominadas"
            value={wc.mas_o_menos ?? 0}
            hint="Intervalo entre 7 y 30 días — consolidándose"
          />
          <StatCard
            label="Dominadas"
            value={wc.dominada ?? 0}
            hint="Intervalo 30+ días — salen del repaso diario"
            tone="accent"
          />
        </div>
      </section>

      {/* Grammar + rank — asymmetric bento */}
      <section className="grid gap-5 xl:grid-cols-2">
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
            Gramática
          </p>
          <div className="grid gap-4 sm:grid-cols-2 stagger">
            <StatCard
              label="Reglas en repaso"
              value={(gc.nueva ?? 0) + (gc.aprendiendo ?? 0) + (gc.mas_o_menos ?? 0)}
              hint="Puntos de gramática en repaso activo"
            />
            <StatCard
              label="Reglas dominadas"
              value={gc.dominada ?? 0}
              hint="Reglas gramaticales consolidadas"
              tone="accent"
            />
          </div>
        </div>

        <section className="card p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                Rango gramatical
              </p>
              <h3 className="mt-1 text-lg font-semibold text-stone-900">
                Basado en reglas dominadas por nivel
              </h3>
            </div>
            <div className="text-right">
              <p className="text-4xl font-bold tabular-nums text-stone-900">{rank.rank ?? "—"}</p>
              {rank.best_level && (
                <p className="text-xs text-stone-400">Nivel: {rank.best_level}</p>
              )}
            </div>
          </div>

          {rank.by_level && Object.keys(rank.by_level).length > 0 ? (
            <div className="mt-5 space-y-3">
              {Object.entries(rank.by_level).map(([level, stats]) => {
                const pct = Math.round(((stats.mastered || 0) / (stats.total || 1)) * 100)
                return (
                  <div key={level}>
                    <div className="mb-1.5 flex items-center justify-between text-xs text-stone-400">
                      <span>{level}</span>
                      <span>{stats.mastered}/{stats.total} dominadas</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-stone-100">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="mt-4 text-sm text-stone-400">
              Haz quizzes de gramática para calcular tu rango.
            </p>
          )}
        </section>
      </section>

      {/* Weak topics — side-by-side */}
      <section className="grid gap-5 xl:grid-cols-2">
        <WeakTopicSection
          title="Temas débiles — Vocabulario"
          subtitle="Temas donde más palabras fallas, ordenados por tasa de error"
          items={summary.weak_topics ?? []}
          emptyMessage="No hay suficiente historial para detectar patrones. Estudia al menos 10 palabras y vuelve."
        />
        <WeakTopicSection
          title="Temas débiles — Gramática"
          subtitle="Reglas con mayor tasa de respuestas incorrectas"
          items={summary.weak_grammar_topics ?? []}
          emptyMessage="Completa al menos un quiz de gramática para ver qué reglas necesitas reforzar."
        />
      </section>
    </div>
  )
}
