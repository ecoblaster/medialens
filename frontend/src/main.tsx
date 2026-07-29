import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import App from './App'
import SetupWizard from './SetupWizard'
import './styles.css'
import './compatibility.css'
import './auto-scan.css'
import './brand-icons.css'
import './setup-wizard.css'

type Library = { id: string; name: string; media_kind: string }

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

async function loadLibraries(): Promise<Library[]> {
  const response = await fetch('/api/v1/libraries')
  if (!response.ok) throw new Error((await response.text()) || response.statusText)
  return response.json()
}

function Root() {
  const libraries = useQuery({ queryKey: ['libraries'], queryFn: loadLibraries })

  return <>
    <App />
    {libraries.isSuccess && libraries.data.length === 0 && <SetupWizard onComplete={async () => {
      await queryClient.invalidateQueries({ queryKey: ['libraries'] })
      await queryClient.invalidateQueries({ queryKey: ['scans'] })
      await queryClient.invalidateQueries({ queryKey: ['summary'] })
      await queryClient.invalidateQueries({ queryKey: ['files'] })
    }}/>} 
  </>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Root />
    </QueryClientProvider>
  </React.StrictMode>,
)
