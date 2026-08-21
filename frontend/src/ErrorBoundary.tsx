// A crash in one panel must never blank the whole application.
//
// Why this exists: a persisted validation report with no `checks` array made
// ValidationPanel throw, React unmounted the tree, and the operator saw a
// FULLY BLACK SCREEN with no message and nothing to act on. On a tool whose
// entire purpose is honest reporting, silently rendering nothing is the
// worst possible failure mode — worse than an ugly error, because it looks
// like the app simply does not work.
//
// Now a failure shows what broke, where, and what to do about it.

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  /** Shown in the message so the operator knows which panel failed. */
  label: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
  stack: string | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, stack: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the real trace in the console for a bug report.
    console.error(`[${this.props.label}] crashed`, error, info.componentStack);
    this.setState({ stack: info.componentStack ?? null });
  }

  render() {
    const { error, stack } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="panel error-panel">
        <h2>
          {this.props.label} <span className="badge badge-fail">CRASHED</span>
        </h2>
        <p>
          This panel failed to render. The rest of the application is still
          working — switch tabs or rebuild.
        </p>
        <pre className="error-detail">
          {error.name}: {error.message}
        </pre>
        {stack && (
          <details>
            <summary>component stack</summary>
            <pre className="error-detail">{stack.trim()}</pre>
          </details>
        )}
        <p className="hint">
          If this persists, run{" "}
          <code>docker compose logs backend</code> and report the message
          above — it is the real error, not a summary.
        </p>
        <button className="rebuild" onClick={() => this.setState({ error: null, stack: null })}>
          Try again
        </button>
      </div>
    );
  }
}
