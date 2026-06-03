import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react"

import { api } from "../lib/api"
import { cn } from "../lib/cn"

function kindLabel(kind) {
  return { video: "Video", audio: "Audio", pdf: "PDF", text: "Texto", content: "Contenido" }[kind] || kind
}

function asrLabel(models, asrKey) {
  return models?.asr_catalog?.find((item) => item.id === asrKey)?.label || asrKey
}

function timeLabel(seconds) {
  const value = Number(seconds || 0)
  const m = Math.floor(value / 60)
  const s = Math.floor(value % 60)
  return `${m}:${String(s).padStart(2, "0")}`
}

function subtitleTracksForMedia({ metadata = {}, lastVttUrl = "", bilingual = false }) {
  const tracks = []
  const ytTracks = metadata.youtube_subtitle_urls || {}
  if (lastVttUrl) {
    tracks.push({
      src: lastVttUrl,
      srcLang: "en",
      label: bilingual ? "ASR ingles + espanol" : "ASR ingles",
      default: !ytTracks.en && !ytTracks.es,
    })
  }
  if (ytTracks.en) tracks.push({ src: ytTracks.en, srcLang: "en", label: "YouTube ingles", default: !lastVttUrl })
  if (ytTracks.es) tracks.push({ src: ytTracks.es, srcLang: "es", label: "YouTube espanol", default: false })
  return tracks
}

function cleanName(sourceName) {
  return (sourceName ?? "")
    .replace(/^\d{8}_\d{6}_/, "")
    .replace(/_/g, " ")
    .replace(/\.\w+$/, "")
    .trim()
}

/* ─── Wizard indicator ──────────────────────────────────────────────────── */
const WIZARD_STEPS = [
  { n: 1, label: "Cargar" },
  { n: 2, label: "Transcribir" },
  { n: 3, label: "Revisar" },
  { n: 4, label: "Guardar" },
]

function WizardIndicator({ current, onGoto, canGoto }) {
  const total = WIZARD_STEPS.length
  const progressPct = ((current - 1) / (total - 1)) * 100

  return (
    <div className="mx-auto w-fit space-y-4">
      {/* Dots + labels — each button is w-24 so dot center = 48px from edge */}
      <div className="relative flex gap-10">
        {/* Line from center-of-first-dot to center-of-last-dot */}
        <div className="absolute left-12 right-12 top-[6px] h-px bg-stone-200" />

        {WIZARD_STEPS.map((step) => {
          const done = step.n < current
          const active = step.n === current
          const accessible = canGoto(step.n)
          return (
            <button
              key={step.n}
              onClick={() => accessible && onGoto(step.n)}
              disabled={!accessible}
              className={cn(
                "relative z-10 flex w-24 flex-col items-center gap-3",
                accessible ? "cursor-pointer" : "cursor-not-allowed",
              )}
            >
              <div
                className={cn(
                  "h-3 w-3 rounded-full transition-all duration-200",
                  active && "bg-stone-900 ring-4 ring-stone-200",
                  done && "bg-stone-900",
                  !active && !done && "bg-stone-200",
                )}
              />
              <span
                className={cn(
                  "text-center text-xs transition-colors",
                  active && "font-bold text-stone-900",
                  done && "text-stone-500",
                  !active && !done && accessible && "text-stone-400",
                  !active && !done && !accessible && "text-stone-300",
                )}
              >
                {step.label}
              </span>
            </button>
          )
        })}
      </div>

      {/* Progress bar — same horizontal extent as the dot line */}
      <div className="mx-12 h-1 rounded-full bg-stone-100">
        <div
          className="h-full rounded-full bg-stone-900 transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  )
}

/* ─── Blob loader ───────────────────────────────────────────────────────── */
function BlobLoader({ label }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-6 py-16">
      <div className="blob-loader">
        <div className="blobs">
          <div className="blob-center" />
          <div className="blob" />
          <div className="blob" />
          <div className="blob" />
          <div className="blob" />
          <div className="blob" />
          <div className="blob" />
        </div>
      </div>
      {label && (
        <p className="text-sm font-semibold text-stone-600">{label}</p>
      )}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        version="1.1"
        style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }}
      >
        <defs>
          <filter id="goo">
            <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7"
              result="goo"
            />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
        </defs>
      </svg>
    </div>
  )
}

