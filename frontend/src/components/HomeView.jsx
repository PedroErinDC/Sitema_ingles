import StatCard from "./StatCard"

function BrainCard({ label, title, desc, labelColor }) {
  return (
    <article className="card p-6">
      <p className={`text-[10px] font-semibold uppercase tracking-widest ${labelColor}`}>{label}</p>
      <h3 className="mt-2 text-base font-semibold text-stone-900">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-stone-500">{desc}</p>
    </article>
  )
}

function NextAction({ summary, content, onNavigate }) {
  const contentCount = content?.length ?? 0
  const wordsPending =
    (summary?.word_counts?.nueva ?? 0) +
    (summary?.word_counts?.aprendiendo ?? 0) +
    (summary?.word_counts?.mas_o_menos ?? 0)
  const graphNodes = summary?.graph?.nodes ?? 0

  if (contentCount === 0) {
    return (
      <div className="banner-amber p-5">
        <p className="text-sm font-semibold text-amber-900">Paso 1 — Agrega tu primer video o audio</p>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Ve a <strong>Material</strong>, sube un archivo local o pega una URL de YouTube.
          El sistema lo transcribirá con IA local y lo guardará en biblioteca.
        </p>
        <button onClick={() => onNavigate("content")} className="btn btn-amber mt-4 px-4 py-2 text-sm">
          Ir a Material →
        </button>
      </div>
    )
  }

  if (wordsPending === 0) {
    return (
      <div className="banner-amber p-5">
        <p className="text-sm font-semibold text-amber-900">
          Paso 2 — Importa vocabulario de tu biblioteca
        </p>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Tienes {contentCount} elemento{contentCount !== 1 ? "s" : ""} en biblioteca. En{" "}
          <strong>Material</strong>, selecciona uno y haz clic en <strong>Procesar</strong> para
          extraer palabras y gramática con el LLM local.
        </p>
        <button onClick={() => onNavigate("content")} className="btn btn-amber mt-4 px-4 py-2 text-sm">
          Ir a Material →
        </button>
      </div>
    )
  }

  return (
    <div className="banner-green p-5">
      <p className="text-sm font-semibold text-green-900">
        {wordsPending} palabras activas — hora de repasar
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-500">
        El motor adaptativo eligió las palabras pendientes para hoy.
        Lo que ya dominas no aparece; lo que fallas vuelve en la misma sesión.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button onClick={() => onNavigate("practicar")} className="btn btn-green px-4 py-2 text-sm">
          Ir a Practicar →
        </button>
        {graphNodes === 0 && (
          <button onClick={() => onNavigate("content")} className="btn btn-ghost px-4 py-2 text-sm">
            Indexar material para consultas →
          </button>
        )}
      </div>
    </div>
  )
}

const FLOW_STEPS = [
  {
    n: "01",
    label: "Agrega material",
    detail: "Sube videos, audios o descarga de YouTube. También PDFs y texto plano.",
    tab: "content",
    action: "Ir a Material",
  },
  {
    n: "02",
    label: "Transcribe y valida",
    detail: "El ASR local genera la transcripción. Corrígela segmento a segmento si hace falta.",
    tab: null,
    action: null,
  },
  {
    n: "03",
    label: "Procesa e importa",
    detail: "El LLM extrae vocabulario y reglas gramaticales del texto automáticamente.",
    tab: null,
    action: null,
  },
  {
    n: "04",
    label: "Estudia cada día",
    detail: "Tarjetas adaptativas y quizzes de gramática priorizan tus puntos débiles.",
    tab: "practicar",
    action: "Ir a Practicar",
  },
]

const GLOSSARY = [
  { term: "ASR", def: "Reconocimiento automático de voz — Parakeet o Whisper convierte audio a texto." },
  { term: "LLM", def: "Modelo de lenguaje local — Qwen, Mistral. Traduce, extrae gramática y responde." },
  { term: "SM-2", def: "Algoritmo de repetición espaciada — decide cuándo volver a mostrarte cada palabra." },
  { term: "Grafo de conocimiento", def: "Red de entidades extraídas de tus transcripciones. El LLM la recorre para responder." },
  { term: "Procesar", def: "Extraer vocabulario y puntos de gramática de un contenido guardado en biblioteca." },
  { term: "Indexar", def: "Añadir un contenido al grafo para poder consultarlo después con el LLM." },
]

