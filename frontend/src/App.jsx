import { startTransition, useEffect, useState } from "react"

import ContentView from "./components/ContentView"
import DashboardView from "./components/DashboardView"
import GraphView from "./components/GraphView"
import HomeView from "./components/HomeView"
import PracticarView from "./components/PracticarView"
import { api } from "./lib/api"

const TABS = [
  {
    id: "home",
    label: "Inicio",
    desc: "Estado del sistema, próximos pasos y cómo funciona todo",
  },
  {
    id: "content",
    label: "Material",
    desc: "Importa videos, audios y documentos — transcríbelos y guárdalos en biblioteca",
  },
  {
    id: "practicar",
    label: "Practicar",
    desc: "Vocabulario adaptativo y quiz de gramática — solo ves lo que aún no dominas",
  },
  {
    id: "graph",
    label: "Explorar",
    desc: "Pregúntale al LLM local usando tu material indexado como contexto",
  },
  {
    id: "dashboard",
    label: "Progreso",
    desc: "Estadísticas, temas débiles y rango gramatical acumulados",
  },
]

function ErrorModal({ message, onClose }) {
  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-red-100 bg-red-50 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="block h-2 w-2 rounded-full bg-red-500" />
            <p className="text-sm font-bold text-red-900">Error</p>
          </div>
          <button onClick={onClose} className="text-sm text-red-400 hover:text-red-700">✕</button>
        </div>
        <div className="max-h-64 overflow-auto p-6">
          <p className="whitespace-pre-wrap break-all font-mono text-sm leading-6 text-stone-700">{message}</p>
        </div>
        <div className="border-t border-stone-100 px-6 py-4">
          <button onClick={onClose} className="btn btn-ghost w-full py-2.5 text-sm">
            Entendido
          </button>
        </div>
      </div>
    </div>
  )
}

