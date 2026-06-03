import { useState } from "react"

import { api } from "../lib/api"

const EXAMPLE_QUESTIONS = [
  "¿Qué sé sobre phrasal verbs? Dame ejemplos de mi material.",
  "Explícame el present perfect con ejemplos de mis videos.",
  "¿Qué diferencia hay entre 'make' y 'do' según mi material?",
  "¿Cuáles son los conectores de contraste que aparecen en mis transcripciones?",
  "Explícame el uso del subjuntivo en inglés con ejemplos concretos.",
]

export default function GraphView({ graph, content, selectedLlm, onNotify, onError }) {
  const [question, setQuestion] = useState("")
  const [hops, setHops] = useState(1)
  const [answer, setAnswer] = useState("")
  const [loading, setLoading] = useState(false)

  const hasGraph = (graph?.nodes ?? 0) > 0
  const hasContent = (content?.length ?? 0) > 0

  async function ask() {
    if (!question.trim()) return
    setLoading(true)
    setAnswer("")
    try {
      const response = await api("/graph/query", {
        method: "POST",
        body: { question, llm_model: selectedLlm, hops },
      })
      setAnswer(response.answer)
    } catch (error) {
      onError(error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header — double-bezel */}
      <div className="shell fade-up">
        <section className="panel px-8 py-8 md:px-10">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
            Explorar material
          </p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-stone-900">
            Pregúntale al LLM local
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-500">
            El LLM recorre el grafo construido a partir de tus transcripciones y responde
            usando{" "}
            <strong className="text-stone-700">tu propio material como contexto</strong>.
            Cuanto más material hayas indexado, más rica la respuesta.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {[
              { label: "Nodos en el grafo",       value: graph?.nodes   ?? 0, sub: "entidades indexadas" },
              { label: "Relaciones",               value: graph?.edges   ?? 0, sub: "conexiones entre entidades" },
              { label: "Material en biblioteca",   value: content?.length ?? 0, sub: "elementos disponibles" },
            ].map(({ label, value, sub }) => (
              <div key={label} className="rounded-xl border border-stone-100 bg-stone-50 p-4">
                <p className="text-xs text-stone-400">{label}</p>
                <p className="mt-2 text-3xl font-bold tabular-nums text-stone-900">{value}</p>
                <p className="mt-0.5 text-xs text-stone-400">{sub}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* No graph warning */}
      {!hasGraph && (
        <div className="banner-amber p-5 fade-up" style={{ animationDelay: "60ms" }}>
          <p className="text-sm font-semibold text-amber-900">
            {hasContent
              ? "El grafo está vacío — indexa tu material primero"
              : "Sin contenido — sube material primero"}
          </p>
          <p className="mt-2 text-sm leading-6 text-stone-500">
            {hasContent
              ? 'Ve a Material, selecciona uno o varios elementos en Biblioteca y haz clic en "Indexar selección". Puede tardar unos minutos.'
              : 'Ve a Material, sube un video o audio y guárdalo en biblioteca. Luego vuelve aquí para indexarlo.'}
          </p>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[0.48fr_1.52fr]">
        {/* Controls */}
        <aside className="space-y-4">
          {/* Depth */}
          <section className="card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Alcance de búsqueda
            </p>
            <p className="mt-2 text-sm leading-5 text-stone-500">
              Controla qué tan lejos busca el sistema en el grafo antes de responder.
            </p>
            <div className="mt-4">
              <input
                type="range"
                min="1"
                max="3"
                value={hops}
                onChange={(e) => setHops(Number(e.target.value))}
                className="w-full accent-blue-600"
              />
              <div className="mt-1.5 grid grid-cols-3 text-[10px] text-stone-400">
                <span>Preciso</span>
                <span className="text-center">Balanceado</span>
                <span className="text-right">Amplio</span>
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-stone-100 bg-stone-50 p-3">
              <p className="text-sm font-semibold text-stone-800">
                {hops === 1 && "Solo nodos más relevantes"}
                {hops === 2 && "Nodos relevantes + vecinos directos"}
                {hops === 3 && "Red extendida — más contexto, más lento"}
              </p>
              <p className="mt-1 text-xs text-stone-400">
                {hops === 1 && "Respuestas directas y rápidas. Recomendado para la mayoría de preguntas."}
                {hops === 2 && "Incluye conexiones secundarias. Bueno para preguntas sobre relaciones."}
                {hops === 3 && "Cubre todo el vecindario del grafo. Útil para preguntas amplias."}
              </p>
            </div>
          </section>

          {/* Examples */}
          <section className="card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Preguntas de ejemplo
            </p>
            <p className="mt-2 text-xs text-stone-400">Haz clic para usarla como punto de partida.</p>
            <div className="mt-4 space-y-2">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => { setQuestion(q); setAnswer("") }}
                  className="block w-full rounded-xl border border-stone-100 bg-stone-50 px-3 py-2.5 text-left text-xs text-stone-600 transition-all hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                >
                  {q}
                </button>
              ))}
            </div>
          </section>
        </aside>

        {/* Query + answer */}
        <article className="card p-7">
          <label className="block">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Tu pregunta
            </p>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask() }}
              rows={4}
              placeholder="Escribe tu pregunta aquí o elige un ejemplo..."
              className="field mt-3 w-full rounded-xl border px-5 py-4 text-sm leading-6 text-stone-800 outline-none placeholder:text-stone-300"
            />
          </label>

          <div className="mt-3 flex items-center justify-between gap-4">
            <p className="text-xs text-stone-400">Ctrl+Enter para consultar</p>
            <button
              onClick={ask}
              disabled={loading || !question.trim() || !hasGraph}
              className="btn btn-primary px-5 py-3 text-sm"
            >
              {loading ? "Consultando..." : "Consultar"}
            </button>
          </div>

          {/* Answer */}
          <div className="mt-6">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Respuesta del LLM
            </p>
            <div className="mt-3 min-h-[160px] rounded-xl border border-stone-100 bg-stone-50 p-6">
              {loading ? (
                <div className="flex items-center gap-3 text-sm text-stone-400">
                  <span className="block h-4 w-4 animate-spin rounded-full border-2 border-stone-200 border-t-blue-500" />
                  Recorriendo el grafo y generando respuesta...
                </div>
              ) : answer ? (
                <div className="whitespace-pre-wrap text-sm leading-7 text-stone-700">{answer}</div>
              ) : (
                <p className="text-sm text-stone-400">
                  {hasGraph
                    ? "La respuesta aparecerá aquí después de consultar."
                    : "Indexa material primero para poder hacer consultas."}
                </p>
              )}
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}
