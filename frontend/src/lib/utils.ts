import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import axios from "axios";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// W1.3: VITE_API_URL is canonical (read at build time); VITE_API_BASE_URL kept
// as a deprecated alias for existing docker-compose builds. Default targets a
// local backend on :8000 (see frontend/.env.example).
const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
});

export type DocumentStatus = "indexing" | "ready" | "failed";

export type DocumentItem = {
  id: string;
  name: string;
  status: DocumentStatus;
  company_id: string;
};

export type SourceClause = {
  file: string;
  excerpt: string;
};

export type QueryResponse = {
  answer: string;
  risk_level: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  source_clauses: SourceClause[];
  graph_nodes_involved: string[];
};

export type GraphNode = {
  id: string;
  label: string;
  type?: string;
};

export type GraphEdge = {
  source: string;
  target: string;
  label?: string;
};

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    node_count: number;
    edge_count: number;
  };
};

export type NodeDetail = {
  id: string;
  label: string;
  description: string;
  type: string;
  source_files: string[];
};

export type ProviderSettings = {
  mode: "cloud" | "local_ollama";
  primary_llm_provider: string;
  embed_provider: string;
  query_model: string;
  embedding_model: string;
  embedding_dim: number;
  requires_reindex: boolean;
  warning?: string | null;
};

export type ChatItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  risk?: QueryResponse["risk_level"];
  sources?: SourceClause[];
  graphNodes?: string[];
  docFilter?: string | null;
  isPending?: boolean;
};

type AppStore = {
  documents: DocumentItem[];
  activeDocId: string | null;
  chatHistory: ChatItem[];
  graphData: GraphData;
  highlightedNodes: string[];
  pendingQueryCount: number;
  companyId: string;
  workspaceConfigs: Record<string, { useLocalOllama: boolean }>;
  setWorkspaceConfig: (companyId: string, config: { useLocalOllama: boolean }) => void;
  setCompanyId: (companyId: string) => void;
  setDocuments: (docs: DocumentItem[]) => void;
  upsertDocument: (doc: DocumentItem) => void;
  setDocumentStatus: (docId: string, status: DocumentStatus) => void;
  setActiveDoc: (docId: string | null) => void;
  addUserMessage: (content: string) => void;
  addAssistantPendingMessage: (docFilter?: string | null) => string;
  resolveAssistantMessage: (messageId: string, data: QueryResponse, docFilter?: string | null) => void;
  failAssistantMessage: (messageId: string, content: string, docFilter?: string | null) => void;
  incrementPendingQueryCount: () => void;
  decrementPendingQueryCount: () => void;
  startNewChatSession: () => void;
  clearChat: () => void;
  setGraphData: (data: GraphData) => void;
  setHighlightedNodes: (nodes: string[]) => void;
};

const DB_NAME = "nyayamitra-ui";
const LEGACY_DB_NAME = "policysattva-ui";
const DB_VERSION = 2;
const DB_STORE = "state";
const DB_KEY = "zustand-app-store";
const LEGACY_DEMO_DOC_IDS = new Set(["truecaller_tos.pdf", "phonepe_terms.pdf", "paytm_terms.pdf"]);

let dbPromise: Promise<IDBDatabase> | null = null;
let migrationPromise: Promise<void> | null = null;

function readKeyFromDb(db: IDBDatabase, key: string): Promise<string | null> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, "readonly");
    const store = tx.objectStore(DB_STORE);
    const req = store.get(key);
    req.onsuccess = () => resolve((req.result as string | undefined) ?? null);
    req.onerror = () => reject(req.error);
  });
}

function openRawDb(name: string, version: number): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, version);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(DB_STORE)) {
        db.createObjectStore(DB_STORE);
      }
    };
  });
}

