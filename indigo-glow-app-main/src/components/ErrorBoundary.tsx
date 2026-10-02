import React, { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircle, RefreshCw, RotateCcw } from "lucide-react";
import { reportClientError } from "../lib/error-reporting";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    reportClientError(
      error,
      { componentStack: errorInfo.componentStack },
      {
        mechanism: "react_error_boundary",
        handled: false,
        severity: "error",
      },
    );
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public handleReload = () => {
    window.location.reload();
  };

  public override render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-[400px] w-full items-center justify-center p-6 bg-background">
          <div className="w-full max-w-md rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center shadow-lg backdrop-blur-md">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h2 className="text-lg font-semibold tracking-tight text-foreground">
              An unexpected error occurred
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              A runtime rendering error was caught safely. You can recover by refreshing or
              navigating to the home view.
            </p>
            {this.state.error?.message && (
              <div className="mt-3 rounded bg-black/40 p-2 text-left font-mono text-xs text-muted-foreground break-all">
                {this.state.error.message}
              </div>
            )}
            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
              >
                <RotateCcw className="h-4 w-4" />
                Try Again
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
