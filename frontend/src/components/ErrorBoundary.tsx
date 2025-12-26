import { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] Error capturado:', error)
    console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  handleGoHome = () => {
    this.setState({ hasError: false, error: null })
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[50vh] items-center justify-center px-4">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
              <AlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" />
            </div>

            <h1 className="mb-2 text-2xl font-bold text-gray-900 dark:text-white">
              Algo salio mal
            </h1>

            <p className="mb-6 text-gray-600 dark:text-gray-400">
              Ocurrio un error inesperado. Puedes intentar recargar la pagina o volver al inicio.
            </p>

            {import.meta.env.DEV && this.state.error && (
              <pre className="mb-6 overflow-auto rounded-lg bg-gray-100 p-4 text-left text-xs text-red-600 dark:bg-gray-800 dark:text-red-400">
                {this.state.error.message}
              </pre>
            )}

            <div className="flex justify-center gap-3">
              <button
                onClick={this.handleReset}
                className="btn-secondary inline-flex items-center gap-2"
              >
                <RefreshCw className="h-4 w-4" />
                Reintentar
              </button>

              <button
                onClick={this.handleGoHome}
                className="btn-primary inline-flex items-center gap-2"
              >
                <Home className="h-4 w-4" />
                Ir al inicio
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
