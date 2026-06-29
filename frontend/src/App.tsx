import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard    from './pages/Dashboard'
import ReviewDetail from './pages/ReviewDetail'
import AgentTrace   from './pages/AgentTrace'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/"                    element={<Dashboard />} />
          <Route path="/review/:id"          element={<ReviewDetail />} />
          <Route path="/review/:id/trace"    element={<AgentTrace />} />
          {/* Fallback */}
          <Route path="*"                    element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
