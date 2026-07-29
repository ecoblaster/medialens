import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, AlertTriangle, CheckCircle2, Film, HardDrive, RefreshCw, Search, Sparkles, Subtitles, Volume2, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AutoScanPanel from './AutoScanPanel'
import CompatibilityPanel from './CompatibilityPanel'

type Library = { id: string; name: string; media_kind: string }
type Summary = { total_files: number; total_size_bytes: number; scan_complete: number; scan_failed: number; hdr10: number; hdr10_plus: number; dolby_vision: number; dolby_vision_profiles: Record<string, number>; atmos: number; dts_x: number; hdr_formats: Record<string, number>; video_codecs: Record<string, number>; audio_formats: Record<string, number>; resolutions: Record<string, number>; library_health: Record<string, number> }
type Stream = Record<string, unknown>
type MediaFile = { id: string; library_id: string; relative_path: string; filename: string; container?: string; size_bytes: number; scan_status: string; last_error?: string; media_item: { title: string; year?: number; item_type: string }; video_streams: Stream[]; audio_streams: Stream[]; subtitle_streams: Stream[] }
type Scan = { id: string; library_id: string; status: string; files_discovered: number; files_analyzed: number; files_skipped: number; files_failed: number; current_relative_path?: string; current_filename?: string; current_stage?: string; current_file_started_at?: string; current_stage_started_at?: string; average_seconds_per_file?: number; estimated_remaining_seconds?: number }
type HealthFilter = '' | 'hdr_metadata_missing' | 'failed_scans' | 'no_subtitles' | 'missing_audio_language'

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) throw new Error((await response.text()) || response.statusText)
  return response.json()
}

const pairs = (value?: Record<string, number>) => Object.entries(value || {}).map(([name, count]) => ({ name, count }))
const bytes = (value: number) => {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4)
  return `${(value / 1024 ** index).toFixed(index > 2 ? 1 : 0)} ${units[index]}`
}
const duration = (seconds?: number) => {
  if (seconds == null) return 'Calculating…'
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainingSeconds = total % 60
  return hours ? `${hours}h ${minutes}m` : minutes ? `${minutes}m ${remainingSeconds}s` : `${remainingSeconds}s`
}
const elapsed = (started?: string) => started ? duration((Date.now() - new Date(started).getTime()) / 1000) : '—'
const finishTime = (remaining?: number) => remaining == null ? 'Calculating…' : new Date(Date.now() + remaining * 1000).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })

function App() {
  const queryClient = useQueryClient()
  const [libraryId, setLibraryId] = useState('')
  const [query, setQuery] = useState('')
  const [dvProfile, setDvProfile] = useState('')
  const [hdr10Plus, setHdr10Plus] = useState(false)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('')
  const [selected, setSelected] = useState<MediaFile | null>(null)

  const libraries = useQuery({ queryKey: ['libraries'], queryFn: () => api<Library[]>('/api/v1/libraries') })
  const summary = useQuery({ queryKey: ['summary', libraryId], queryFn: () => api<Summary>(`/api/v1/dashboard/summary${libraryId ? `?library_id=${libraryId}` : ''}`) })
  const params = new URLSearchParams({ limit: '500' })
  if (libraryId) params.set('library_id', libraryId)
  if (query.trim()) params.set('search', query.trim())
  if (dvProfile) params.set('dolby_vision_profile', dvProfile)
  if (hdr10Plus) params.set('has_hdr10_plus', 'true')
  if (healthFilter) params.set('health', healthFilter)
  const files = useQuery({ queryKey: ['files', libraryId, query, dvProfile, hdr10Plus, healthFilter], queryFn: () => api<MediaFile[]>(`/api/v1/files?${params}`) })
  const scans = useQuery({ queryKey: ['scans'], queryFn: () => api<Scan[]>('/api/v1/scans?limit=10'), refetchInterval: 1000 })

  const startScan = useMutation({
    mutationFn: (id: string) => api<Scan>('/api/v1/scans', { method: 'POST', body: JSON.stringify({ library_id: id, mode: 'full', force: false }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scans'] }),
  })
  const cancelScan = useMutation({
    mutationFn: (id: string) => api<Scan>(`/api/v1/scans/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scans'] }),
  })

  const visibleFiles = files.data || []
  const activeScan = scans.data?.find((scan) => ['queued', 'running', 'cancelling'].includes(scan.status))
  const activeLibrary = activeScan ? libraries.data?.find((library) => library.id === activeScan.library_id) : undefined
  const activeLibraryName = activeLibrary?.name || (activeScan ? `Library ${activeScan.library_id.slice(0, 8)}` : '')
  const data = summary.data
  const processed = activeScan ? activeScan.files_analyzed + activeScan.files_skipped + activeScan.files_failed : 0

  return <div className="app-shell">
    <header className="topbar">
      <div><div className="brand"><Sparkles size={20}/> MediaLens <span className="version">0.6.2-dev</span></div><p>Read-only media capability intelligence</p></div>
      <div className="toolbar">
        <select value={libraryId} onChange={(event) => setLibraryId(event.target.value)}><option value="">All libraries</option>{libraries.data?.map((library) => <option key={library.id} value={library.id}>{library.name}</option>)}</select>
        <button className="primary" disabled={!libraryId || Boolean(activeScan) || startScan.isPending} onClick={() => libraryId && startScan.mutate(libraryId)}><RefreshCw size={16}/> Scan library</button>
        <a className="ghost" href="/docs" target="_blank">API docs</a>
      </div>
    </header>

    {activeScan && <section className="scan-strip">
      <Activity size={18}/>
      <div className="scan-main">
        <strong>{activeLibraryName} library scan {activeScan.status}</strong>
        <span>{processed} / {activeScan.files_discovered || '…'} processed · {activeScan.files_failed} failed</span>
        <span className="current-file" title={activeScan.current_relative_path}>{activeScan.current_filename || activeScan.current_stage || 'Preparing scan…'}</span>
        <span>{activeScan.current_stage || 'Preparing scan…'} · file elapsed {elapsed(activeScan.current_file_started_at)}</span>
      </div>
      <div className="scan-estimate">
        <span><b>Average</b>{activeScan.average_seconds_per_file != null ? `${activeScan.average_seconds_per_file.toFixed(1)}s/file` : 'Calculating…'}</span>
        <span><b>Remaining</b>{duration(activeScan.estimated_remaining_seconds)}</span>
        <span><b>Estimated finish</b>{finishTime(activeScan.estimated_remaining_seconds)}</span>
      </div>
      <progress value={processed} max={activeScan.files_discovered || 1}/>
      <button className="cancel" disabled={activeScan.status === 'cancelling' || cancelScan.isPending} onClick={() => cancelScan.mutate(activeScan.id)}>{activeScan.status === 'cancelling' ? 'Cancelling…' : 'Cancel scan'}</button>
    </section>}

    <main>
      <section className="metrics">
        <Metric icon={<Film/>} label="Media files" value={data?.total_files ?? 0}/>
        <Metric icon={<HardDrive/>} label="Library size" value={bytes(data?.total_size_bytes ?? 0)}/>
        <Metric icon={<BrandLogo src="/brands/dolby-vision.svg"/>} label="Dolby Vision" value={data?.dolby_vision ?? 0}/>
        <Metric icon={<BrandLogo src="/brands/hdr10-plus.svg"/>} label="HDR10+" value={data?.hdr10_plus ?? 0}/>
        <Metric icon={<BrandLogo src="/brands/dolby-atmos.svg"/>} label="Dolby Atmos" value={data?.atmos ?? 0}/>
        <Metric icon={<Activity/>} label="Failed scans" value={data?.scan_failed ?? 0} danger={Boolean(data?.scan_failed)}/>
      </section>

      <section className="health-card">
        <div><p className="eyebrow">Library health</p><h2>Quality checks</h2><p>Click a warning to filter the media browser.</p></div>
        <div className="health-grid">
          <Health icon={<CheckCircle2/>} label="Analyzed" count={data?.library_health?.analyzed ?? 0} active={healthFilter === ''} onClick={() => setHealthFilter('')}/>
          <Health icon={<AlertTriangle/>} label="HDR metadata missing" count={data?.library_health?.hdr_metadata_missing ?? 0} active={healthFilter === 'hdr_metadata_missing'} onClick={() => setHealthFilter('hdr_metadata_missing')}/>
          <Health icon={<Activity/>} label="Failed scans" count={data?.library_health?.failed_scans ?? 0} active={healthFilter === 'failed_scans'} onClick={() => setHealthFilter('failed_scans')}/>
          <Health icon={<Subtitles/>} label="No subtitles" count={data?.library_health?.no_subtitles ?? 0} active={healthFilter === 'no_subtitles'} onClick={() => setHealthFilter('no_subtitles')}/>
          <Health icon={<Volume2/>} label="Audio language missing" count={data?.library_health?.missing_audio_language ?? 0} active={healthFilter === 'missing_audio_language'} onClick={() => setHealthFilter('missing_audio_language')}/>
        </div>
      </section>

      <AutoScanPanel/>
      <CompatibilityPanel libraryId={libraryId}/>

      <section className="charts-grid">
        <ChartCard title="HDR formats"><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={pairs(data?.hdr_formats)} dataKey="count" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>{pairs(data?.hdr_formats).map((_, index) => <Cell key={index} fill={`hsl(${190 + index * 42} 75% 58%)`}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></ChartCard>
        <ChartCard title="Dolby Vision profiles"><ResponsiveContainer width="100%" height={260}><BarChart data={pairs(data?.dolby_vision_profiles)}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" fill="#8b5cf6" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></ChartCard>
        <ChartCard title="Video codecs"><ResponsiveContainer width="100%" height={260}><BarChart data={pairs(data?.video_codecs).slice(0, 8)} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number"/><YAxis type="category" dataKey="name" width={72}/><Tooltip/><Bar dataKey="count" fill="#22d3ee" radius={[0,8,8,0]}/></BarChart></ResponsiveContainer></ChartCard>
        <ChartCard title="Resolutions"><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={pairs(data?.resolutions)} dataKey="count" nameKey="name" outerRadius={96}>{pairs(data?.resolutions).map((_, index) => <Cell key={index} fill={`hsl(${260 + index * 35} 72% 62%)`}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></ChartCard>
      </section>

      <section className="library-panel">
        <div className="panel-head">
          <div><h2>Media browser</h2><p>{visibleFiles.length} visible files{query ? ' · database search active' : ''}{healthFilter ? ' · health filter active' : ''}</p></div>
          <div className="filters">
            <label className="search"><Search size={16}/><input placeholder="Search entire library" value={query} onChange={(event) => setQuery(event.target.value)}/></label>
            <select value={dvProfile} onChange={(event) => setDvProfile(event.target.value)}><option value="">All DV profiles</option><option value="5">Profile 5</option><option value="7">Profile 7</option><option value="8">Profile 8</option></select>
            <label className="check"><input type="checkbox" checked={hdr10Plus} onChange={(event) => setHdr10Plus(event.target.checked)}/> HDR10+</label>
            {healthFilter && <button onClick={() => setHealthFilter('')}>Clear health filter</button>}
          </div>
        </div>
        <div className="table-wrap"><table><thead><tr><th>Title</th><th>Video</th><th>HDR</th><th>Audio</th><th>Size</th><th>Status</th></tr></thead><tbody>
          {visibleFiles.map((file) => {
            const video = file.video_streams[0] as any
            const audio = file.audio_streams[0] as any
            const dolbyVision = video?.dolby_vision
            const inferredSdr = video?.base_hdr_format === 'SDR' || (!video?.color_transfer && video?.bit_depth && video.bit_depth <= 8)
            const hdr = video?.has_dolby_vision ? `DV P${dolbyVision?.profile || '?'}` : video?.has_hdr10_plus ? 'HDR10+' : inferredSdr ? 'SDR' : video?.base_hdr_format === 'UNKNOWN' ? 'Metadata missing' : video?.base_hdr_format || 'Unknown'
            return <tr key={file.id} onClick={() => setSelected(file)}>
              <td><strong>{file.media_item.title}</strong><small>{file.media_item.year || ''} · {file.filename}</small></td>
              <td>{video?.codec_name?.toUpperCase() || '—'}<small>{video?.width ? `${video.width}×${video.height}` : ''}</small></td>
              <td><span className="badge">{hdr}</span></td>
              <td>{audio?.immersive_format === 'DOLBY_ATMOS' ? 'Dolby Atmos' : audio?.immersive_format === 'DTS_X' ? 'DTS:X' : audio?.codec_name?.toUpperCase() || '—'}<small>{audio?.channels ? `${audio.channels} channels` : ''}</small></td>
              <td>{bytes(file.size_bytes)}</td>
              <td><span className={`status ${file.scan_status}`}>{file.scan_status}</span></td>
            </tr>
          })}
        </tbody></table></div>
      </section>
    </main>

    {selected && <div className="drawer-backdrop" onClick={() => setSelected(null)}><aside className="drawer" onClick={(event) => event.stopPropagation()}><button className="close" onClick={() => setSelected(null)}><X/></button><p className="eyebrow">{selected.media_item.item_type}</p><h2>{selected.media_item.title}</h2><p>{selected.relative_path}</p><Detail title="File" value={{ container: selected.container, size: bytes(selected.size_bytes), status: selected.scan_status, error: selected.last_error }}/><Detail title="Video streams" value={selected.video_streams}/><Detail title="Audio streams" value={selected.audio_streams}/><Detail title="Subtitles" value={selected.subtitle_streams}/></aside></div>}
  </div>
}

function BrandLogo({ src }: { src: string }) {
  return <img className="brand-logo" src={src} alt="" aria-hidden="true"/>
}

function Metric({ icon, label, value, danger }: { icon: React.ReactNode; label: string; value: string | number; danger?: boolean }) {
  return <article className={`metric ${danger ? 'danger' : ''}`}><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></article>
}

function Health({ icon, label, count, active, onClick }: { icon: React.ReactNode; label: string; count: number; active: boolean; onClick: () => void }) {
  return <button className={`health-item ${active ? 'active' : ''}`} onClick={onClick}><span>{icon}</span><strong>{count}</strong><small>{label}</small></button>
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <article className="chart-card"><h3>{title}</h3>{children}</article>
}

function Detail({ title, value }: { title: string; value: unknown }) {
  return <section className="detail"><h3>{title}</h3><pre>{JSON.stringify(value, null, 2)}</pre></section>
}

export default App
