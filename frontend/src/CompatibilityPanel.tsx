import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Cpu, Monitor, Repeat2, Volume2 } from 'lucide-react'

type DeviceProfile = {
  id: string
  name: string
  family: string
  description: string
  caveats: string[]
  supported_hdr_formats: string[]
  supported_dolby_vision_profiles: string[]
}

type CompatibilityOutcome = 'direct_play' | 'remux' | 'audio_transcode' | 'video_transcode' | 'unsupported' | 'unknown'

type CompatibilitySummary = {
  device: DeviceProfile
  total_files: number
  direct_play: number
  remux: number
  audio_transcode: number
  video_transcode: number
  unsupported: number
  unknown: number
  direct_play_percent: number
  issue_counts: Record<string, number>
}

type CompatibilityFile = {
  file_id: string
  relative_path: string
  title: string
  year?: number
  outcome: CompatibilityOutcome
  selected_container?: string
  selected_video_codec?: string
  selected_hdr_format?: string
  selected_dolby_vision_profile?: string
  selected_audio_codec?: string
  reasons: { code: string; message: string; severity: string }[]
}

type CompatibilityFileList = {
  total_matching: number
  files: CompatibilityFile[]
}

async function request<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error((await response.text()) || response.statusText)
  return response.json()
}

const outcomeLabels: Record<CompatibilityOutcome, string> = {
  direct_play: 'Direct Play',
  remux: 'Remux',
  audio_transcode: 'Audio transcode',
  video_transcode: 'Video transcode',
  unsupported: 'Unsupported',
  unknown: 'Unknown',
}

const issueLabels: Record<string, string> = {
  unsupported_video_codec: 'Unsupported video codec',
  resolution_exceeds_profile: 'Resolution exceeds device profile',
  bit_depth_exceeds_profile: 'Bit depth exceeds device profile',
  unsupported_hdr_format: 'Unsupported HDR format',
  unsupported_dolby_vision_profile: 'Unsupported Dolby Vision profile',
  unknown_dolby_vision_profile: 'Unknown Dolby Vision profile',
  unknown_hdr_metadata: 'Unknown HDR metadata',
  unsupported_audio_codec: 'Audio decode or transcode required',
  container_requires_remux: 'Container remux required',
  subtitle_requires_burn_in: 'Subtitle burn-in may be required',
  missing_video_stream: 'No video stream detected',
  file_not_fully_scanned: 'File metadata incomplete',
}

