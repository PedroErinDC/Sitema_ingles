import { useState } from "react"

import { api } from "../lib/api"

/* ─── Vocabulary (SM-2 flashcards) ───────────────────────────────────────── */

const RATINGS = [
  {
    value: 1,
    label: "Fallé",
    desc: "Vuelve ahora mismo en esta sesión. Intervalo reiniciado a 1 día.",
    cls: "btn-red",
  },
  {
    value: 2,
    label: "Difícil",
    desc: "Vuelve pronto. El intervalo crece poco.",
    cls: "btn-amber",
  },
  {
    value: 3,
    label: "Bien",
    desc: "Buen avance. El intervalo se alarga normalmente.",
    cls: "btn-green",
  },
  {
    value: 4,
    label: "Fácil",
    desc: "Intervalo largo — esta palabra tardará semanas en volver.",
    cls: "btn-accent",
  },
]

const STATUS_META = {
  nueva:      { label: "Nueva",          color: "bg-stone-400" },
  aprendiendo: { label: "Aprendiendo",   color: "bg-amber-500" },
  mas_o_menos: { label: "Casi dominada", color: "bg-green-500" },
  dominada:   { label: "Dominada",       color: "bg-blue-600"  },
}

function VocabPanel({ onRefresh, onNotify, onError }) {
  const [queue, setQueue] = useState([])
  const [revealed, setRevealed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [hoveredRating, setHoveredRating] = useState(null)

  const current = queue[0]
  const statusMeta = STATUS_META[current?.status] ?? { label: current?.status ?? "", color: "bg-stone-400" }

  async function loadQueue() {
    setLoading(true)
    try {
      const items = await api("/study/queue?limit=20")
      setQueue(items)
      setRevealed(false)
      onNotify(
        items.length === 0
          ? "No hay nada pendiente para hoy — buen trabajo"
          : `Sesión lista: ${items.length} palabras`
      )
    } catch (error) {
      onError(error.message)
    } finally {
      setLoading(false)
    }
  }

  async function rate(rating) {
    if (!current) return
    setSubmitting(true)
    try {
      await api("/study/review", { method: "POST", body: { word_id: current.id, rating } })
      setQueue((prev) => {
        const [head, ...rest] = prev
        return rating === 1 ? [...rest, head] : rest
      })
      setRevealed(false)
      onRefresh()
    } catch (error) {
      onError(error.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Action bar */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Vocabulario</p>
          <h2 className="mt-0.5 text-2xl font-bold text-stone-900">Repaso adaptativo</h2>
          <p className="mt-1 max-w-lg text-sm leading-6 text-stone-500">
            El sistema decide qué palabras mostrarte hoy. Lo que dominas no aparece.
            Lo que fallas vuelve dentro de la misma sesión.
          </p>
        </div>
        <button
          onClick={loadQueue}
          disabled={loading}
          className="btn btn-primary flex-shrink-0 px-5 py-2.5 text-sm"
        >
          {loading ? "Cargando..." : queue.length > 0 ? `${queue.length} pendientes` : "Empezar sesión"}
        </button>
      </div>

      {/* Empty state */}
      {!current && (
        <div className="card p-12 text-center">
          <p className="text-5xl font-black text-stone-100">?</p>
          <p className="mt-4 text-base font-semibold text-stone-700">
            {loading ? "Cargando palabras..." : "Sin palabras pendientes"}
          </p>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            {loading
              ? ""
              : 'Haz clic en "Empezar sesión" para cargar las palabras de hoy, o ve a Material para importar vocabulario.'}
          </p>
        </div>
      )}

      {/* Flashcard */}
      {current && (
        <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
          {/* Word — double-bezel */}
          <div className="shell">
            <article className="panel px-8 py-8">
              {/* Meta */}
              <div className="flex items-center justify-between gap-4">
                <p className="text-xs text-stone-400">
                  {queue.length} pendiente{queue.length !== 1 ? "s" : ""} ·{" "}
                  {current.topic || current.pos || "vocabulario general"}
                </p>
                <span className="inline-flex items-center gap-1.5 text-xs text-stone-400">
                  <span className={`block h-2 w-2 rounded-full ${statusMeta.color}`} />
                  {statusMeta.label}
                </span>
              </div>

              {/* Word */}
              <h3 className="mt-6 text-6xl font-bold tracking-tight text-stone-900">
                {current.word || current.lemma}
              </h3>
              {current.word !== current.lemma && (
                <p className="mt-2 text-sm text-stone-400">Forma base: {current.lemma}</p>
              )}

              {!revealed ? (
                <div className="mt-8">
                  <button
                    onClick={() => setRevealed(true)}
                    className="btn btn-primary px-5 py-3 text-sm"
                  >
                    Mostrar significado
                  </button>
                  <p className="mt-3 text-xs text-stone-400">
                    Intenta recordar la traducción antes de revelar.
                  </p>
                </div>
              ) : (
                <div className="mt-8 space-y-4">
                  <div className="banner-green p-5">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-green-700">
                      Traducción
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-green-900">
                      {current.translation || "Sin traducción guardada"}
                    </p>
                  </div>
                  {current.example_en && (
                    <div className="rounded-xl border border-stone-100 bg-stone-50 p-5">
                      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                        Ejemplo
                      </p>
                      <p className="mt-2 text-base italic text-stone-700">{current.example_en}</p>
                      {current.example_es && (
                        <p className="mt-2 text-sm text-stone-400">{current.example_es}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </article>
          </div>

          {/* Rating + stats */}
          <div className="space-y-4">
            <article className="card p-6">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                ¿Qué tan bien lo sabías?
              </p>
              <p className="mt-1 text-xs text-stone-400">Tu respuesta ajusta el próximo repaso.</p>
              <div className="mt-4 space-y-2">
                {RATINGS.map((r) => (
                  <div key={r.value}>
                    <button
                      onClick={() => rate(r.value)}
                      onMouseEnter={() => setHoveredRating(r.value)}
                      onMouseLeave={() => setHoveredRating(null)}
                      disabled={!revealed || submitting}
                      className={`btn ${r.cls} w-full justify-start px-4 py-3 text-sm`}
                    >
                      {r.label}
                    </button>
                    {hoveredRating === r.value && (
                      <p className="mt-1 px-1 text-xs text-stone-400">{r.desc}</p>
                    )}
                  </div>
                ))}
              </div>
              {!revealed && (
                <p className="mt-4 text-xs text-stone-400">Revela el significado primero.</p>
              )}
            </article>

            <article className="card p-6">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                Esta palabra
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {[
                  { label: "Veces fallada", value: current.lapses },
                  { label: "Repasos totales", value: current.reps },
                  {
                    label: "Próximo repaso",
                    value: current.interval === 0 ? "Hoy" : `${current.interval}d`,
                  },
                  { label: "Estado", value: statusMeta.label },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-xl border border-stone-100 bg-stone-50 p-3">
                    <p className="text-xs text-stone-400">{label}</p>
                    <p className="mt-1 text-lg font-bold tabular-nums text-stone-800">{value}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs leading-5 text-stone-400">
                El intervalo crece con cada acierto y se reinicia con cada fallo. A los 30+ días la
                palabra pasa a <em>dominada</em>.
              </p>
            </article>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Grammar quiz ───────────────────────────────────────────────────────── */

function GrammarPanel({ onRefresh, onNotify, onError }) {
  const [quiz, setQuiz] = useState([])
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState("")
  const [feedback, setFeedback] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const current = quiz[index]
  const isDone = quiz.length > 0 && index >= quiz.length

  async function loadQuiz() {
    setLoading(true)
    setFeedback(null)
    try {
      const items = await api("/grammar/quiz?limit=5")
      setQuiz(items)
      setIndex(0)
      setAnswer("")
      onNotify(
        items.length === 0
          ? "No hay gramática pendiente — importa contenido primero"
          : `Quiz listo: ${items.length} preguntas`
      )
    } catch (error) {
      onError(error.message)
    } finally {
      setLoading(false)
    }
  }

  async function submit() {
    if (!current || !answer) return
    setSubmitting(true)
    const correct = current.options[current.answer_index] === answer
    try {
      await api("/grammar/review", {
        method: "POST",
        body: { item_id: current.id, rating: correct ? 4 : 1, correct },
      })
      setFeedback({ correct, title: current.title, description: current.description })
      setIndex((v) => v + 1)
      setAnswer("")
      onRefresh()
    } catch (error) {
      onError(error.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Action bar */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Gramática</p>
          <h2 className="mt-0.5 text-2xl font-bold text-stone-900">Quiz de reconocimiento</h2>
          <p className="mt-1 max-w-lg text-sm leading-6 text-stone-500">
            Identifica qué regla explica cada ejemplo. Los aciertos alargan el intervalo;
            los errores lo reinician.
          </p>
        </div>
        <button
          onClick={loadQuiz}
          disabled={loading}
          className="btn btn-primary flex-shrink-0 px-5 py-2.5 text-sm"
        >
          {loading ? "Cargando..." : quiz.length === 0 ? "Generar quiz" : "Nuevo quiz"}
        </button>
      </div>

      {/* Empty state */}
      {quiz.length === 0 && (
        <div className="card p-12 text-center">
          <p className="text-5xl font-black text-stone-100">?</p>
          <p className="mt-4 text-base font-semibold text-stone-700">Sin quiz activo</p>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            Haz clic en Generar quiz. Si no aparece nada, ve a Material → Procesar con gramática activada.
          </p>
        </div>
      )}

      {/* Completed */}
      {isDone && (
        <div className="banner-green p-8 text-center">
          <p className="text-2xl font-bold text-green-900">Quiz completado</p>
          <p className="mt-2 text-sm text-stone-500">
            Tus respuestas actualizaron el historial de repaso.
          </p>
          <button onClick={loadQuiz} className="btn btn-green mt-5 px-5 py-2.5 text-sm">
            Nuevo quiz
          </button>
        </div>
      )}

      {/* Question */}
      {current && !isDone && (
        <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          {/* Question — double-bezel */}
          <div className="shell">
            <article className="panel px-7 py-7">
              {/* Progress */}
              <div className="mb-6">
                <div className="mb-2 flex items-center justify-between text-xs text-stone-400">
                  <span>Pregunta {index + 1} de {quiz.length} · Nivel: {current.level}</span>
                  <span>{Math.round((index / quiz.length) * 100)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-stone-100">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all"
                    style={{ width: `${(index / quiz.length) * 100}%` }}
                  />
                </div>
              </div>

              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                ¿Qué regla gramatical explica este ejemplo?
              </p>
              <blockquote className="mt-4 rounded-xl border border-stone-100 bg-stone-50 p-5 text-lg font-medium leading-7 text-stone-800">
                {current.prompt}
              </blockquote>

              <div className="mt-5 space-y-2">
                {current.options.map((option) => (
                  <label
                    key={option}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-all ${
                      answer === option
                        ? "border-blue-200 bg-blue-50"
                        : "border-stone-200 bg-white hover:border-stone-300 hover:bg-stone-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="grammar-option"
                      value={option}
                      checked={answer === option}
                      onChange={(e) => setAnswer(e.target.value)}
                      className="mt-0.5 accent-blue-600"
                    />
                    <span className="text-sm text-stone-700">{option}</span>
                  </label>
                ))}
              </div>

              <button
                onClick={submit}
                disabled={!answer || submitting}
                className="btn btn-primary mt-5 px-5 py-3 text-sm"
              >
                {submitting ? "Registrando..." : "Enviar respuesta"}
              </button>
            </article>
          </div>

          {/* Feedback */}
          <article className="card p-6">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Resultado
            </p>

            {!feedback ? (
              <div className="mt-5 rounded-xl border border-dashed border-stone-200 p-8 text-center">
                <p className="text-sm text-stone-400">
                  Responde la pregunta para ver si acertaste.
                </p>
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                <div className={feedback.correct ? "banner-green p-5" : "banner-red p-5"}>
                  <p className={`text-sm font-semibold ${feedback.correct ? "text-green-900" : "text-red-900"}`}>
                    {feedback.correct ? "Correcto" : "Incorrecto"}
                  </p>
                  {!feedback.correct && (
                    <p className="mt-0.5 text-xs text-red-700">La respuesta correcta era:</p>
                  )}
                  <p className="mt-1 text-base font-semibold text-stone-900">{feedback.title}</p>
                </div>
                {feedback.description && (
                  <div className="rounded-xl border border-stone-100 bg-stone-50 p-5">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                      Explicación
                    </p>
                    <p className="mt-3 text-sm leading-6 text-stone-600">{feedback.description}</p>
                  </div>
                )}
              </div>
            )}

            <div className="mt-8 border-t border-stone-100 pt-6">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                ¿Cómo funciona?
              </p>
              <div className="mt-4 space-y-3 text-sm text-stone-400">
                <p>Acierto → el intervalo se alarga. Esta regla tardará más en aparecer.</p>
                <p>Error → el intervalo se reinicia. La regla vuelve pronto para reforzarla.</p>
                <p>Las preguntas vienen de tu propio material transcrito e importado.</p>
              </div>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}

/* ─── Main PracticarView ─────────────────────────────────────────────────── */

export default function PracticarView({ onRefresh, onNotify, onError }) {
  const [mode, setMode] = useState("vocab")

  return (
    <div className="space-y-6">
      {/* Mode toggle */}
      <div className="tab-island">
        <button
          onClick={() => setMode("vocab")}
          className={`tab-btn${mode === "vocab" ? " tab-active" : ""}`}
        >
          Vocabulario
        </button>
        <button
          onClick={() => setMode("grammar")}
          className={`tab-btn${mode === "grammar" ? " tab-active" : ""}`}
        >
          Gramática
        </button>
      </div>

      {mode === "vocab" ? (
        <VocabPanel onRefresh={onRefresh} onNotify={onNotify} onError={onError} />
      ) : (
        <GrammarPanel onRefresh={onRefresh} onNotify={onNotify} onError={onError} />
      )}
    </div>
  )
}
