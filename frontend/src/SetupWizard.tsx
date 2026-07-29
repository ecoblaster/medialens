import { useState } from 'react'
import { CheckCircle2, Film, FolderOpen, Sparkles, Tv } from 'lucide-react'

type Library = { id: string; name: string; media_kind: string }
type LibraryDraft = { key: 'movies' | 'tv'; name: string; media_kind: 'movies' | 'tv'; root_path: string; enabled: boolean }

type Props = {
  onComplete: (libraries: Library[]) => Promise<void> | void
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) {
    const raw = await response.text()
    try {
      const parsed = JSON.parse(raw)
      throw new Error(parsed?.detail?.message || parsed?.message || response.statusText)
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(raw || response.statusText)
      throw error
    }
  }
  return response.json()
}

const defaults: LibraryDraft[] = [
  { key: 'movies', name: 'Movies', media_kind: 'movies', root_path: '/media/movies', enabled: true },
  { key: 'tv', name: 'TV Shows', media_kind: 'tv', root_path: '/media/tv', enabled: true },
]

export default function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [libraries, setLibraries] = useState(defaults)
  const [startScans, setStartScans] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const selected = libraries.filter((library) => library.enabled)
  const update = (key: LibraryDraft['key'], field: 'name' | 'root_path' | 'enabled', value: string | boolean) => {
    setLibraries((current) => current.map((library) => library.key === key ? { ...library, [field]: value } : library))
  }

  const finish = async () => {
    setSaving(true)
    setError('')
    const created: Library[] = []
    try {
      for (const library of selected) {
        const result = await request<Library>('/api/v1/libraries', {
          method: 'POST',
          body: JSON.stringify({
            name: library.name.trim(),
            media_kind: library.media_kind,
            source_type: 'filesystem',
            root_path: library.root_path.trim(),
            external_id: null,
            enabled: true,
          }),
        })
        created.push(result)
      }

      if (startScans) {
        for (const library of created) {
          await request('/api/v1/scans', {
            method: 'POST',
            body: JSON.stringify({ library_id: library.id, mode: 'full', force: false }),
          })
        }
      }
      await onComplete(created)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Setup could not be completed.')
    } finally {
      setSaving(false)
    }
  }

  return <div className="setup-backdrop">
    <section className="setup-card" aria-modal="true" role="dialog" aria-labelledby="setup-title">
      <div className="setup-progress"><span className={step >= 0 ? 'active' : ''}>1</span><i/><span className={step >= 1 ? 'active' : ''}>2</span><i/><span className={step >= 2 ? 'active' : ''}>3</span></div>

      {step === 0 && <>
        <div className="setup-hero"><span><Sparkles size={30}/></span><p className="eyebrow">MediaLens 1.1</p><h1 id="setup-title">Welcome to MediaLens</h1><p>Add the media folders already mounted in your container. MediaLens only reads these folders and stores its analysis in <code>/data</code>.</p></div>
        <div className="setup-notes"><div><FolderOpen/><span><strong>Container paths</strong>Use paths such as <code>/media/movies</code>, not the original Unraid host path.</span></div><div><CheckCircle2/><span><strong>Read-only analysis</strong>Your movie and TV files are never modified.</span></div></div>
        <div className="setup-actions"><a href="/docs" target="_blank" rel="noreferrer">Open API docs</a><button className="primary" onClick={() => setStep(1)}>Get started</button></div>
      </>}

      {step === 1 && <>
        <div className="setup-heading"><p className="eyebrow">Step 2 of 3</p><h1 id="setup-title">Choose your libraries</h1><p>The usual Docker and Unraid container paths are filled in for you.</p></div>
        <div className="setup-libraries">
          {libraries.map((library) => <article className={library.enabled ? 'selected' : ''} key={library.key}>
            <label className="setup-toggle"><input type="checkbox" checked={library.enabled} onChange={(event) => update(library.key, 'enabled', event.target.checked)}/><span>{library.key === 'movies' ? <Film/> : <Tv/>}</span><strong>{library.key === 'movies' ? 'Movie library' : 'TV library'}</strong></label>
            <label>Name<input disabled={!library.enabled} value={library.name} onChange={(event) => update(library.key, 'name', event.target.value)}/></label>
            <label>Container path<input disabled={!library.enabled} value={library.root_path} onChange={(event) => update(library.key, 'root_path', event.target.value)}/></label>
          </article>)}
        </div>
        <div className="setup-actions"><button onClick={() => setStep(0)}>Back</button><button className="primary" disabled={!selected.length || selected.some((library) => !library.name.trim() || !library.root_path.trim())} onClick={() => setStep(2)}>Review setup</button></div>
      </>}

      {step === 2 && <>
        <div className="setup-heading"><p className="eyebrow">Step 3 of 3</p><h1 id="setup-title">Ready to analyze</h1><p>MediaLens will create {selected.length} {selected.length === 1 ? 'library' : 'libraries'} using these container paths.</p></div>
        <div className="setup-review">{selected.map((library) => <div key={library.key}><span>{library.key === 'movies' ? <Film/> : <Tv/>}</span><div><strong>{library.name}</strong><code>{library.root_path}</code></div></div>)}</div>
        <label className="setup-scan"><input type="checkbox" checked={startScans} onChange={(event) => setStartScans(event.target.checked)}/><span><strong>Start full scans now</strong><small>You can follow progress from the dashboard. Libraries are created even when this is disabled.</small></span></label>
        {error && <div className="setup-error">{error}<small>Check that the path exists inside the container and is mounted correctly.</small></div>}
        <div className="setup-actions"><button disabled={saving} onClick={() => setStep(1)}>Back</button><button className="primary" disabled={saving} onClick={finish}>{saving ? 'Creating libraries…' : 'Finish setup'}</button></div>
      </>}
    </section>
  </div>
}