export default function CompatibilityPanel({ libraryId }: { libraryId: string }) {
  const [deviceId, setDeviceId] = useState('nvidia-shield-tv-pro-2019')
  const [outcome, setOutcome] = useState<CompatibilityOutcome | ''>('')

  const devices = useQuery({
    queryKey: ['compatibility-devices'],
    queryFn: () => request<DeviceProfile[]>('/api/v1/compatibility/devices'),
  })

  useEffect(() => {
    if (devices.data?.length && !devices.data.some((device) => device.id === deviceId)) {
      setDeviceId(devices.data[0].id)
    }
  }, [devices.data, deviceId])

  const scope = libraryId ? `&library_id=${encodeURIComponent(libraryId)}` : ''
  const summary = useQuery({
    queryKey: ['compatibility-summary', deviceId, libraryId],
    queryFn: () => request<CompatibilitySummary>(`/api/v1/compatibility/summary?device_id=${encodeURIComponent(deviceId)}${scope}`),
    enabled: Boolean(deviceId),
  })
  const files = useQuery({
    queryKey: ['compatibility-files', deviceId, libraryId, outcome],
    queryFn: () => request<CompatibilityFileList>(`/api/v1/compatibility/files?device_id=${encodeURIComponent(deviceId)}${scope}${outcome ? `&outcome=${outcome}` : ''}&limit=100`),
    enabled: Boolean(deviceId),
  })

  const selectedDevice = devices.data?.find((device) => device.id === deviceId)
  const topIssues = Object.entries(summary.data?.issue_counts || {}).slice(0, 6)

  return <section className="compatibility-panel">
    <div className="compatibility-head">
      <div>
        <p className="eyebrow">Hardware compatibility</p>
        <h2>Will this library Direct Play?</h2>
        <p>Compare scanned media against a conservative playback-device profile.</p>
      </div>
      <label>
        Playback device
        <select value={deviceId} onChange={(event) => { setDeviceId(event.target.value); setOutcome('') }}>
          {devices.data?.map((device) => <option key={device.id} value={device.id}>{device.name}</option>)}
        </select>
      </label>
    </div>

    {summary.isError && <div className="compatibility-error"><AlertTriangle size={18}/> Compatibility analysis failed: {(summary.error as Error).message}</div>}

    <div className="compatibility-overview">
      <div className="compatibility-score">
        <Monitor size={28}/>
        <strong>{summary.data?.direct_play_percent ?? 0}%</strong>
        <span>Direct Play</span>
        <small>{summary.data?.direct_play ?? 0} of {summary.data?.total_files ?? 0} files</small>
      </div>
      <OutcomeButton icon={<CheckCircle2/>} label="Direct Play" count={summary.data?.direct_play ?? 0} active={outcome === 'direct_play'} onClick={() => setOutcome(outcome === 'direct_play' ? '' : 'direct_play')}/>
      <OutcomeButton icon={<Repeat2/>} label="Remux" count={summary.data?.remux ?? 0} active={outcome === 'remux'} onClick={() => setOutcome(outcome === 'remux' ? '' : 'remux')}/>
      <OutcomeButton icon={<Volume2/>} label="Audio transcode" count={summary.data?.audio_transcode ?? 0} active={outcome === 'audio_transcode'} onClick={() => setOutcome(outcome === 'audio_transcode' ? '' : 'audio_transcode')}/>
      <OutcomeButton icon={<Cpu/>} label="Video transcode" count={summary.data?.video_transcode ?? 0} active={outcome === 'video_transcode'} onClick={() => setOutcome(outcome === 'video_transcode' ? '' : 'video_transcode')}/>
      <OutcomeButton icon={<AlertTriangle/>} label="Unknown / unsupported" count={(summary.data?.unknown ?? 0) + (summary.data?.unsupported ?? 0)} active={outcome === 'unknown'} onClick={() => setOutcome(outcome === 'unknown' ? '' : 'unknown')}/>
    </div>

    <div className="compatibility-details">
      <div className="device-notes">
        <h3>{selectedDevice?.name || 'Device profile'}</h3>
        <p>{selectedDevice?.description}</p>
        <div className="capability-tags">
          {selectedDevice?.supported_hdr_formats.map((format) => <span key={format}>{format.replaceAll('_', ' ')}</span>)}
          {selectedDevice?.supported_dolby_vision_profiles.map((profile) => <span key={profile}>DV P{profile}</span>)}
        </div>
        {selectedDevice?.caveats.map((caveat) => <small key={caveat}>• {caveat}</small>)}
      </div>
      <div className="compatibility-issues">
        <h3>Most common issues</h3>
        {topIssues.length ? topIssues.map(([code, count]) => <div key={code}><span>{issueLabels[code] || code.replaceAll('_', ' ')}</span><strong>{count}</strong></div>) : <p>No compatibility issues found in this scope.</p>}
      </div>
    </div>

    <div className="compatibility-files">
      <div className="compatibility-files-head">
        <div><h3>{outcome ? outcomeLabels[outcome] : 'Compatibility results'}</h3><p>{files.data?.total_matching ?? 0} matching files · showing the first 100</p></div>
        {outcome && <button onClick={() => setOutcome('')}>Clear filter</button>}
      </div>
      <div className="table-wrap"><table><thead><tr><th>Title</th><th>Outcome</th><th>Video</th><th>HDR</th><th>Audio</th><th>Reason</th></tr></thead><tbody>
        {files.data?.files.map((file) => <tr key={file.file_id}>
          <td><strong>{file.title}</strong><small>{file.year || ''} · {file.relative_path}</small></td>
          <td><span className={`compatibility-badge ${file.outcome}`}>{outcomeLabels[file.outcome]}</span></td>
          <td>{file.selected_video_codec?.toUpperCase() || '—'}<small>{file.selected_container?.toUpperCase() || ''}</small></td>
          <td>{file.selected_hdr_format?.replaceAll('_', ' ') || '—'}<small>{file.selected_dolby_vision_profile ? `Profile ${file.selected_dolby_vision_profile}` : ''}</small></td>
          <td>{file.selected_audio_codec?.toUpperCase() || '—'}</td>
          <td>{file.reasons[0]?.message || 'Compatible'}</td>
        </tr>)}
      </tbody></table></div>
    </div>
  </section>
}

function OutcomeButton({ icon, label, count, active, onClick }: { icon: React.ReactNode; label: string; count: number; active: boolean; onClick: () => void }) {
  return <button className={`compatibility-outcome ${active ? 'active' : ''}`} onClick={onClick}><span>{icon}</span><strong>{count}</strong><small>{label}</small></button>
}
