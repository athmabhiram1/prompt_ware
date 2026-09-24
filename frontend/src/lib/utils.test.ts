import { describe, expect, it } from "vitest";
import { cn } from "./utils";
import { useAppStore } from "./utils";

describe("utils cn", () => {
  it("merges classes", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});

describe("useAppStore", () => {
  it("sets company and documents", () => {
    const { setCompanyId, setDocuments, setActiveDoc, clearChat } = useAppStore.getState();
    setCompanyId("test-co");
    expect(useAppStore.getState().companyId).toBe("test-co");
    setDocuments([{ id: "d1", name: "a.pdf", status: "ready", company_id: "test-co" }]);
    expect(useAppStore.getState().documents).toHaveLength(1);
    setActiveDoc("d1");
    expect(useAppStore.getState().activeDocId).toBe("d1");
    clearChat();
    expect(useAppStore.getState().chatHistory).toHaveLength(0);
  });
  it("upserts and updates status", () => {
    const store = useAppStore.getState();
    store.setDocuments([]);
    store.upsertDocument({ id: "d2", name: "b.pdf", status: "indexing", company_id: "c1" });
    expect(useAppStore.getState().documents.some(d => d.id === "d2")).toBe(true);
    store.setDocumentStatus("d2", "ready");
    expect(useAppStore.getState().documents.find(d => d.id === "d2")?.status).toBe("ready");
  });
  it("chat pending flow", () => {
    const s = useAppStore.getState();
    s.clearChat();
    useAppStore.getState().addUserMessage("hi again");
    expect(useAppStore.getState().chatHistory.length).toBeGreaterThan(0);
    const id = useAppStore.getState().addAssistantPendingMessage(null);
    expect(typeof id).toBe("string");
    useAppStore.getState().resolveAssistantMessage(id, { answer: "ans", risk_level: "LOW", source_clauses: [], graph_nodes_involved: [] }, null);
    const msg = useAppStore.getState().chatHistory.find(m => m.id === id);
    expect(msg?.content).toBe("ans");
    const id2 = useAppStore.getState().addAssistantPendingMessage(null);
    useAppStore.getState().failAssistantMessage(id2, "failed msg", null);
    expect(useAppStore.getState().chatHistory.find(m => m.id === id2)?.content).toBe("failed msg");
  });
});
