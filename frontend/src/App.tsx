import { Routes, Route } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Home from './pages/Home'
import Article from './pages/Article'
import LeyIndex from './pages/LeyIndex'
import DivisionView from './pages/DivisionView'
import Header from './components/Header'
import ErrorBoundary from './components/ErrorBoundary'

function App() {
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('darkMode') === 'true' ||
        (!localStorage.getItem('darkMode') && window.matchMedia('(prefers-color-scheme: dark)').matches)
    }
    return false
  })

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('darkMode', String(darkMode))
  }, [darkMode])

  return (
    <div className="min-h-screen">
      <Header darkMode={darkMode} onToggleDarkMode={() => setDarkMode(!darkMode)} />
      <main className="container mx-auto px-4 py-8">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/:ley/articulo/*" element={<Article />} />
            <Route path="/:ley/regla/*" element={<Article />} />
            <Route path="/:ley/ficha/*" element={<Article />} />
            <Route path="/:ley/criterio/*" element={<Article />} />
            <Route path="/:ley/division/:id" element={<DivisionView />} />
            <Route path="/:ley" element={<LeyIndex />} />
            <Route path="/articulo/:id" element={<Article />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