export default function HomeView({ summary, content, onNavigate }) {
  const wc = summary?.word_counts ?? {}
  const graphStats = summary?.graph ?? {}
  const rank = summary?.rank ?? {}

  return (
    <div className="space-y-8">
      {/* Hero — double-bezel */}
      <div className="shell fade-up">
        <section className="panel px-8 py-9 md:px-10 md:py-11">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
            Tu sistema de aprendizaje
          </p>
          <h2 className="mt-3 text-4xl font-bold tracking-tight text-stone-900 md:text-5xl">
            Inglés local —<br className="hidden md:block" /> aprende de tu propio material
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-500">
            Sube videos y audios en inglés, transcríbelos con IA local y el sistema analiza qué
            sabes y qué no. Estudia con tarjetas adaptativas que priorizan tus puntos débiles y
            dejan de mostrarte lo que ya dominas.{" "}
            <strong className="text-stone-700">Sin nube, sin suscripciones, 100% en tu máquina.</strong>
          </p>
        </section>
      </div>

      {/* Next action */}
      <section className="fade-up" style={{ animationDelay: "60ms" }}>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
          ¿Qué hacer ahora?
        </p>
        <NextAction summary={summary} content={content} onNavigate={onNavigate} />
      </section>

      {/* Quick stats */}
      {summary && (
        <section>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
            Tu progreso de un vistazo
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 stagger">
            <StatCard
              label="En repaso activo"
              value={(wc.nueva ?? 0) + (wc.aprendiendo ?? 0) + (wc.mas_o_menos ?? 0)}
              hint="Palabras que aún no dominas"
            />
            <StatCard
              label="Palabras dominadas"
              value={wc.dominada ?? 0}
              hint="Ya salieron del repaso diario"
              tone="accent"
            />
            <StatCard
              label="Nodos en el grafo"
              value={graphStats.nodes ?? 0}
              hint="Entidades indexadas para consultas al LLM"
            />
            <StatCard
              label="Rango gramatical"
              value={rank.rank ?? "—"}
              hint={rank.best_level ? `Nivel estimado: ${rank.best_level}` : "Haz quizzes para obtener rango"}
              tone="warning"
            />
          </div>
        </section>
      )}

      {/* 3 system components */}
      <section>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
          Los 3 componentes del sistema
        </p>
        <div className="grid gap-4 lg:grid-cols-3 stagger">
          <BrainCard
            label="Componente 1 — Motor adaptativo"
            title="Aprende de ti, no tú de él"
            labelColor="text-blue-600"
            desc="Recuerda qué palabras y reglas fallas y cuáles dominas. SM-2 espacia los repasos: lo dominado desaparece semanas, lo que fallas vuelve hoy mismo."
          />
          <BrainCard
            label="Componente 2 — Grafo de conocimiento"
            title="Tu material, listo para preguntas"
            labelColor="text-amber-700"
            desc="El LLM extrae entidades y relaciones de tus transcripciones. Puedes preguntar: «Explícame el present perfect con ejemplos de mis videos»."
          />
          <BrainCard
            label="Componente 3 — Biblioteca y flujo"
            title="Todo en un solo lugar"
            labelColor="text-green-700"
            desc="Sube, transcribe, valida y aprueba. Solo lo que validas entra a biblioteca. Solo lo de biblioteca alimenta el estudio."
          />
        </div>
      </section>

      {/* Workflow steps */}
      <section>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
          El flujo completo
        </p>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 stagger">
          {FLOW_STEPS.map((step) => (
            <article key={step.n} className="card p-6">
              <span className="block text-4xl font-black text-stone-100">{step.n}</span>
              <h4 className="mt-3 text-base font-semibold text-stone-900">{step.label}</h4>
              <p className="mt-2 text-sm leading-6 text-stone-500">{step.detail}</p>
              {step.action && (
                <button
                  onClick={() => onNavigate(step.tab)}
                  className="btn btn-ghost mt-4 px-4 py-2 text-xs"
                >
                  {step.action} →
                </button>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* Glossary */}
      <section className="card p-6">
        <h3 className="text-sm font-semibold text-stone-900">Glosario rápido</h3>
        <p className="mt-1 text-xs text-stone-400">Términos que verás en la aplicación</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {GLOSSARY.map(({ term, def }) => (
            <div key={term} className="rounded-xl border border-stone-100 bg-stone-50 p-4">
              <p className="text-sm font-semibold text-stone-900">{term}</p>
              <p className="mt-1 text-xs leading-5 text-stone-500">{def}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
