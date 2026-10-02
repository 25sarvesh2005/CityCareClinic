/**
 * Production Client Error Telemetry Reporter
 */

export type ClientErrorOptions = {
  mechanism?: "manual" | "onerror" | "unhandledrejection" | "react_error_boundary";
  handled?: boolean;
  severity?: "error" | "warning" | "info";
};

export function reportClientError(
  error: unknown,
  context: Record<string, unknown> = {},
  options?: ClientErrorOptions,
) {
  if (typeof window === "undefined") return;

  const message =
    error instanceof Response
      ? `Response ${error.status}${error.url ? ` at ${error.url}` : ""}`
      : error instanceof Error
        ? error.message
        : String(error);
  const stack = error instanceof Error ? error.stack : undefined;

  // Log in structured format for client telemetry / observability pipelines
  console.error("[ClientError]", {
    message,
    stack,
    route: window.location.pathname,
    context,
    options,
  });
}