// T3 rebrand: copy the persisted zustand value from the legacy
// "policysattva-ui" DB into "nyayamitra-ui", then delete the legacy DB.
// Fully guarded — a migration failure must never break app boot.
function migrateDbName(): Promise<void> {
  if (migrationPromise) return migrationPromise;
  migrationPromise = (async () => {
    try {
      const fresh = await openRawDb(DB_NAME, DB_VERSION);
      let existing: string | null = null;
      try {
        existing = await readKeyFromDb(fresh, DB_KEY);
      } finally {
        fresh.close();
      }
      if (existing !== null) {
        try {
          indexedDB.deleteDatabase(LEGACY_DB_NAME);
        } catch {
          // best-effort legacy cleanup
        }
        return;
      }
      let legacyValue: string | null = null;
      try {
        const legacy = await openRawDb(LEGACY_DB_NAME, 1);
        try {
          legacyValue = await readKeyFromDb(legacy, DB_KEY);
        } finally {
          legacy.close();
        }
      } catch {
        return; // no legacy DB — nothing to migrate
      }
      if (legacyValue === null) {
        try {
          indexedDB.deleteDatabase(LEGACY_DB_NAME);
        } catch {
          // best-effort legacy cleanup
        }
        return;
      }
      const target = await openRawDb(DB_NAME, DB_VERSION);
      try {
        await new Promise<void>((resolve, reject) => {
          const tx = target.transaction(DB_STORE, "readwrite");
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
          tx.objectStore(DB_STORE).put(legacyValue, DB_KEY);
        });
      } finally {
        target.close();
      }
      try {
        await new Promise<void>((resolve) => {
          const del = indexedDB.deleteDatabase(LEGACY_DB_NAME);
          del.onsuccess = () => resolve();
          del.onerror = () => resolve();
          del.onblocked = () => resolve();
        });
      } catch {
        // best-effort legacy cleanup
      }
    } catch {
      // guarded: migration must never break boot
    }
  })();
  return migrationPromise;
}

function openStateDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;
  dbPromise = migrateDbName().then(() => openRawDb(DB_NAME, DB_VERSION));
  dbPromise.catch(() => {
    dbPromise = null;
  });
  return dbPromise;
}

const indexedDbStorage: StateStorage = {
  getItem: async (name) => {
    try {
      const db = await openStateDb();
      return await new Promise<string | null>((resolve, reject) => {
        const tx = db.transaction(DB_STORE, "readonly");
        const store = tx.objectStore(DB_STORE);
        const req = store.get(name);
        req.onsuccess = () => resolve((req.result as string | undefined) ?? null);
        req.onerror = () => reject(req.error);
      });
    } catch {
      return null;
    }
  },
  setItem: async (name, value) => {
    const db = await openStateDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(DB_STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(DB_STORE).put(value, name);
    });
  },
  removeItem: async (name) => {
    const db = await openStateDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(DB_STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(DB_STORE).delete(name);
    });
  },
};

