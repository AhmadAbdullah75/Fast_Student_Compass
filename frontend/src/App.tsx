import {
  Component,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  Compass,
  Copy,
  ExternalLink,
  FileText,
  GraduationCap,
  HeartHandshake,
  Info,
  Menu,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  X,
  Pencil,
  RefreshCw,
} from "lucide-react";
import { createPortal } from "react-dom";
import {
  api,
  type Citation,
  type Conversation,
  type Health,
  type Turn,
} from "./api";
const AnswerMarkdown = lazy(() => import("./AnswerMarkdown"));
class FormattingBoundary extends Component<
  { children: ReactNode; answer: string },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="markdown">
        <p style={{ whiteSpace: "pre-wrap" }}>{this.props.answer}</p>
        <small>
          Plain-text view · rich formatting could not load. Your saved answer
          and sources are available.
        </small>
      </div>
    ) : (
      this.props.children
    );
  }
}

const uuid = () => crypto.randomUUID().replaceAll("-", "");
const clock = (value: string | null) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
const examples = [
  {
    icon: GraduationCap,
    label: "Academic guidance",
    question: "How do I withdraw from a course?",
    detail: "Understand the rules. Know your next step.",
    color: "sage",
  },
  {
    icon: HeartHandshake,
    label: "Financial assistance",
    question: "What conditions apply to a merit scholarship?",
    detail: "Find support for your education.",
    color: "peach",
  },
  {
    icon: BookOpen,
    label: "Life at CFD",
    question: "What hostel facilities are available at CFD?",
    detail: "Get to know your campus better.",
    color: "blue",
  },
];

