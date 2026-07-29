import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, CheckCircle2, Clock3, Eye, RefreshCw, ScanSearch, TriangleAlert } from 'lucide-react'

type WatcherActivity = {
  timestamp: string
  action: string
  message: string
  library_id?: string
  library_name?: string
  relative_path?: string
}

type WatcherLibrary = {
  library_id: string
  library_name: string
  root_path: string
  state: 'watching' | 'reconciliation_only' | 'disabled' | 'error'
  pending_files: number
  last_event_at?: string
  last_reconcile_at?: string
  last_error?: string
}

type WatcherStatus = {
  enabled: boolean
  running: boolean
  stability_seconds: number
  reconcile_minutes: number
  pending_files: number
  active_library_id?: string
  active_relative_path?: string
  libraries: WatcherLibrary[]
  recent_activity: WatcherActivity[]
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) throw new Error((await response.text()) || response.statusText)
  return response.json()
}

const age = (value?: string) => {
  if (!value) return 'Never'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

const stateLabel = (state: WatcherLibrary['state']) => state === 'reconciliation_only' ? 'Reconciliation only' : state[0].toUpperCase() + state.slice(1)

export default function AutoScanPanel() {
  const queryClient = useQueryClient()
  const lastCompletedRef = useRef('')
  const status = useQuery({
    queryKey: ['watcher-status'],
    queryFn: () => api<WatcherStatus>('/api/v1/watcher/status'),
    refetchInterval: 3000,
  })
  const reconcile = useMutation({
    mutationFn: () => api<{ accepted: boolean; message: string }>('/api/v1/watcher/reconcile', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watcher-status'] }),
  })

  const data = status.data
  const activeLibrary = data?.libraries.find((library) => library.library_id === data.active_library_id)
  const latestCompleted = data?.recent_activity.find((entry) => entry.action === 'completed')

  useEffect(() => {
    if (!latestCompleted || latestCompleted.timestamp === lastCompletedRef.current) return
    lastCompletedRef.current = latestCompleted.timestamp
    queryClient.invalidateQueries({ queryKey: ['files'] })
    queryClient.invalidateQueries({ queryKey: ['summary'] })
    queryClient.invalidateQueries({ queryKey: ['compatibility-summary'] })
    queryClient.invalidateQueries({ queryKey: ['compatibility-files'] })
  }, [latestCompleted, queryClient])

  return <section className="auto-scan-card">
    <div className="auto-scan-head">
      <div>
        <p className="eyebrow">Automatic scanning</p>
        <h2><Eye size={22}/> Library watcher</h2>
        <p>Detects new, changed, renamed, and removed media without rescanning the full library.</p>
      </div>
      <div className="auto-scan-actions">
        <span className={`watcher-pill ${data?.running ? 'running' : 'stopped'}`}>
          {data?.running ? <CheckCircle2 size={15}/> : <TriangleAlert size={15}/>} {data?.running ? 'Watching' : data?.enabled ? 'Stopped' : 'Disabled'}
        </span>
        <button disabled={reconcile.isPending || !data?.enabled} onClick={() => reconcile.mutate()}>
          <RefreshCw size={15} className={reconcile.isPending ? 'spin' : ''}/> {reconcile.isPending ? 'Reconciling…' : 'Reconcile now'}
        </button>
      </div>
    </div>

    <div className="auto-scan-metrics">
      <article><ScanSearch/><div><small>Pending files</small><strong>{data?.pending_files ?? 0}</strong></div></article>
      <article><Clock3/><div><small>Stability delay</small><strong>{data ? `${data.stability_seconds}s` : '—'}</strong></div></article>
      <article><RefreshCw/><div><small>Safety check</small><strong>{data ? `${data.reconcile_minutes} min` : '—'}</strong></div></article>
      <article><Activity/><div><small>Currently scanning</small><strong title={data?.active_relative_path}>{data?.active_relative_path ? `${activeLibrary?.library_name || 'Library'} · ${data.active_relative_path.split('/').pop()}` : 'Idle'}</strong></div></article>
    </div>

    {status.isError && <p className="watcher-error">Could not load automatic scanning status.</p>}

    <div className="watcher-libraries">
      {(data?.libraries || []).map((library) => <article key={library.library_id} className={`watcher-library ${library.state}`}>
        <div>
          <strong>{library.library_name}</strong>
          <small title={library.root_path}>{library.root_path}</small>
        </div>
        <span>{stateLabel(library.state)}</span>
        <dl>
          <div><dt>Pending</dt><dd>{library.pending_files}</dd></div>
          <div><dt>Last event</dt><dd>{age(library.last_event_at)}</dd></div>
          <div><dt>Last check</dt><dd>{age(library.last_reconcile_at)}</dd></div>
        </dl>
        {library.last_error && <p>{library.last_error}</p>}
      </article>)}
    </div>

    {data?.recent_activity?.length ? <details className="watcher-activity">
      <summary>Recent automatic scan activity</summary>
      <div>{data.recent_activity.slice(0, 12).map((entry, index) => <p key={`${entry.timestamp}-${index}`}><time>{new Date(entry.timestamp).toLocaleString()}</time><span className={`activity-action ${entry.action}`}>{entry.action}</span><span>{entry.message}</span></p>)}</div>
    </details> : null}
  </section>
}