const storage = createJSONStorage(() => indexedDbStorage);

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      documents: [],
      activeDocId: null,
      chatHistory: [],
      graphData: {
        nodes: [],
        edges: [],
        stats: { node_count: 0, edge_count: 0 },
      },
      highlightedNodes: [],
      pendingQueryCount: 0,
      companyId: "telegram",
      workspaceConfigs: {
        telegram: { useLocalOllama: true },
        spotify: { useLocalOllama: true },
        default_company: { useLocalOllama: true },
      },
      setWorkspaceConfig: (companyId, config) =>
        set((state) => ({
          workspaceConfigs: {
            ...state.workspaceConfigs,
            [companyId]: config,
          },
        })),
      setCompanyId: (companyId) => set({ companyId, documents: [], activeDocId: null }),
      setDocuments: (docs) =>
        set((state) => {
          if (!state.activeDocId) {
            return { documents: docs, activeDocId: null };
          }
          const matchingDoc = docs.find(
            (doc) => doc.id === state.activeDocId || doc.name === state.activeDocId
          );
          return {
            documents: docs,
            activeDocId: matchingDoc ? matchingDoc.id : null,
          };
        }),
      upsertDocument: (doc) =>
        set((state) => {
          const exists = state.documents.some((item) => item.id === doc.id || item.name === doc.name);
          if (!exists) {
            return { documents: [doc, ...state.documents] };
          }
          return {
            documents: state.documents.map((item) =>
              item.id === doc.id || item.name === doc.name ? doc : item
            ),
          };
        }),
      setDocumentStatus: (docId, status) =>
        set((state) => ({
          documents: state.documents.map((item) =>
            item.id === docId ? { ...item, status } : item
          ),
        })),
      setActiveDoc: (docId) => set({ activeDocId: docId }),
      addUserMessage: (content) =>
        set((state) => ({
          chatHistory: [
            ...state.chatHistory,
            { id: crypto.randomUUID(), role: "user", content },
          ],
        })),
      addAssistantPendingMessage: (docFilter) => {
        const id = crypto.randomUUID();
        set((state) => ({
          chatHistory: [
            ...state.chatHistory,
            {
              id,
              role: "assistant",
              content: "Analyzing document...",
              risk: "UNKNOWN",
              sources: [],
              graphNodes: [],
              docFilter: docFilter ?? null,
              isPending: true,
            },
          ],
        }));
        return id;
      },
      resolveAssistantMessage: (messageId, data, docFilter) =>
        set((state) => ({
          chatHistory: state.chatHistory.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  content: data.answer,
                  risk: data.risk_level,
                  sources: data.source_clauses,
                  graphNodes: data.graph_nodes_involved,
                  docFilter: docFilter ?? null,
                  isPending: false,
                }
              : message
          ),
        })),
      failAssistantMessage: (messageId, content, docFilter) =>
        set((state) => ({
          chatHistory: state.chatHistory.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  content,
                  risk: "UNKNOWN",
                  sources: [],
                  graphNodes: [],
                  docFilter: docFilter ?? null,
                  isPending: false,
                }
              : message
          ),
        })),
      incrementPendingQueryCount: () =>
        set((state) => ({ pendingQueryCount: state.pendingQueryCount + 1 })),
      decrementPendingQueryCount: () =>
        set((state) => ({ pendingQueryCount: Math.max(0, state.pendingQueryCount - 1) })),
      startNewChatSession: () =>
        set({
          chatHistory: [],
          highlightedNodes: [],
          graphData: {
            nodes: [],
            edges: [],
            stats: { node_count: 0, edge_count: 0 },
          },
          pendingQueryCount: 0,
        }),
      clearChat: () => set({ chatHistory: [] }),
      setGraphData: (data) => set({ graphData: data }),
      setHighlightedNodes: (nodes) => set({ highlightedNodes: nodes }),
    }),
    {
      name: DB_KEY,
      version: 2,
      migrate: (persistedState) => {
        if (!persistedState || typeof persistedState !== "object") {
          return persistedState as AppStore;
        }
        const candidate = persistedState as Partial<AppStore>;
        const docs = Array.isArray(candidate.documents)
          ? candidate.documents.filter((doc) => !LEGACY_DEMO_DOC_IDS.has(doc.id))
          : [];
        const activeDocId =
          candidate.activeDocId && docs.some((doc) => doc.id === candidate.activeDocId)
            ? candidate.activeDocId
            : null;
        return {
          ...candidate,
          documents: docs,
          activeDocId,
          companyId: candidate.companyId ?? "telegram",
          workspaceConfigs: candidate.workspaceConfigs ?? {
            telegram: { useLocalOllama: true },
            spotify: { useLocalOllama: true },
            default_company: { useLocalOllama: false },
          },
        } as AppStore;
      },
      storage,
      partialize: (state) => ({
        documents: state.documents,
        activeDocId: state.activeDocId,
        chatHistory: state.chatHistory,
        graphData: state.graphData,
        highlightedNodes: state.highlightedNodes,
        pendingQueryCount: state.pendingQueryCount,
        companyId: state.companyId,
        workspaceConfigs: state.workspaceConfigs,
      }),
    }
  )
);