function Sources({
  citations,
  turnId,
}: {
  citations: Citation[];
  turnId: string;
}) {
  return (
    <details className="sources">
      <summary>
        <BookOpen size={15} />
        <span>Sources</span>
        <span className="source-count">{citations.length}</span>
        <ChevronDown size={14} />
      </summary>
      <div className="source-list">
        {citations.map((c) => (
          <details
            className="source-card"
            key={c.id}
            id={`source-${turnId}-${c.id}`}
          >
            <summary>
              <span className="source-label">{c.id}</span>
              <span>
                <strong>
                  {c.references[0]?.title ?? "Document reference"}
                </strong>
                <small>
                  {[
                    ...new Set(c.references.map((r) => `PDF p. ${r.pdf_page}`)),
                  ].join(" · ")}
                </small>
              </span>
              <ChevronDown size={15} />
            </summary>
            <div className="source-body">
              {c.references.map((r, i) => (
                <div className="reference" key={i}>
                  <strong>{r.section}</strong>
                  <p>
                    PDF page {r.pdf_page} · Printed page {r.printed_label} ·{" "}
                    {r.campus === "all" ? "University-wide" : r.campus} ·{" "}
                    {r.degree}
                  </p>
                  {r.collection_date && (
                    <p>Snapshot collected {r.collection_date}</p>
                  )}
                  {r.url && /^https?:\/\//i.test(r.url) && (
                    <a href={r.url} target="_blank" rel="noopener noreferrer">
                      Open original source <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              ))}
              <span className="excerpt-label">DOCUMENT PASSAGE</span>
              <pre>{c.excerpt}</pre>
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}

function Message({
  turn,
  onRetry,
  onDiscard,
}: {
  turn: Turn;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const pending = turn.status === "pending" && turn.running;
  async function copy() {
    try {
      await navigator.clipboard.writeText(turn.answer ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return (
    <article className="exchange" data-testid="exchange">
      <div className="user-message">
        <div className="user-bubble">{turn.question}</div>
        <time dateTime={turn.created}>You · {clock(turn.created)}</time>
      </div>
      <div className="assistant-message">
        <span className="assistant-avatar">
          <Compass size={19} />
        </span>
        <div className="assistant-content">
          <div className="assistant-label">
            Student Compass <span>CFD</span>
          </div>
          {pending ? (
            <div className="thinking" role="status">
              <span className="thinking-dots">
                <i />
                <i />
                <i />
              </span>
              <span>
                Finding a clearer answer
                <span className="thinking-sub">Checking your documents…</span>
              </span>
            </div>
          ) : turn.status === "completed" ? (
            <>
              <FormattingBoundary answer={turn.answer ?? ""}>
                <Suspense fallback={<p className="markdown">{turn.answer}</p>}>
                  <AnswerMarkdown answer={turn.answer ?? ""} turnId={turn.id} />
                </Suspense>
              </FormattingBoundary>
              {!!turn.citations.length && (
                <Sources citations={turn.citations} turnId={turn.id} />
              )}
              <div className="answer-footer">
                <time dateTime={turn.completed ?? turn.created}>
                  {clock(turn.completed ?? turn.created)}
                </time>
                <button
                  className="quiet-icon"
                  aria-label={copied ? "Answer copied" : "Copy answer"}
                  onClick={copy}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                </button>
                <details className="technical">
                  <summary>
                    <SlidersHorizontal size={13} />
                    Response details
                  </summary>
                  <div className="technical-body">
                    <dl>
                      <dt>Model</dt>
                      <dd>{turn.model ?? "Local response"}</dd>
                      <dt>Dataset</dt>
                      <dd>{turn.dataset_version ?? "—"}</dd>
                      <dt>Generation time</dt>
                      <dd>
                        {typeof turn.latency === "number"
                          ? `${turn.latency.toFixed(1)}s`
                          : "—"}
                      </dd>
                    </dl>
                    <details>
                      <summary>Retrieval and active history</summary>
                      <pre>
                        {JSON.stringify(turn.diagnostics ?? {}, null, 2)}
                      </pre>
                    </details>
                  </div>
                </details>
              </div>
            </>
          ) : (
            <div className="generation-error" role="alert">
              <strong>
                {turn.unsaved
                  ? "Connection interrupted"
                  : turn.status === "failed"
                    ? "This answer couldn’t be completed"
                    : "This question was interrupted"}
              </strong>
              <p>
                {turn.unsaved
                  ? "Your question is still here. Reconnect and retry safely; the same request ID prevents duplicate messages."
                  : (turn.error ??
                    "Your question was saved. Retry to continue from here.")}
              </p>
              <div className="recovery-actions">
                <button onClick={onRetry}>
                  <RefreshCw size={14} />
                  {turn.unsaved ? "Reconnect & retry" : "Retry answer"}
                </button>
                {!turn.unsaved && (
                  <button className="text-button" onClick={onDiscard}>
                    Discard question
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function ConversationMenu({
  chat,
  onRename,
  onDelete,
}: {
  chat: Conversation;
  onRename: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  useEffect(() => {
    if (!open) return;
    popup.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]')
      ?.focus();
    function close(e: PointerEvent) {
      if (
        !ref.current?.contains(e.target as Node) &&
        !popup.current?.contains(e.target as Node)
      )
        setOpen(false);
    }
    function scroll() {
      const r = trigger.current?.getBoundingClientRect();
      const clip = trigger.current
        ?.closest(".history")
        ?.getBoundingClientRect();
      if (!r) return;
      if (clip && (r.bottom < clip.top || r.top > clip.bottom)) {
        setOpen(false);
        return;
      }
      setPosition({
        left: Math.max(8, Math.min(innerWidth - 162, r.right - 154)),
        top: Math.max(8, Math.min(innerHeight - 100, r.bottom + 5)),
      });
    }
    document.addEventListener("pointerdown", close);
    window.addEventListener("resize", scroll);
    window.addEventListener("scroll", scroll, true);
    return () => {
      document.removeEventListener("pointerdown", close);
      window.removeEventListener("resize", scroll);
      window.removeEventListener("scroll", scroll, true);
    };
  }, [open]);
  function dismiss() {
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div
      className="chat-menu-wrap"
      ref={ref}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          dismiss();
          e.stopPropagation();
        }
        if (["ArrowDown", "ArrowUp"].includes(e.key)) {
          e.preventDefault();
          const items = Array.from(
            popup.current?.querySelectorAll<HTMLButtonElement>(
              '[role="menuitem"]',
            ) ?? [],
          );
          const i = items.indexOf(document.activeElement as HTMLButtonElement);
          items[
            (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length
          ]?.focus();
        }
      }}
    >
      <button
        className="chat-options"
        aria-label={`Options for ${chat.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        ref={trigger}
        onKeyDown={(e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            e.preventDefault();
            e.stopPropagation();
            trigger.current?.click();
          }
        }}
        onClick={() => {
          const r = trigger.current!.getBoundingClientRect();
          setPosition({
            left: Math.max(8, Math.min(innerWidth - 162, r.right - 154)),
            top: Math.max(8, Math.min(innerHeight - 100, r.bottom + 5)),
          });
          setOpen(!open);
        }}
      >
        <MoreHorizontal size={18} />
      </button>
      {open &&
        createPortal(
          <div
            className="chat-menu"
            ref={popup}
            style={{
              position: "fixed",
              ...position,
              right: "auto",
              width: 154,
              zIndex: 50,
            }}
            role="menu"
            aria-label="Conversation actions"
          >
            <button
              role="menuitem"
              onClick={() => {
                dismiss();
                onRename();
              }}
            >
              <Pencil size={14} />
              Rename
            </button>
            <button
              className="danger"
              role="menuitem"
              onClick={() => {
                dismiss();
                onDelete();
              }}
            >
              <Trash2 size={14} />
              Delete
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}

function Modal({
  mode,
  chat,
  onClose,
  onSave,
  busy,
  error,
}: {
  mode: "rename" | "delete" | "about";
  chat?: Conversation;
  onClose: () => void;
  onSave: (title: string) => void;
  busy: boolean;
  error: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState(chat?.title ?? "");
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(e) => {
        if (busy) e.preventDefault();
        else onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
      aria-labelledby="dialog-title"
    >
      <div className="modal-inner">
        <button
          className="modal-close quiet-icon"
          aria-label="Close dialog"
          onClick={onClose}
          disabled={busy}
        >
          <X size={19} />
        </button>
        <span className={`modal-icon ${mode === "delete" ? "red" : ""}`}>
          {mode === "delete" ? (
            <Trash2 size={23} />
          ) : mode === "rename" ? (
            <Pencil size={23} />
          ) : (
            <Compass size={26} />
          )}
        </span>
        <h2 id="dialog-title">
          {mode === "rename"
            ? "A new name for this chat"
            : mode === "delete"
              ? "Delete this conversation?"
              : "A little about your Compass"}
        </h2>
        {mode === "about" ? (
          <>
            <p>
              A student-built guide to FAST policies, campus services, and
              financial assistance, grounded in four reviewed documents.
            </p>
            <div className="about-note">
              <ShieldCheck size={20} />
              <p>
                Conversations stay in this local workspace. Relevant messages
                and document passages are sent to Google to generate answers.
                Avoid sharing personal records.
              </p>
            </div>
            <p>
              Full transcripts are saved. Active memory uses the latest six
              completed exchanges within a bounded context. University offices
              retain final authority; documents may not reflect the latest
              policy.
            </p>
            <button className="primary" onClick={onClose}>
              Got it <ArrowRight size={16} />
            </button>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!busy) onSave(title);
            }}
          >
            {mode === "rename" ? (
              <label>
                Conversation name
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                  autoFocus
                  required
                />
              </label>
            ) : (
              <p>
                “{chat?.title}” and its saved messages and sources will be
                permanently removed from this laptop.
              </p>
            )}
            {error && (
              <p className="modal-error" role="alert">
                {error}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={onClose}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={mode === "delete" ? "destructive" : "primary"}
                disabled={busy || (mode === "rename" && !title.trim())}
              >
                {busy
                  ? "Saving…"
                  : mode === "delete"
                    ? "Delete conversation"
                    : "Save name"}
              </button>
            </div>
          </form>
        )}
      </div>
    </dialog>
  );
}

export default function App() {
  const [chats, setChats] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState(uuid);
  const [byChat, setByChat] = useState<Record<string, Turn[]>>({});
  const [health, setHealth] = useState<Health | null>(null);
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [sidebar, setSidebar] = useState(false);
  const [notice, setNotice] = useState("");
  const [loadingId, setLoadingId] = useState("");
  const [loadError, setLoadError] = useState("");
  const [modal, setModal] = useState<{
    mode: "rename" | "delete" | "about";
    chat?: Conversation;
  } | null>(null);
  const [modalBusy, setModalBusy] = useState(false);
  const [modalError, setModalError] = useState("");
  const activeRef = useRef(activeId);
  const loadSequence = useRef(0);
  const sending = useRef(new Set<string>());
  const textarea = useRef<HTMLTextAreaElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const stickBottom = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const turns = byChat[activeId] ?? [];
  const selected = chats.find((c) => c.id === activeId);
  const unfinished = turns.some((t) => t.status !== "completed");
  const running = turns.some(
    (t) => t.status === "pending" && t.running && !t.unsaved,
  );

  const refreshList = useCallback(async () => {
    const list = await api<Conversation[]>("/conversations");
    setChats(list);
  }, []);
  const refreshHealth = useCallback(async () => {
    setHealth(await api<Health>("/health"));
  }, []);
  useEffect(() => {
    let live = true;
    Promise.all([refreshList(), refreshHealth()]).catch((e) => {
      if (live) setNotice(errorText(e));
    });
    return () => {
      live = false;
    };
  }, [refreshList, refreshHealth]);

  const mergeTurn = useCallback(
    (cid: string, turn: Turn) =>
      setByChat((prev) => {
        const old = prev[cid] ?? [];
        const index = old.findIndex(
          (t) =>
            t.id === turn.id ||
            (t.client_request_id &&
              t.client_request_id === turn.client_request_id),
        );
        return {
          ...prev,
          [cid]:
            index < 0
              ? [...old, turn]
              : old.map((t, i) => (i === index ? turn : t)),
        };
      }),
    [],
  );
  const loadChat = useCallback(async (cid: string, initial = false) => {
    const sequence = ++loadSequence.current;
    if (initial) setLoadingId(cid);
    try {
      const chat = await api<Conversation>(`/conversations/${cid}`);
      if (sequence !== loadSequence.current || activeRef.current !== cid)
        return;
      setByChat((prev) => ({
        ...prev,
        [cid]: [
          ...(chat.turns ?? []),
          ...(prev[cid] ?? []).filter(
            (t) =>
              t.unsaved &&
              !chat.turns?.some(
                (s) => s.client_request_id === t.client_request_id,
              ),
          ),
        ],
      }));
      setLoadError("");
      setNotice("");
    } catch (error) {
      if (sequence === loadSequence.current && activeRef.current === cid) {
        setNotice(errorText(error));
        setLoadError(cid);
      }
    } finally {
      if (sequence === loadSequence.current) setLoadingId("");
    }
  }, []);
  const known = !!selected;
  useEffect(() => {
    if (known) void loadChat(activeId, true);
  }, [activeId, known, loadChat]);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => void loadChat(activeId), 1200);
    return () => clearInterval(timer);
  }, [activeId, running, loadChat]);
  useEffect(() => {
    const el = scroll.current;
    if (el && stickBottom.current)
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [activeId, turns.length, turns.at(-1)?.status, turns.at(-1)?.answer]);
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = "auto";
      textarea.current.style.height =
        Math.min(textarea.current.scrollHeight, 150) + "px";
    }
  }, [draft]);
  useEffect(() => {
    if (!sidebar) return;
    const before = document.activeElement as HTMLElement | null;
    const nav = document.querySelector<HTMLElement>(".sidebar");
    nav?.querySelector<HTMLButtonElement>(".new-chat")?.focus();
    function keyboard(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setSidebar(false);
        return;
      }
      if (e.key === "Tab") {
        const nodes = Array.from(
          nav?.querySelectorAll<HTMLElement>("button,a,input") ?? [],
        ).filter(
          (el) => el.getClientRects().length && !el.hasAttribute("disabled"),
        );
        const first = nodes[0],
          last = nodes.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("keydown", keyboard);
      before?.focus();
    };
  }, [sidebar]);

  function selectChat(cid: string) {
    activeRef.current = cid;
    loadSequence.current++;
    setActiveId(cid);
    setDraft("");
    setNotice("");
    setLoadError("");
    setLoadingId("");
    setSidebar(false);
    stickBottom.current = true;
    setAtBottom(true);
  }
  function newChat() {
    selectChat(uuid());
    requestAnimationFrame(() => textarea.current?.focus());
  }
  async function sendTurn(cid: string, t: Turn) {
    if (sending.current.has(cid)) return;
    sending.current.add(cid);
    mergeTurn(cid, {
      ...t,
      running: true,
      status: "pending",
      unsaved: true,
      error: null,
    });
    try {
      await api<Conversation>("/conversations", {
        method: "POST",
        body: JSON.stringify({ id: cid }),
      });
      const saved = await api<Turn>(`/conversations/${cid}/turns`, {
        method: "POST",
        body: JSON.stringify({
          question: t.question,
          request_id: t.client_request_id,
        }),
      });
      mergeTurn(cid, saved);
      if (activeRef.current === cid) setNotice("");
      await refreshList().catch((error) => {
        if (activeRef.current === cid) setNotice(errorText(error));
      });
    } catch (error) {
      mergeTurn(cid, {
        ...t,
        status: "failed",
        running: false,
        unsaved: true,
        error: errorText(error),
      });
      if (activeRef.current === cid) setNotice(errorText(error));
    } finally {
      sending.current.delete(cid);
    }
  }
  function submit(e?: FormEvent) {
    e?.preventDefault();
    const question = draft.trim();
    if (
      !question ||
      question.length > 6000 ||
      unfinished ||
      loadingId === activeId ||
      loadError === activeId ||
      sending.current.has(activeId) ||
      !health?.ready
    )
      return;
    const id = crypto.randomUUID();
    const t: Turn = {
      id,
      conversation_id: activeId,
      question,
      answer: null,
      citations: [],
      created: new Date().toISOString(),
      completed: null,
      status: "pending",
      running: true,
      error: null,
      unsaved: true,
      client_request_id: id,
    };
    setDraft("");
    stickBottom.current = true;
    setAtBottom(true);
    void sendTurn(activeId, t);
  }
  async function retry(t: Turn) {
    const cid = activeId;
    if (t.unsaved) {
      void sendTurn(cid, t);
      return;
    }
    if (sending.current.has(cid)) return;
    sending.current.add(cid);
    mergeTurn(cid, { ...t, status: "pending", running: true, error: null });
    try {
      mergeTurn(
        cid,
        await api<Turn>(`/turns/${t.id}/retry`, { method: "POST" }),
      );
      await refreshList().catch((error) => setNotice(errorText(error)));
    } catch (error) {
      mergeTurn(cid, { ...t, error: errorText(error) });
      if (activeRef.current === cid) setNotice(errorText(error));
    } finally {
      sending.current.delete(cid);
    }
  }
  async function discard(t: Turn) {
    const cid = activeId;
    try {
      await api(`/turns/${t.id}`, { method: "DELETE" });
      setByChat((prev) => ({
        ...prev,
        [cid]: (prev[cid] ?? []).filter((row) => row.id !== t.id),
      }));
      await refreshList();
      setNotice("");
    } catch (error) {
      setNotice(errorText(error));
    }
  }
  async function reconnect() {
    setNotice("");
    try {
      await Promise.all([refreshList(), refreshHealth()]);
      if (selected) await loadChat(activeId, true);
    } catch (error) {
      setNotice(errorText(error));
    }
  }
  async function saveModal(title: string) {
    if (!modal?.chat || modalBusy) return;
    setModalBusy(true);
    setModalError("");
    const { chat, mode } = modal;
    try {
      await api(`/conversations/${chat.id}`, {
        method: mode === "delete" ? "DELETE" : "PATCH",
        ...(mode === "rename"
          ? { body: JSON.stringify({ title: title.trim() }) }
          : {}),
      });
      if (mode === "delete") {
        setChats((prev) => prev.filter((c) => c.id !== chat.id));
        setByChat((prev) => {
          const next = { ...prev };
          delete next[chat.id];
          return next;
        });
        if (activeRef.current === chat.id) newChat();
      } else
        setChats((prev) =>
          prev.map((c) =>
            c.id === chat.id ? { ...c, title: title.trim() } : c,
          ),
        );
      setModal(null);
      await refreshList().catch((error) => setNotice(errorText(error)));
    } catch (error) {
      setModalError(errorText(error));
    } finally {
      setModalBusy(false);
    }
  }
  const filtered = chats.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()),
  );
  const groups = new Map<string, Conversation[]>();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (const c of filtered) {
    const day = new Date(c.updated);
    const diff = (today.getTime() - day.getTime()) / 86400000;
    const group =
      diff < 0
        ? "Today"
        : diff < 1
          ? "Yesterday"
          : diff < 7
            ? "Previous 7 days"
            : "Earlier";
    groups.set(group, [...(groups.get(group) ?? []), c]);
  }
  return (
    <div className="app-shell">
      {sidebar && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside
        className={`sidebar ${sidebar ? "is-open" : ""}`}
        aria-label="Conversations"
      >
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            newChat();
          }}
        >
          <span className="brand-mark">
            <Compass size={24} />
          </span>
          <span>
            Student Compass<small>FAST · CHINIOT-FAISALABAD</small>
          </span>
        </a>
        <button
          className="mobile-sidebar-close"
          aria-label="Close sidebar"
          onClick={() => setSidebar(false)}
        >
          <PanelLeftClose size={20} />
        </button>
        <button
          className="new-chat"
          onClick={newChat}
          aria-label="New conversation"
        >
          <Plus size={18} />
          <span>New conversation</span>
          <span className="new-chat-key" aria-hidden="true">
            ↗
          </span>
        </button>
        <label className="search-box">
          <Search size={16} />
          <input
            aria-label="Search conversations"
            placeholder="Search conversations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button aria-label="Clear search" onClick={() => setSearch("")}>
              <X size={13} />
            </button>
          )}
        </label>
        <div className="history">
          <div className="history-heading">
            YOUR CONVERSATIONS<span>{chats.length}</span>
          </div>
          {!filtered.length && (
            <p className="empty-history">
              {search
                ? "No matching conversations."
                : "A fresh start. Your conversations will appear here."}
            </p>
          )}
          {[...groups].map(([name, items]) => (
            <section className="history-group" key={name}>
              <h2>{name}</h2>
              {items.map((chat) => (
                <div
                  className={`chat-row ${chat.id === activeId ? "selected" : ""}`}
                  key={chat.id}
                >
                  <button
                    className="chat-select"
                    onClick={() => selectChat(chat.id)}
                    aria-current={chat.id === activeId ? "page" : undefined}
                  >
                    <MessageSquare size={15} />
                    <span>{chat.title}</span>
                    {(byChat[chat.id] ?? []).some((t) => t.running) && (
                      <span className="busy-dot" />
                    )}
                  </button>
                  <ConversationMenu
                    chat={chat}
                    onRename={() => {
                      setModalError("");
                      setModal({ mode: "rename", chat });
                    }}
                    onDelete={() => {
                      setModalError("");
                      setModal({ mode: "delete", chat });
                    }}
                  />
                </div>
              ))}
            </section>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="grounded-note">
            <span>
              <ShieldCheck size={18} />
            </span>
            <div>
              Grounded in your documents
              <small>Helpful answers. Sources included.</small>
            </div>
          </div>
          <button
            className="workspace-profile"
            onClick={() => setModal({ mode: "about" })}
          >
            <span className="profile-avatar">CFD</span>
            <span>
              Your student workspace<small>Local & personal</small>
            </span>
            <Info size={16} />
          </button>
        </div>
      </aside>
      <main className="workspace" inert={sidebar ? true : undefined}>
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu quiet-icon"
              aria-label="Open sidebar"
              onClick={() => setSidebar(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">YOUR CAMPUS GUIDE</span>
            <span className="header-separator">/</span>
            <span className="chat-title">
              {selected?.title ?? "New conversation"}
            </span>
          </div>
          <button
            className="workspace-badge"
            onClick={() => setModal({ mode: "about" })}
          >
            <span />
            Local workspace
            <ChevronDown size={13} />
          </button>
        </header>
        {notice && (
          <div className="connection-notice" role="alert">
            <span>{notice}</span>
            <button onClick={() => void reconnect()}>
              <RefreshCw size={14} />
              Reconnect
            </button>
            <button
              className="quiet-icon"
              aria-label="Dismiss notification"
              onClick={() => setNotice("")}
            >
              <X size={15} />
            </button>
          </div>
        )}
        {health && !health.ready && (
          <div className="setup-notice" role="status">
            <Info size={17} />
            <span>
              Your saved chats are available. To ask new questions, configure
              the local API key and reviewed index. See the setup guide.
            </span>
          </div>
        )}
        <div
          className="chat-scroll"
          ref={scroll}
          onScroll={() => {
            const el = scroll.current;
            if (el) {
              const at = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
              stickBottom.current = at;
              setAtBottom(at);
            }
          }}
        >
          {loadingId === activeId && !turns.length ? (
            <div className="chat-loading" role="status">
              <span className="thinking-dots">
                <i />
                <i />
                <i />
              </span>
              Opening your conversation…
            </div>
          ) : !turns.length ? (
            <div className="welcome">
              <div className="welcome-art" aria-hidden="true">
                <div className="orbit orbit-one" />
                <div className="orbit orbit-two" />
                <span className="orbit-dot dot-one" />
                <span className="orbit-dot dot-two" />
                <span className="hero-mark">
                  <Compass size={42} strokeWidth={1.4} />
                </span>
              </div>
              <span className="eyebrow"><span className="welcome-status-dot" /> YOUR NEXT CHAPTER STARTS HERE</span>
              <h1>
                Your campus.
                <br />
                <span>A clearer path.</span>
              </h1>
              <p className="welcome-description">
                From academic policies to campus life, find the answers
                <br className="desktop-break" /> you need to make your next move
                with confidence.
              </p>
              <div className="welcome-features" aria-label="Workspace features">
                <span><BookOpen size={14} /> Four reference documents</span>
                <span><ShieldCheck size={14} /> Sources you can explore</span>
                <span><MessageSquare size={14} /> Conversations that stay</span>
              </div>
              <div className="suggestion-heading">What would you like to explore?</div>
              <div className="suggestions">
                {examples.map(({ icon: Icon, ...item }) => (
                  <button
                    key={item.label}
                    className="suggestion"
                    onClick={() => {
                      setDraft(item.question);
                      textarea.current?.focus();
                    }}
                  >
                    <span className={`topic-icon ${item.color}`}>
                      <Icon size={21} />
                    </span>
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                    <div>
                      {item.question}
                      <ArrowRight size={17} />
                    </div>
                  </button>
                ))}
              </div>
              <div className="source-promise">
                <span className="document-stack">
                  <FileText size={15} />
                  <FileText size={15} />
                </span>
                <span>Four documents. One helpful starting point.</span>
                <span className="tiny-dot" />
                Answers with sources
              </div>
            </div>
          ) : (
            <div
              className="transcript"
              role="log"
              aria-label="Conversation messages"
              aria-live="polite"
            >
              {turns.map((t) => (
                <Message
                  key={t.id}
                  turn={t}
                  onRetry={() => void retry(t)}
                  onDiscard={() => void discard(t)}
                />
              ))}
            </div>
          )}
        </div>
        {!atBottom && turns.length > 0 && (
          <button
            className="jump-bottom"
            aria-label="Jump to latest message"
            onClick={() => {
              stickBottom.current = true;
              setAtBottom(true);
              scroll.current?.scrollTo({
                top: scroll.current.scrollHeight,
                behavior: "smooth",
              });
            }}
          >
            <ArrowDown size={18} />
          </button>
        )}
        <div className="composer-region">
          <form
            className={`composer ${unfinished ? "waiting" : ""}`}
            onSubmit={submit}
          >
            <textarea
              ref={textarea}
              aria-label="Message Student Compass"
              placeholder={
                unfinished
                  ? "Finish or retry your last question to continue…"
                  : "Ask anything about your student journey…"
              }
              value={draft}
              maxLength={6000}
              rows={1}
              disabled={
                unfinished ||
                loadingId === activeId ||
                loadError === activeId ||
                !health?.ready
              }
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <div className="composer-bottom">
              <span>
                <ShieldCheck size={14} />
                <span>Answers grounded in your documents</span>
              </span>
              <span className="compose-controls">
                {draft.length > 5500 && <small>{draft.length}/6000</small>}
                <small className="enter-hint">Enter to send</small>
                <button
                  className="send-button"
                  type="submit"
                  aria-label="Send message"
                  disabled={
                    !draft.trim() ||
                    unfinished ||
                    loadingId === activeId ||
                    loadError === activeId ||
                    !health?.ready
                  }
                >
                  <ArrowUp size={20} />
                </button>
              </span>
            </div>
          </form>
          <p className="disclaimer">
            Student-built, with care. Confirm important decisions with your
            university.
            <button onClick={() => setModal({ mode: "about" })}>
              About Compass <Info size={12} />
            </button>
          </p>
        </div>
      </main>
      {modal && (
        <Modal
          key={`${modal.mode}-${modal.chat?.id ?? ""}`}
          {...modal}
          onClose={() => {
            if (!modalBusy) setModal(null);
          }}
          onSave={(title) => void saveModal(title)}
          busy={modalBusy}
          error={modalError}
        />
      )}
    </div>
  );
}