/* ─── Working overlay ───────────────────────────────────────────────────── */
function WorkingOverlay({ label }) {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    setSecs(0)
    const id = setInterval(() => setSecs((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [label])

  const mins = Math.floor(secs / 60)
  const s = secs % 60
  const timeStr = mins > 0 ? `${mins}m ${s}s` : `${s}s`
  const isLong = /transcrib|indexand|generand|procesand/i.test(label)

  return (
    <div className="fixed bottom-6 left-1/2 z-50 w-full max-w-md -translate-x-1/2 px-4">
      <div className="card overflow-hidden shadow-2xl">
        <div className="h-1 overflow-hidden bg-stone-100">
          <div className="bar-indeterminate h-full w-1/3 rounded-full bg-blue-500" />
        </div>
        <div className="flex items-center gap-4 px-5 py-4">
          <span className="h-5 w-5 flex-shrink-0 animate-spin rounded-full border-2 border-stone-200 border-t-blue-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-stone-900">{label}</p>
            {isLong && (
              <p className="mt-0.5 text-xs text-stone-400">Puede tardar varios minutos — no cierres la ventana</p>
            )}
          </div>
          <div className="flex-shrink-0 text-right">
            <p className="text-sm font-bold tabular-nums text-stone-600">{timeStr}</p>
            <p className="text-[10px] text-stone-400">transcurrido</p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── Subtitle patch hook ───────────────────────────────────────────────── */
function useCenteredSubtitles(ref) {
  function patchCue(cue) {
    if (!(cue instanceof VTTCue)) return
    cue.position = 50
    cue.positionAlign = "center"
    cue.align = "center"
  }
  function patchTrack(track) {
    if (track.cues) for (const cue of track.cues) patchCue(cue)
    track.addEventListener("cuechange", () => {
      if (track.activeCues) for (const cue of track.activeCues) patchCue(cue)
    })
  }
  function onLoaded() {
    const video = ref.current
    if (!video) return
    for (const track of video.textTracks) patchTrack(track)
    video.textTracks.addEventListener("addtrack", (e) => patchTrack(e.track))
  }
  return { onLoaded }
}

/* ─── Media player ──────────────────────────────────────────────────────── */
function MediaPlayer({ asset, bilingual = false, videoRef }) {
  const { onLoaded } = useCenteredSubtitles(videoRef)

  if (!asset) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50 text-center text-sm text-stone-400">
        <div>
          <p className="text-4xl font-black text-stone-200">▶</p>
          <p className="mt-3">Carga un archivo o pega una URL de YouTube para empezar.</p>
        </div>
      </div>
    )
  }
  if (asset.media_kind === "video") {
    return (
      <video
        ref={videoRef}
        onLoadedMetadata={onLoaded}
        controls
        className="aspect-video w-full rounded-xl border border-stone-200 bg-stone-900"
      >
        <source src={asset.media_url} />
        {subtitleTracksForMedia({ metadata: asset.metadata, lastVttUrl: asset.last_vtt_url, bilingual }).map((track) => (
          <track
            key={`${track.label}-${track.src}`}
            default={track.default}
            kind="subtitles"
            srcLang={track.srcLang}
            label={track.label}
            src={track.src}
          />
        ))}
      </video>
    )
  }
  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50 p-6">
      <audio controls src={asset.media_url} className="w-full" />
    </div>
  )
}

/* ─── Source controls ───────────────────────────────────────────────────── */
function SourceControls({ sourceMode, setSourceMode, mediaFile, setMediaFile, youtubeUrl, setYoutubeUrl, audioOnly, setAudioOnly, uploadLocalMedia, downloadYouTube, working }) {
  return (
    <section className="card p-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Paso 1 — Cargar medio</p>
      <p className="mt-1 text-xs leading-5 text-stone-500">Sube un archivo local o descarga directamente de YouTube.</p>

      <div className="mt-4 grid grid-cols-2 gap-1 rounded-xl border border-stone-100 bg-stone-50 p-1">
        {[["local", "Archivo local"], ["youtube", "YouTube"]].map(([mode, label]) => (
          <button
            key={mode}
            onClick={() => setSourceMode(mode)}
            className={`px-4 py-2 text-sm font-semibold transition-all ${
              sourceMode === mode
                ? "rounded-lg bg-white text-stone-900 shadow-sm"
                : "text-stone-500 hover:text-stone-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {sourceMode === "local" ? (
        <div className="mt-4">
          <label className="block">
            <span className="mb-2 block text-xs text-stone-400">
              Formatos: mp4, mkv, mov, webm, mp3, wav, m4a, flac, ogg
            </span>
            <input
              type="file"
              accept=".mp4,.mkv,.mov,.webm,.avi,.m4v,.mp3,.wav,.m4a,.aac,.flac,.ogg"
              onChange={(e) => setMediaFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-stone-600 file:mr-4 file:rounded-lg file:border-0 file:bg-stone-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-stone-700"
            />
          </label>
          <button onClick={uploadLocalMedia} disabled={working || !mediaFile} className="btn btn-primary mt-4 w-full py-3 text-sm">
            {working ? "Cargando..." : "Cargar para validar"}
          </button>
        </div>
      ) : (
        <div className="mt-4">
          <label className="block">
            <span className="mb-2 block text-xs text-stone-400">URL del video</span>
            <input
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="field w-full rounded-xl border px-4 py-3 text-sm outline-none placeholder:text-stone-300"
            />
          </label>
          <label className="mt-3 flex items-center gap-3 text-sm text-stone-500">
            <input type="checkbox" checked={audioOnly} onChange={() => setAudioOnly((v) => !v)} className="accent-blue-600" />
            Solo audio (más rápido, sin imagen)
          </label>
          <button onClick={downloadYouTube} disabled={working || !youtubeUrl.trim()} className="btn btn-primary mt-4 w-full py-3 text-sm">
            {working ? "Descargando..." : "Descargar para validar"}
          </button>
        </div>
      )}
    </section>
  )
}

/* ─── ASR controls ──────────────────────────────────────────────────────── */
function AsrControls({ asset, models, selectedAsr, setSelectedAsr, language, setLanguage, translateMedia, setTranslateMedia, transcribeAsset, working }) {
  return (
    <section className="card p-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Paso 2 — Transcribir</p>
      <p className="mt-1 text-xs leading-5 text-stone-500">
        El modelo ASR convierte el audio a texto. Si el resultado no es bueno, corrígelo en el editor.
      </p>
      <div className="mt-4 grid gap-3">
        <label className="block">
          <span className="mb-2 block text-[10px] font-semibold uppercase tracking-widest text-stone-400">Modelo ASR</span>
          <select value={selectedAsr} onChange={(e) => setSelectedAsr(e.target.value)} className="field w-full rounded-xl border px-4 py-3 text-sm outline-none">
            {(models?.asr_catalog ?? []).map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-[10px] font-semibold uppercase tracking-widest text-stone-400">Idioma del audio</span>
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="field w-full rounded-xl border px-4 py-3 text-sm outline-none">
            <option value="en">Inglés</option>
          </select>
        </label>
        <label className="flex items-center gap-3 text-sm text-stone-500">
          <input type="checkbox" checked={translateMedia} onChange={() => setTranslateMedia((v) => !v)} className="accent-blue-600" />
          Generar traducción al español para revisar
        </label>
      </div>
      <button onClick={transcribeAsset} disabled={working || !asset?.asset_id} className="btn btn-primary mt-4 w-full py-3 text-sm">
        {working ? "Transcribiendo..." : "Transcribir"}
      </button>
      {!asset?.asset_id && (
        <p className="mt-3 text-xs text-stone-400">Carga un medio primero para habilitar la transcripción.</p>
      )}
    </section>
  )
}

/* ─── Pending media queue ────────────────────────────────────────────────── */
function PendingQueue({ items, onUse, onDelete, working }) {
  return (
    <section className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Medios por procesar</p>
          <p className="mt-0.5 text-xs text-stone-400">Archivos cargados aún no guardados en biblioteca.</p>
        </div>
        <span className="rounded-lg border border-stone-100 bg-stone-50 px-2 py-1 text-xs font-semibold text-stone-500">
          {items.length}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-xs leading-5 text-stone-400">
          Los archivos que cargues aparecerán aquí hasta que los transcribas y guardes.
        </p>
      ) : (
        <div className="mt-4 max-h-72 space-y-2 overflow-auto pr-1">
          {items.map((item) => (
            <article key={item.media_id} className="rounded-xl border border-stone-100 bg-stone-50 p-3">
              <p className="truncate text-sm font-semibold text-stone-900">{item.source_name}</p>
              <p className="mt-1 text-xs text-stone-400">
                {(item.size_bytes / (1024 * 1024)).toFixed(1)} MB · {kindLabel(item.media_kind)}
                {item.transcript_saved ? " · transcripción guardada" : ""}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button onClick={() => onUse(item.media_id)} disabled={working} className="btn btn-green py-2 text-xs">
                  Usar
                </button>
                <button onClick={() => onDelete(item.media_id)} disabled={working} className="btn btn-red py-2 text-xs">
                  Borrar
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

/* ─── Document importer ─────────────────────────────────────────────────── */
function DocumentImporter({ documentFile, setDocumentFile, translateDoc, setTranslateDoc, importDocument, working }) {
  return (
    <section className="card p-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Documentos</p>
      <p className="mt-1 text-xs leading-5 text-stone-500">
        PDF, TXT o MD — el sistema extrae el texto y lo guarda en biblioteca sin transcripción.
      </p>
      <input
        type="file"
        accept=".pdf,.txt,.md"
        onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
        className="mt-4 block w-full text-sm text-stone-600 file:mr-4 file:rounded-lg file:border-0 file:bg-stone-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-stone-700"
      />
      <label className="mt-4 flex items-center gap-3 text-sm text-stone-500">
        <input type="checkbox" checked={translateDoc} onChange={() => setTranslateDoc((v) => !v)} className="accent-blue-600" />
        Traducir al español al importar
      </label>
      <button onClick={importDocument} disabled={working || !documentFile} className="btn btn-primary mt-4 w-full py-3 text-sm">
        {working ? "Importando..." : "Importar documento"}
      </button>
    </section>
  )
}

/* ─── Segment editor ────────────────────────────────────────────────────── */
function SegmentEditor({ segments, setSegments, working, onApply, onSave, videoRef }) {
  const [currentTime, setCurrentTime] = useState(0)
  const activeRowRef = useRef(null)

  useEffect(() => {
    const video = videoRef?.current
    if (!video) return
    const handler = () => setCurrentTime(video.currentTime)
    video.addEventListener("timeupdate", handler)
    return () => video.removeEventListener("timeupdate", handler)
  }, [videoRef])

  const activeIndex = segments.findIndex(
    (s) => currentTime >= (s.start ?? 0) && currentTime <= (s.end ?? 0)
  )

  useEffect(() => {
    activeRowRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [activeIndex])

  function seekTo(seconds) {
    const video = videoRef?.current
    if (video) video.currentTime = seconds
  }

  if (segments.length === 0) {
    return (
      <div className="flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50 p-8 text-center">
        <p className="text-4xl font-black text-stone-200">✍</p>
        <p className="mt-3 text-sm font-semibold text-stone-600">Editor de segmentos</p>
        <p className="mt-2 max-w-xs text-sm leading-6 text-stone-400">
          Después de transcribir aparecerán aquí los segmentos. Corrige el inglés y el español antes de guardar.
        </p>
      </div>
    )
  }

  return (
    <section className="card overflow-hidden">
      <div className="sticky top-0 z-10 flex flex-col gap-3 border-b border-stone-100 bg-white/95 p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Paso 3 — Revisa y corrige</p>
          <h3 className="mt-1 text-base font-semibold text-stone-900">
            {segments.length} segmento{segments.length !== 1 ? "s" : ""}
          </h3>
          <p className="mt-0.5 text-xs text-stone-400">
            Haz clic en el tiempo para ir a esa parte del video.
          </p>
        </div>
        <div className={`grid gap-2 ${onSave ? "sm:grid-cols-2" : "sm:grid-cols-1"}`}>
          <button onClick={onApply} disabled={working} className="btn btn-green px-4 py-2.5 text-sm">
            Aplicar correcciones
          </button>
          {onSave && (
            <button onClick={onSave} disabled={working} className="btn btn-amber px-4 py-2.5 text-sm">
              Guardar en biblioteca
            </button>
          )}
        </div>
      </div>

      <div className="max-h-[680px] divide-y divide-stone-100 overflow-auto">
        {segments.map((segment, index) => {
          const isActive = index === activeIndex
          return (
            <article
              key={`${segment.start}-${index}`}
              ref={isActive ? activeRowRef : null}
              className={`grid gap-3 p-4 lg:grid-cols-[72px_1fr_1fr] transition-colors ${
                isActive ? "bg-blue-50" : ""
              }`}
            >
              <button
                onClick={() => seekTo(segment.start ?? 0)}
                className={`text-left text-xs transition-colors hover:text-blue-600 ${
                  isActive ? "font-semibold text-blue-600" : "text-stone-400"
                }`}
                title="Ir a este momento"
              >
                <p>{timeLabel(segment.start)}</p>
                <p>{timeLabel(segment.end)}</p>
                {isActive && <p className="mt-1 text-[9px] uppercase tracking-wide text-blue-400">▶ activo</p>}
              </button>
              <label className="block">
                <span className="mb-2 block text-[10px] font-semibold uppercase tracking-widest text-stone-400">Inglés</span>
                <textarea
                  value={segment.text_en ?? ""}
                  onChange={(e) => setSegments((cur) => cur.map((item, i) => i === index ? { ...item, text_en: e.target.value } : item))}
                  rows={3}
                  className="field w-full resize-y rounded-xl border px-3 py-2 text-sm leading-6 outline-none"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[10px] font-semibold uppercase tracking-widest text-stone-400">Español</span>
                <textarea
                  value={segment.text_es ?? ""}
                  onChange={(e) => setSegments((cur) => cur.map((item, i) => i === index ? { ...item, text_es: e.target.value } : item))}
                  rows={3}
                  className="field w-full resize-y rounded-xl border px-3 py-2 text-sm leading-6 outline-none"
                />
              </label>
            </article>
          )
        })}
      </div>
    </section>
  )
}

/* ─── Library browser ───────────────────────────────────────────────────── */
function LibraryBrowser({ content, search, setSearch, activeItem, activeId, setActiveId, selectedIds, toggleSelected, topic, setTopic, importVocab, setImportVocab, importGrammar, setImportGrammar, processCurrent, indexSelected, syncRecords, cleanupFiles, deleteContentItem, working }) {
  return (
    <section className="grid gap-5 xl:grid-cols-[0.86fr_1.14fr]">
      {/* List */}
      <article className="card p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-600">Biblioteca</p>
            <h2 className="mt-1 text-2xl font-bold text-stone-900">Material aprobado</h2>
            <p className="mt-1 text-sm text-stone-500">Solo el contenido que validaste y guardaste.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <button onClick={syncRecords} disabled={working} className="btn btn-ghost px-4 py-2 text-xs" title="Sincroniza la base de datos con los archivos en disco">
              Sincronizar
            </button>
            <button onClick={cleanupFiles} disabled={working} className="btn btn-amber px-4 py-2 text-xs" title="Elimina archivos temporales y residuos de transcripciones fallidas">
              Limpiar residuos
            </button>
          </div>
        </div>

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por título, tipo o contenido..."
          className="field mt-5 w-full rounded-xl border px-4 py-3 text-sm outline-none placeholder:text-stone-300"
        />

        <div className="mt-4 max-h-[620px] space-y-2 overflow-auto pr-1">
          {content.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-200 p-8 text-center">
              <p className="text-3xl font-black text-stone-200">□</p>
              <p className="mt-3 text-sm font-semibold text-stone-600">Biblioteca vacía</p>
              <p className="mt-2 text-sm text-stone-400">
                Sube un video o audio, transcríbelo y guárdalo para verlo aquí.
              </p>
            </div>
          ) : (
            content.map((item) => (
              <article
                key={item.id}
                className={`rounded-xl border p-4 transition-all ${
                  activeId === item.id
                    ? "border-blue-200 bg-blue-50"
                    : "border-stone-100 bg-stone-50 hover:border-stone-200"
                }`}
              >
                <div className="flex gap-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleSelected(item.id)}
                    className="mt-1 accent-blue-600"
                    title="Seleccionar para indexar en el grafo"
                  />
                  <button onClick={() => setActiveId(item.id)} className="min-w-0 flex-1 text-left">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">{kindLabel(item.kind)}</p>
                    <h3 className="mt-1 truncate text-base font-semibold text-stone-900">
                      {item.source_metadata?.title || item.source}
                    </h3>
                    <p className="mt-1.5 line-clamp-2 text-sm leading-5 text-stone-400">
                      {item.text_preview || "Sin vista previa"}
                    </p>
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </article>

      {/* Detail */}
      <article className="card p-5">
        {!activeItem ? (
          <div className="flex min-h-[360px] items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50 p-8 text-center">
            <div>
              <p className="text-4xl font-black text-stone-200">↑</p>
              <p className="mt-3 text-sm text-stone-400">Selecciona un contenido para verlo, procesarlo o indexarlo.</p>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Contenido seleccionado</p>
            <h3 className="mt-2 text-2xl font-bold text-stone-900">
              {activeItem.source_metadata?.title || activeItem.source}
            </h3>
            <p className="mt-1 text-sm text-stone-400">
              {kindLabel(activeItem.kind)} · {activeItem.language} · {activeItem.text_en_length?.toLocaleString()} caracteres
            </p>

            {activeItem.media_url && (
              <div className="mt-5">
                {activeItem.kind === "video" ? (
                  <video controls className="aspect-video w-full rounded-xl border border-stone-200 bg-stone-900">
                    <source src={activeItem.media_url} />
                    {subtitleTracksForMedia({ metadata: activeItem.source_metadata, lastVttUrl: activeItem.vtt_url, bilingual: true }).map((track) => (
                      <track key={`${track.label}-${track.src}`} default={track.default} kind="subtitles" srcLang={track.srcLang} label={track.label} src={track.src} />
                    ))}
                  </video>
                ) : activeItem.kind === "audio" ? (
                  <audio controls src={activeItem.media_url} className="w-full" />
                ) : null}
              </div>
            )}

            {/* Process & index panel */}
            <div className="mt-5 rounded-xl border border-stone-100 bg-stone-50 p-5">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                Extraer vocabulario y gramática
              </p>
              <p className="mt-1 text-xs leading-5 text-stone-500">
                El LLM analiza el texto y añade palabras y reglas al motor de repaso.
              </p>

              <label className="mt-4 block">
                <span className="mb-2 block text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                  Tema (opcional)
                </span>
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="ej. phrasal verbs, present perfect, conversación"
                  className="field w-full rounded-xl border px-4 py-3 text-sm outline-none placeholder:text-stone-300"
                />
              </label>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <label className="flex items-center gap-3 rounded-xl border border-stone-200 bg-white p-3 text-sm text-stone-600">
                  <input type="checkbox" checked={importVocab} onChange={() => setImportVocab((v) => !v)} className="accent-blue-600" />
                  Importar vocabulario
                </label>
                <label className="flex items-center gap-3 rounded-xl border border-stone-200 bg-white p-3 text-sm text-stone-600">
                  <input type="checkbox" checked={importGrammar} onChange={() => setImportGrammar((v) => !v)} className="accent-blue-600" />
                  Importar gramática
                </label>
              </div>

              <div className="mt-4 grid gap-2 md:grid-cols-2">
                <button onClick={processCurrent} disabled={working} className="btn btn-primary py-2.5 text-sm">
                  Procesar este contenido
                </button>
                <button onClick={indexSelected} disabled={working || selectedIds.length === 0} className="btn btn-amber py-2.5 text-sm">
                  Indexar seleccionados ({selectedIds.length})
                </button>
              </div>

              {selectedIds.length === 0 && (
                <p className="mt-2 text-xs text-stone-400">
                  Marca la casilla de uno o varios contenidos para indexarlos en el grafo.
                </p>
              )}
            </div>

            <button onClick={() => deleteContentItem(activeItem.id)} disabled={working} className="btn btn-red mt-4 w-full py-2.5 text-sm">
              Borrar de biblioteca y eliminar archivos
            </button>

            {/* Text preview */}
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-stone-100 bg-stone-50 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Texto en inglés</p>
                <div className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-6 text-stone-600">
                  {activeItem.text_en || activeItem.text_preview}
                </div>
              </div>
              <div className="rounded-xl border border-stone-100 bg-stone-50 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Traducción al español</p>
                <div className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-6 text-stone-600">
                  {activeItem.text_es || <span className="text-stone-400">Sin traducción guardada.</span>}
                </div>
              </div>
            </div>
          </div>
        )}
      </article>
    </section>
  )
}

/* ─── Main ContentView ──────────────────────────────────────────────────── */
export default function ContentView({ content, models, selectedLlm, onRefreshContent, onRefreshDashboard, onNotify, onError }) {
  const [search, setSearch] = useState("")
  const [activeId, setActiveId] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [topic, setTopic] = useState("")
  const [importVocab, setImportVocab] = useState(true)
  const [importGrammar, setImportGrammar] = useState(true)
  const [working, setWorking] = useState(false)
  const [sourceMode, setSourceMode] = useState("youtube")
  const [mediaFile, setMediaFile] = useState(null)
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [audioOnly, setAudioOnly] = useState(false)
  const [language, setLanguage] = useState("en")
  const [translateMedia, setTranslateMedia] = useState(true)
  const [translateDoc, setTranslateDoc] = useState(true)
  const [documentFile, setDocumentFile] = useState(null)
  const [selectedAsr, setSelectedAsr] = useState("")
  const [asset, setAsset] = useState(null)
  const [existingMedia, setExistingMedia] = useState([])
  const [editedSegments, setEditedSegments] = useState([])
  const [taskLabel, setTaskLabel] = useState(null)
  const [contentTab, setContentTab] = useState("library")
  const [wizardStep, setWizardStep] = useState(1)
  const [sourceType, setSourceType] = useState("media")
  const videoRef = useRef(null)

  useEffect(() => {
    if (!selectedAsr && models?.asr_catalog?.length) setSelectedAsr(models.asr_catalog[0].id)
  }, [models, selectedAsr])

  useEffect(() => { refreshExistingMedia() }, [])
  useEffect(() => { setEditedSegments(asset?.segments ?? []) }, [asset])

  // Switch to upload tab when an asset is loaded
  useEffect(() => {
    if (asset) setContentTab("upload")
  }, [asset?.asset_id])

  // Auto-advance wizard
  useEffect(() => {
    if (asset?.asset_id && wizardStep === 1) setWizardStep(2)
  }, [asset?.asset_id])

  useEffect(() => {
    if (asset?.transcript_text && wizardStep <= 2) setWizardStep(3)
  }, [asset?.transcript_text])

  // Reset wizard when asset is cleared
  useEffect(() => {
    if (!asset) setWizardStep(1)
  }, [asset])

  function canGoto(n) {
    if (n === 1) return true
    if (n === 2) return Boolean(asset?.asset_id)
    if (n === 3) return Boolean(asset?.transcript_text)
    if (n === 4) return Boolean(asset?.transcript_text)
    return false
  }

  const deferredSearch = useDeferredValue(search)
  const visibleItems = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase()
    return content.filter((item) =>
      `${item.source} ${item.kind} ${item.text_preview}`.toLowerCase().includes(q)
    )
  }, [content, deferredSearch])

  const activeItem = visibleItems.find((item) => item.id === activeId) ?? visibleItems[0] ?? null
  const hasPreview = editedSegments.some((s) => s.text_es)

  async function refreshExistingMedia() {
    try {
      const items = await api("/media/library")
      setExistingMedia(items)
    } catch (error) {
      onNotify(error.message)
    }
  }

  async function syncRecords() {
    setTaskLabel("Sincronizando registros...")
    setWorking(true)
    try {
      const r = await api("/content/sync", { method: "POST" })
      onNotify(r.message)
      await onRefreshContent()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function cleanupFiles() {
    setTaskLabel("Limpiando archivos residuales...")
    setWorking(true)
    try {
      const r = await api("/content/cleanup", { method: "POST" })
      onNotify(r.message)
      await Promise.all([onRefreshContent(), onRefreshDashboard(), refreshExistingMedia()])
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function uploadLocalMedia() {
    if (!mediaFile) return onNotify("Elige un archivo de audio o video.")
    const fd = new FormData()
    fd.append("file", mediaFile)
    setTaskLabel("Cargando archivo...")
    setWorking(true)
    try {
      const r = await api("/ingest/media/upload", { method: "POST", body: fd })
      setAsset(r.asset)
      onNotify(r.message)
      await refreshExistingMedia()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function downloadYouTube() {
    if (!youtubeUrl.trim()) return onNotify("Pega una URL válida de YouTube.")
    setTaskLabel("Descargando de YouTube...")
    setWorking(true)
    try {
      const r = await api("/ingest/media/youtube", { method: "POST", body: { url: youtubeUrl.trim(), audio_only: audioOnly } })
      setAsset(r.asset)
      onNotify(r.message)
      if (r.asset?.metadata?.youtube_subtitles_warning) onNotify(r.asset.metadata.youtube_subtitles_warning)
      await refreshExistingMedia()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function transcribeAsset() {
    if (!asset?.asset_id) return onNotify("Primero carga o descarga un medio.")
    if (!selectedAsr) return onNotify("Selecciona un modelo ASR.")
    setTaskLabel(`Transcribiendo audio con ${selectedAsr}...`)
    setWorking(true)
    try {
      const r = await api("/ingest/media/transcribe", { method: "POST", body: { asset_id: asset.asset_id, asr_key: selectedAsr, language } })
      setAsset(r.asset)
      onNotify(r.message)
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function previewTranslation() {
    if (!asset?.asset_id || !asset?.transcript_text) return onNotify("Primero genera una transcripción.")
    setTaskLabel("Generando traducción bilingüe...")
    setWorking(true)
    try {
      const r = await api("/ingest/media/preview", { method: "POST", body: { asset_id: asset.asset_id, llm_model: selectedLlm, translate: translateMedia } })
      setAsset(r.asset)
      onNotify(r.message)
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function applyCorrections() {
    if (!asset?.asset_id || editedSegments.length === 0) return onNotify("No hay segmentos para corregir.")
    setTaskLabel("Aplicando correcciones...")
    setWorking(true)
    try {
      const r = await api("/ingest/media/corrections", {
        method: "POST",
        body: { asset_id: asset.asset_id, segments: editedSegments.map((s, i) => ({ index: i, text_en: s.text_en ?? "", text_es: s.text_es ?? "" })) },
      })
      setAsset(r.asset)
      onNotify(r.message)
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function useExistingMedia(mediaId) {
    setTaskLabel("Cargando medio...")
    setWorking(true)
    try {
      const r = await api("/ingest/media/library", { method: "POST", body: { media_id: mediaId } })
      setAsset(r.asset)
      onNotify(r.message)
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function deleteExistingMedia(mediaId) {
    setTaskLabel("Eliminando medio...")
    setWorking(true)
    try {
      const r = await api(`/media/library/${encodeURIComponent(mediaId)}`, { method: "DELETE" })
      onNotify(r.message)
      setAsset(null)
      setEditedSegments([])
      await refreshExistingMedia()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function saveTranscription() {
    if (!asset?.asset_id || !asset?.transcript_text) return onNotify("Primero genera y valida una transcripción.")
    setTaskLabel("Guardando en biblioteca...")
    setWorking(true)
    try {
      if (editedSegments.length > 0) {
        await api("/ingest/media/corrections", {
          method: "POST",
          body: { asset_id: asset.asset_id, segments: editedSegments.map((s, i) => ({ index: i, text_en: s.text_en ?? "", text_es: s.text_es ?? "" })) },
        })
      }
      const r = await api("/ingest/media/save", { method: "POST", body: { asset_id: asset.asset_id, llm_model: selectedLlm, translate: translateMedia } })
      onNotify(r.message)
      setAsset(null)
      setEditedSegments([])
      setMediaFile(null)
      setYoutubeUrl("")
      setContentTab("library")
      await Promise.all([onRefreshContent(), onRefreshDashboard(), refreshExistingMedia()])
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function importDocument() {
    if (!documentFile) return onNotify("Elige un PDF, TXT o MD.")
    const fd = new FormData()
    fd.append("file", documentFile)
    fd.append("llm_model", selectedLlm)
    fd.append("translate", String(translateDoc))
    setTaskLabel("Importando documento...")
    setWorking(true)
    try {
      const r = await api("/ingest/document", { method: "POST", body: fd })
      onNotify(r.message)
      setDocumentFile(null)
      setContentTab("library")
      await Promise.all([onRefreshContent(), refreshExistingMedia()])
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function processCurrent() {
    if (!activeItem) return
    setTaskLabel("Procesando vocabulario y gramática...")
    setWorking(true)
    try {
      const r = await api(`/content/${activeItem.id}/process`, {
        method: "POST",
        body: { topic, import_vocab: importVocab, import_grammar: importGrammar, llm_model: selectedLlm },
      })
      onNotify(r.message)
      await onRefreshDashboard()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function indexSelected() {
    if (selectedIds.length === 0) return onNotify("Selecciona al menos un contenido para indexar.")
    setTaskLabel(`Indexando ${selectedIds.length} elemento${selectedIds.length !== 1 ? "s" : ""} en el grafo...`)
    setWorking(true)
    try {
      const r = await api("/graph/index", { method: "POST", body: { content_ids: selectedIds, llm_model: selectedLlm } })
      onNotify(r.message)
      await onRefreshDashboard()
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  async function deleteContentItem(contentId) {
    setTaskLabel("Eliminando contenido...")
    setWorking(true)
    try {
      const r = await api(`/content/${contentId}`, { method: "DELETE" })
      onNotify(r.message)
      setSelectedIds((cur) => cur.filter((id) => id !== contentId))
      setActiveId(null)
      await Promise.all([onRefreshContent(), onRefreshDashboard(), refreshExistingMedia()])
    } catch (e) { onError(e.message) }
    finally { setWorking(false); setTaskLabel(null) }
  }

  function toggleSelected(id) {
    setSelectedIds((cur) => cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id])
  }

  return (
    <div className="space-y-6">
      {working && taskLabel && <WorkingOverlay label={taskLabel} />}

      {/* ── Tab switcher ── */}
      <nav className="tab-island">
        <button
          onClick={() => setContentTab("library")}
          className={`tab-btn${contentTab === "library" ? " tab-active" : ""}`}
        >
          Biblioteca
          {visibleItems.length > 0 && (
            <span className="ml-2 rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-bold text-stone-500">
              {visibleItems.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setContentTab("upload")}
          className={`tab-btn${contentTab === "upload" ? " tab-active" : ""}`}
        >
          Subir contenido
          {existingMedia.length > 0 && (
            <span className="ml-2 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
              {existingMedia.length}
            </span>
          )}
        </button>
      </nav>

      {/* ── BIBLIOTECA ── */}
      {contentTab === "library" && (
        <LibraryBrowser
          content={visibleItems} search={search} setSearch={setSearch}
          activeItem={activeItem} activeId={activeItem?.id ?? activeId} setActiveId={setActiveId}
          selectedIds={selectedIds} toggleSelected={toggleSelected}
          topic={topic} setTopic={setTopic}
          importVocab={importVocab} setImportVocab={setImportVocab}
          importGrammar={importGrammar} setImportGrammar={setImportGrammar}
          processCurrent={processCurrent} indexSelected={indexSelected}
          syncRecords={syncRecords} cleanupFiles={cleanupFiles}
          deleteContentItem={deleteContentItem} working={working}
        />
      )}

      {/* ── SUBIR CONTENIDO — wizard ── */}
      {contentTab === "upload" && (
        <div className="space-y-6">

          {/* Wizard progress indicator */}
          <div className="card px-6 py-4">
            <WizardIndicator current={wizardStep} onGoto={setWizardStep} canGoto={canGoto} />
          </div>

          {/* ── Step 1: Cargar ── */}
          {wizardStep === 1 && (
            <div className="mx-auto max-w-2xl space-y-5">
              {working ? (
                <BlobLoader label={taskLabel} />
              ) : (
                <>
                  {/* Tipo de contenido */}
                  <div className="card p-5">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">¿Qué quieres subir?</p>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      {[
                        { id: "media", icon: "▶", title: "Video o audio", desc: "MP4, MKV, MP3, WAV, YouTube…" },
                        { id: "document", icon: "📄", title: "Documento", desc: "PDF, TXT o Markdown" },
                      ].map(({ id, icon, title, desc }) => (
                        <button
                          key={id}
                          onClick={() => setSourceType(id)}
                          className={`flex flex-col items-start gap-2 rounded-xl border-2 px-5 py-4 text-left transition-all ${
                            sourceType === id
                              ? "border-blue-500 bg-blue-50"
                              : "border-stone-100 bg-stone-50 hover:border-stone-200"
                          }`}
                        >
                          <span className="text-2xl">{icon}</span>
                          <span className={`text-sm font-semibold ${sourceType === id ? "text-blue-900" : "text-stone-800"}`}>
                            {title}
                          </span>
                          <span className="text-xs text-stone-400">{desc}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {sourceType === "media" && (
                    <>
                      <SourceControls
                        sourceMode={sourceMode} setSourceMode={setSourceMode}
                        mediaFile={mediaFile} setMediaFile={setMediaFile}
                        youtubeUrl={youtubeUrl} setYoutubeUrl={setYoutubeUrl}
                        audioOnly={audioOnly} setAudioOnly={setAudioOnly}
                        uploadLocalMedia={uploadLocalMedia} downloadYouTube={downloadYouTube}
                        working={working}
                      />
                      {existingMedia.length > 0 && (
                        <PendingQueue items={existingMedia} onUse={useExistingMedia} onDelete={deleteExistingMedia} working={working} />
                      )}
                    </>
                  )}

                  {sourceType === "document" && (
                    <DocumentImporter
                      documentFile={documentFile} setDocumentFile={setDocumentFile}
                      translateDoc={translateDoc} setTranslateDoc={setTranslateDoc}
                      importDocument={importDocument} working={working}
                    />
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Step 2: Transcribir ── */}
          {wizardStep === 2 && (
            <div className="grid gap-5 lg:grid-cols-2">
              <article className="card p-5">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
                  Medio cargado
                </p>
                <MediaPlayer asset={asset} bilingual={false} videoRef={videoRef} />
                {asset?.source_name && (
                  <div className="mt-4 rounded-xl border border-stone-100 bg-stone-50 px-4 py-3">
                    <p className="truncate text-sm font-semibold text-stone-800">{cleanName(asset.source_name)}</p>
                    <p className="mt-0.5 text-xs text-stone-400">{kindLabel(asset.media_kind)}</p>
                  </div>
                )}
              </article>
              <AsrControls
                asset={asset} models={models}
                selectedAsr={selectedAsr} setSelectedAsr={setSelectedAsr}
                language={language} setLanguage={setLanguage}
                translateMedia={translateMedia} setTranslateMedia={setTranslateMedia}
                transcribeAsset={transcribeAsset}
                working={working}
              />
            </div>
          )}

          {/* ── Step 3: Revisar ── */}
          {wizardStep === 3 && (
            <div className="space-y-4">
              <section className="grid gap-4 2xl:grid-cols-2">
                <article className="card p-5">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Vista previa</p>
                    {asset?.last_asr_key && (
                      <span className="rounded-lg border border-stone-100 bg-stone-50 px-3 py-1 text-xs text-stone-500">
                        ASR: {asrLabel(models, asset.last_asr_key)}
                      </span>
                    )}
                  </div>
                  <MediaPlayer asset={asset} bilingual={hasPreview} videoRef={videoRef} />
                  {!hasPreview && asset?.transcript_text && (
                    <button
                      onClick={previewTranslation}
                      disabled={working}
                      className="btn btn-amber mt-3 w-full py-2.5 text-sm"
                    >
                      {working ? "Generando..." : "Generar vista previa bilingüe"}
                    </button>
                  )}
                </article>
                <SegmentEditor
                  segments={editedSegments} setSegments={setEditedSegments}
                  working={working} onApply={applyCorrections} onSave={null}
                  videoRef={videoRef}
                />
              </section>

              {/* Nav bar */}
              <div className="flex items-center justify-between rounded-xl border border-stone-100 bg-white px-6 py-4 shadow-sm">
                <button onClick={() => setWizardStep(2)} className="btn btn-ghost px-4 py-2.5 text-sm">
                  ← Retranscribir
                </button>
                <button onClick={() => setWizardStep(4)} className="btn btn-primary px-6 py-2.5 text-sm">
                  Continuar →
                </button>
              </div>
            </div>
          )}

          {/* ── Step 4: Guardar ── */}
          {wizardStep === 4 && (
            <div className="mx-auto max-w-xl space-y-5">
              {/* Summary */}
              <div className="card p-6">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-green-600">
                  Listo para guardar
                </p>
                <h3 className="mt-2 text-2xl font-bold text-stone-900">
                  {cleanName(asset?.source_name) || "Contenido"}
                </h3>
                <p className="mt-2 text-sm text-stone-500">
                  {editedSegments.length} segmento{editedSegments.length !== 1 ? "s" : ""}
                  {" · "}{kindLabel(asset?.media_kind)}
                  {hasPreview ? " · Vista bilingüe lista" : ""}
                </p>
              </div>

              {/* Options */}
              <div className="card p-6">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Opciones al guardar</p>
                <label className="mt-4 flex items-center gap-3 text-sm text-stone-600">
                  <input
                    type="checkbox"
                    checked={translateMedia}
                    onChange={() => setTranslateMedia((v) => !v)}
                    className="accent-blue-600"
                  />
                  Incluir traducción al español en biblioteca
                </label>
              </div>

              <button
                onClick={saveTranscription}
                disabled={working}
                className="btn btn-primary w-full py-4 text-base font-semibold"
              >
                {working ? "Guardando..." : "Guardar en biblioteca"}
              </button>
              <button
                onClick={() => setWizardStep(3)}
                className="btn btn-ghost w-full py-2.5 text-sm"
              >
                ← Volver a revisar
              </button>
            </div>
          )}

        </div>
      )}
    </div>
  )
}