export async function ingestDocument(file: File, companyId: string): Promise<{ doc_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("company_id", companyId);
  const response = await api.post<{ status: string; doc_id: string }>("/ingest", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return { doc_id: response.data.doc_id };
}

export async function getIngestStatus(docId: string, companyId: string): Promise<DocumentStatus> {
  const response = await api.get<{ doc_id: string; status: DocumentStatus }>(
    `/ingest/status/${encodeURIComponent(companyId)}/${encodeURIComponent(docId)}`
  );
  return response.data.status;
}

export async function listDocuments(companyId?: string): Promise<DocumentItem[]> {
  const response = await api.get<DocumentItem[]>("/documents", {
    params: companyId ? { company_id: companyId } : undefined,
  });
  return response.data;
}

export async function deleteDocument(docId: string, companyId: string): Promise<boolean> {
  const response = await api.delete<{ deleted: boolean }>(
    `/documents/${encodeURIComponent(companyId)}/${encodeURIComponent(docId)}`
  );
  return response.data.deleted;
}

export async function getProviderSettings(): Promise<ProviderSettings> {
  const response = await api.get<ProviderSettings>("/settings/provider");
  return response.data;
}

export async function setProviderSettings(payload: {
  use_local_ollama: boolean;
  query_model: string;
  embedding_model: string;
  embedding_dim: number;
}): Promise<ProviderSettings> {
  const response = await api.post<ProviderSettings>("/settings/provider", payload);
  return response.data;
}

export async function queryDocument(payload: {
  question: string;
  doc_filter: string | null;
  company_id: string;
}): Promise<QueryResponse> {
  const response = await api.post<QueryResponse>("/query", payload);
  return response.data;
}

export async function submitQueryInBackground(question: string): Promise<void> {
  const state = useAppStore.getState();
  const docFilter = state.activeDocId;
  const companyId = state.companyId;
  state.addUserMessage(question);
  const pendingId = state.addAssistantPendingMessage(docFilter);
  state.incrementPendingQueryCount();
  try {
    const response = await queryDocument({
      question,
      doc_filter: docFilter,
      company_id: companyId,
    });
    useAppStore.getState().resolveAssistantMessage(pendingId, response, docFilter);
    if (docFilter && response.graph_nodes_involved.length > 0) {
      useAppStore.getState().setHighlightedNodes(response.graph_nodes_involved);
    }
  } catch {
    useAppStore
      .getState()
      .failAssistantMessage(
        pendingId,
        "Query failed. Ensure backend is running and indexed documents are ready.",
        docFilter
      );
  } finally {
    useAppStore.getState().decrementPendingQueryCount();
  }
}

export async function fetchGraph(companyId: string): Promise<GraphData> {
  const activeDocId = useAppStore.getState().activeDocId;
  const response = await api.get<GraphData>("/graph", {
    params: { doc_filter: activeDocId, company_id: companyId },
  });
  return response.data;
}

export async function fetchSubgraph(nodes: string[], companyId: string): Promise<GraphData> {
  const query = nodes.join(",");
  const activeDocId = useAppStore.getState().activeDocId;
  const response = await api.get<GraphData>("/graph/subgraph", {
    params: { nodes: query, doc_filter: activeDocId, company_id: companyId },
  });
  return response.data;
}

export async function fetchNodeDetails(nodeId: string): Promise<NodeDetail> {
  const response = await api.get<NodeDetail>(`/graph/node/${encodeURIComponent(nodeId)}`);
  return response.data;
}

export async function listWorkspaces(): Promise<string[]> {
  const response = await api.get<string[]>("/workspaces");
  return response.data;
}