function StatusPill({ loading, error, message }) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
        <span className="dot-pulse block h-1.5 w-1.5 rounded-full bg-amber-500" />
        Conectando
      </span>
    )
  }
  if (error) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
        <span className="block h-1.5 w-1.5 rounded-full bg-red-500" />
        Sin conexión
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">
      <span className="block h-1.5 w-1.5 rounded-full bg-green-500" />
      {message}
    </span>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState("home")
  const [dashboard, setDashboard] = useState(null)
  const [content, setContent] = useState([])
  const [models, setModels] = useState(null)
  const [selectedLlm, setSelectedLlm] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [statusMessage, setStatusMessage] = useState("Backend conectado")
  const [errorModal, setErrorModal] = useState(null)

  useEffect(() => { refreshAll() }, [])

  async function refreshAll() {
    setLoading(true)
    setError("")
    try {
      const [dashData, contentData, modelData] = await Promise.all([
        api("/dashboard/summary"),
        api("/content"),
        api("/models"),
      ])
      startTransition(() => {
        setDashboard(dashData)
        setContent(contentData)
        setModels(modelData)
        setSelectedLlm((cur) => cur || modelData.preferred_llm || modelData.catalog[0]?.id || "")
        setStatusMessage("Backend conectado")
      })
    } catch (failure) {
      setError(failure.message)
      setStatusMessage("Sin conexión")
    } finally {
      setLoading(false)
    }
  }

  async function refreshDashboard() {
    try {
      const data = await api("/dashboard/summary")
      startTransition(() => setDashboard(data))
    } catch (failure) {
      setError(failure.message)
    }
  }

  async function refreshContent() {
    try {
      const data = await api("/content")
      startTransition(() => setContent(data))
    } catch (failure) {
      setError(failure.message)
    }
  }

  function navigate(tabId) { startTransition(() => setActiveTab(tabId)) }
  function notify(text) { setStatusMessage(text) }
  function onError(msg) { setErrorModal(msg) }

  const activeTabMeta = TABS.find((t) => t.id === activeTab) ?? TABS[0]
  const installedLlms = models?.installed_llms ?? []

  return (
    <main className="app-frame page-shell bg-[#fafaf8]">
      {errorModal && <ErrorModal message={errorModal} onClose={() => setErrorModal(null)} />}
      {/* ─── Header ─── */}
      <header className="sticky top-0 z-20 border-b border-stone-200/70 bg-[#fafaf8]/95 backdrop-blur-xl">
        <div className="mx-auto max-w-[1600px] px-5">

          {/* Top row — brand + controls */}
          <div className="flex items-center justify-between gap-4 py-3">
            <div className="flex items-center gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                  English Studio
                </p>
                <p className="text-sm font-semibold text-stone-900">Sistema local de inglés</p>
              </div>
              <StatusPill loading={loading} error={error} message={statusMessage} />
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 md:flex">
                <label className="text-xs text-stone-400">Modelo IA</label>
                <select
                  value={selectedLlm}
                  onChange={(e) => setSelectedLlm(e.target.value)}
                  className="field rounded-lg border px-3 py-1.5 text-xs text-stone-700 outline-none"
                >
                  {(models?.catalog ?? []).map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label} {model.installed ? "✓" : "↓"}
                    </option>
                  ))}
                </select>
                {installedLlms.length === 0 && (
                  <span className="text-xs text-amber-700">Ningún LLM instalado</span>
                )}
              </div>
              <button onClick={refreshAll} className="btn btn-ghost px-3 py-1.5 text-xs">
                Actualizar
              </button>
            </div>
          </div>

          {/* Tab island */}
          <div className="pb-3">
            <nav className="tab-island">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => navigate(tab.id)}
                  className={`tab-btn${activeTab === tab.id ? " tab-active" : ""}`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Description strip */}
        <div className="border-t border-stone-200/50 bg-stone-50/70 px-5 py-1.5">
          <div className="mx-auto max-w-[1600px]">
            <p className="text-xs text-stone-400">
              <span className="mr-2 font-semibold text-stone-600">{activeTabMeta.label}.</span>
              {activeTabMeta.desc}
            </p>
          </div>
        </div>
      </header>

      {/* ─── Error banner ─── */}
      {error && (
        <div className="border-b border-red-200 bg-red-50 px-5 py-3">
          <div className="mx-auto max-w-[1600px] text-sm text-red-700">
            <strong>Error de conexión:</strong> {error} — ¿está corriendo el backend en el puerto 8000?
          </div>
        </div>
      )}

      {/* ─── Notification strip ─── */}
      {!error && !loading && statusMessage !== "Backend conectado" && (
        <div className="border-b border-stone-200 bg-stone-50 px-5 py-1.5">
          <div className="mx-auto max-w-[1600px] text-xs text-stone-500">{statusMessage}</div>
        </div>
      )}

      {/* ─── Content ─── */}
      <section className="mx-auto max-w-[1600px] px-5 py-7">
        {loading ? (
          <div className="card p-12 text-center text-sm text-stone-400">
            Conectando con el backend local...
          </div>
        ) : (
          <>
            {activeTab === "home" && (
              <HomeView summary={dashboard} content={content} onNavigate={navigate} />
            )}
            {activeTab === "content" && (
              <ContentView
                content={content}
                models={models}
                selectedLlm={selectedLlm}
                onRefreshContent={refreshContent}
                onRefreshDashboard={refreshDashboard}
                onNotify={notify}
                onError={onError}
              />
            )}
            {activeTab === "practicar" && (
              <PracticarView onRefresh={refreshDashboard} onNotify={notify} onError={onError} />
            )}
            {activeTab === "graph" && (
              <GraphView
                graph={dashboard?.graph}
                content={content}
                selectedLlm={selectedLlm}
                onNotify={notify}
                onError={onError}
              />
            )}
            {activeTab === "dashboard" && (
              <DashboardView summary={dashboard} onNavigate={navigate} />
            )}
          </>
        )}
      </section>
    </main>
  )
}
