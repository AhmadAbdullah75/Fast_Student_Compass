export type Reference = {
  title: string;
  section: string;
  pdf_page: number;
  printed_label: string;
  campus: string;
  degree: string;
  url?: string;
  collection_date?: string;
};
export type Citation = {
  id: string;
  chunk_id: string;
  excerpt: string;
  references: Reference[];
};
export type Turn = {
  id: string;
  conversation_id: string;
  question: string;
  answer: string | null;
  status: "pending" | "failed" | "completed";
  error: string | null;
  citations: Citation[];
  created: string;
  completed: string | null;
  running: boolean;
  model?: string;
  dataset_version?: string;
  latency?: number;
  diagnostics?: Record<string, unknown>;
  client_request_id?: string;
  unsaved?: boolean;
};
export type Conversation = {
  id: string;
  title: string;
  created: string;
  updated: string;
  turns?: Turn[];
};
export type Health = {
  status: string;
  ready: boolean;
  dataset_version: string | null;
  chat_model: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}
function validTurn(t: Turn) {
  return (
    !!t &&
    typeof t.id === "string" &&
    typeof t.question === "string" &&
    typeof t.created === "string" &&
    typeof t.running === "boolean" &&
    (t.error === null || typeof t.error === "string") &&
    (t.answer === null || typeof t.answer === "string") &&
    (t.completed === null || typeof t.completed === "string") &&
    ["pending", "failed", "completed"].includes(t.status) &&
    (t.status !== "completed" || typeof t.answer === "string") &&
    Array.isArray(t.citations) &&
    t.citations.every(
      (c) =>
        typeof c.id === "string" &&
        typeof c.excerpt === "string" &&
        Array.isArray(c.references) &&
        c.references.every(
          (r) =>
            typeof r.title === "string" &&
            typeof r.section === "string" &&
            typeof r.pdf_page === "number" &&
            typeof r.printed_label === "string" &&
            typeof r.campus === "string" &&
            typeof r.degree === "string",
        ),
    )
  );
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("/api" + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: options.signal ?? controller.signal,
    });
    if (response.status === 204) return undefined as T;
    let value: unknown;
    try {
      value = await response.json();
    } catch {
      throw new ApiError(
        "The server returned an unexpected response. Please reconnect.",
        response.status,
      );
    }
    if (!response.ok) {
      const detail = (value as { detail?: unknown })?.detail;
      throw new ApiError(
        typeof detail === "string"
          ? detail
          : "Please check your input and try again.",
        response.status,
      );
    }
    // Reject malformed success payloads instead of crashing or losing a question.
    const valid =
      path === "/conversations" && options.method !== "POST"
        ? Array.isArray(value) &&
          value.every(
            (c) =>
              typeof c?.id === "string" &&
              typeof c?.title === "string" &&
              typeof c?.updated === "string",
          )
        : path === "/health"
          ? typeof (value as Health)?.ready === "boolean"
          : path.endsWith("/turns") || path.endsWith("/retry")
            ? validTurn(value as Turn)
            : !!value &&
              typeof value === "object" &&
              typeof (value as { id?: unknown }).id === "string" &&
              typeof (value as { title?: unknown }).title === "string";
    if (!valid)
      throw new ApiError(
        "The server returned an unexpected response. Please reconnect.",
        response.status,
      );
    if (path.startsWith("/conversations/") && !options.method) {
      const turns = (value as Conversation).turns;
      if (!Array.isArray(turns) || !turns.every(validTurn))
        throw new ApiError(
          "The conversation response was incomplete. Please reconnect.",
        );
    }
    return value as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "Connection interrupted. Your message is still here. Reconnect to continue.",
    );
  } finally {
    clearTimeout(timeout);
  }
}
