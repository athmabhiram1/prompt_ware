import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cloud, FileText, PanelLeftClose, PanelLeftOpen, RotateCcw, Send, Server, Waypoints, ArrowRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  getProviderSettings,
  setProviderSettings,
  submitQueryInBackground,
  type ChatItem,
  useAppStore,
} from '../lib/utils';

export default function Chat() {
  const navigate = useNavigate();
  const endRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState('');
  const [docsCollapsed, setDocsCollapsed] = useState(true);
  const [isLocalOllama, setIsLocalOllama] = useState(false);
  const [providerStatusText, setProviderStatusText] = useState('');
  const [isUpdatingProvider, setIsUpdatingProvider] = useState(false);

  const documents = useAppStore((state) => state.documents);
  const activeDocId = useAppStore((state) => state.activeDocId);
  const chatHistory = useAppStore((state) => state.chatHistory);
  const pendingQueryCount = useAppStore((state) => state.pendingQueryCount);
  const setActiveDoc = useAppStore((state) => state.setActiveDoc);
  const setHighlightedNodes = useAppStore((state) => state.setHighlightedNodes);
  const startNewChatSession = useAppStore((state) => state.startNewChatSession);

  const activeDoc = useMemo(
    () => documents.find((doc) => doc.id === activeDocId) ?? null,
    [documents, activeDocId]
  );
  const readyDocuments = useMemo(
    () => documents.filter((doc) => doc.status === 'ready'),
    [documents]
  );

  const hasCompletedChat = useMemo(
    () => chatHistory.some((message) => message.role === 'assistant'),
    [chatHistory]
  );

  const renderSources = useCallback((message: ChatItem) => {
    const all = message.sources ?? [];
    if (all.length === 0) return null;

    const docBaseName = message.docFilter
      ? message.docFilter.split('/').pop()?.toLowerCase() ?? ''
      : '';
    const filtered = docBaseName
      ? all.filter((s) => s.file.toLowerCase().includes(docBaseName))
      : all;
    const visibleSources = filtered.length > 0 ? filtered : all;

    return (
      <details className="mt-4 rounded-xl border border-[#d4c5a9] bg-[#eae3d2]/30 p-3 select-none">
        <summary className="text-xs font-bold text-[#155e54] cursor-pointer outline-none flex items-center gap-1.5 hover:text-[#84cc16] transition-colors">
          <FileText size={12} />
          Source Clauses & Verbatim Quotes
        </summary>
        <div className="mt-3 space-y-3 pl-1 select-text">
          {visibleSources.map((source, index) => (
            <div key={`${source.file}-${index}`} className="text-xs text-[#8c7e6b] space-y-1 border-t border-[#d4c5a9]/30 pt-2.5 first:border-0 first:pt-0">
              <p className="font-bold text-[#2d261e] text-[10px] uppercase tracking-wider">📄 {source.file}</p>
              <div className="prose prose-sm max-w-none text-[#2d261e] italic leading-relaxed bg-[#fbf9f4] p-3 rounded-lg border border-[#d4c5a9]/40">
                <ReactMarkdown>{source.excerpt}</ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      </details>
    );
  }, []);

  const renderGraphNodes = useCallback((message: ChatItem) => {
    if (!message.graphNodes || message.graphNodes.length === 0) {
      return null;
    }
    return (
      <details className="mt-3 rounded-xl border border-[#d4c5a9] bg-[#eae3d2]/30 p-3 select-none">
        <summary className="text-xs font-bold text-[#155e54] cursor-pointer outline-none flex items-center gap-1.5 hover:text-[#84cc16] transition-colors">
          <Waypoints size={12} />
          Referenced Knowledge Nodes ({message.graphNodes.length})
        </summary>
        <ul className="mt-3 flex flex-wrap gap-1.5 pl-1">
          {message.graphNodes.map((node) => (
            <li key={node} className="rounded-full bg-[#155e54]/10 text-[#155e54] border border-[#d4c5a9]/40 px-3 py-0.5 text-[9px] font-bold uppercase tracking-wider">
              {node}
            </li>
          ))}
        </ul>
      </details>
    );
  }, []);

  const submitQuestion = async (event: React.FormEvent) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || pendingQueryCount > 0) {
      return;
    }

    if (activeDoc && activeDoc.status !== 'ready') {
      return;
    }
    if (!activeDoc && readyDocuments.length === 0) {
      return;
    }
    setInput('');
    await submitQueryInBackground(question);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }));
  };

  useEffect(() => {
    let mounted = true;
    const loadSettings = async () => {
      try {
        const settings = await getProviderSettings();
        if (!mounted) return;
        setIsLocalOllama(settings.mode === 'local_ollama');
        setProviderStatusText(
          settings.warning
            ? settings.warning
            : settings.mode === 'local_ollama'
              ? `Local Active: LLM=${settings.query_model}, EMBED=${settings.embedding_model}`
              : 'Cloud Active: Google Gemini fallback chain'
        );
      } catch {
        if (mounted) {
          setProviderStatusText('Ready to query workspaces.');
        }
      }
    };
    void loadSettings();
    return () => {
      mounted = false;
    };
  }, []);

  const toggleProvider = async (nextLocal: boolean) => {
    setIsUpdatingProvider(true);
    try {
      const settings = await setProviderSettings({
        use_local_ollama: nextLocal,
        query_model: 'qwen3:8b',
        embedding_model: 'qwen3-embedding:8b',
        embedding_dim: 4096,
      });
      setIsLocalOllama(settings.mode === 'local_ollama');
      setProviderStatusText(
        settings.warning
          ? settings.warning
          : settings.mode === 'local_ollama'
            ? `Local Active: LLM=${settings.query_model}, EMBED=${settings.embedding_model}`
            : 'Cloud Active: Google Gemini fallback chain'
      );
    } catch {
      setProviderStatusText('Unable to modify runtime provider.');
    } finally {
      setIsUpdatingProvider(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 flex-1 min-h-[calc(100vh-12rem)]">
      
      {/* Collapsible Left Pane: Query Scope Selector */}
      {!docsCollapsed && (
        <aside className="xl:col-span-3 parchment-card p-5 space-y-4 relative">
          <div className="absolute top-3 left-3 w-3 h-3 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
          <div className="absolute bottom-3 right-3 w-3 h-3 border-b border-r border-[#8c7e6b]/40 pointer-events-none" />
          
          <h2 className="font-headline font-bold text-xl text-[#155e54]">Scope Filter</h2>
          <p className="text-xs text-[#8c7e6b] font-medium leading-relaxed">
            Select a specific document to isolate search scope, or let NyayaMitra automatically query all ready texts.
          </p>

          <div className="space-y-2 pt-2">
            <label htmlFor="doc-filter-select" className="text-[10px] font-bold uppercase tracking-wider text-[#8c7e6b]">
              Scope Target
            </label>
            <select
              id="doc-filter-select"
              value={activeDocId ?? ''}
              onChange={(event) => setActiveDoc(event.target.value || null)}
              className="w-full bg-white border border-[#d4c5a9] rounded-xl p-3 text-xs font-bold text-[#155e54] focus:outline-none"
            >
              <option value="">Auto (All ready docs)</option>
              {readyDocuments.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.name}
                </option>
              ))}
            </select>
          </div>
        </aside>
      )}

      {/* Main Column: Chat Console */}
      <section
        className={[
          'parchment-card flex flex-col overflow-hidden relative border border-[#d4c5a9] min-h-[500px]',
          docsCollapsed ? 'xl:col-span-12' : 'xl:col-span-9',
        ].join(' ')}
      >
        {/* Subtle Decorative Borders */}
        <div className="absolute top-4 left-4 w-4 h-4 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
        <div className="absolute top-4 right-4 w-4 h-4 border-t border-r border-[#8c7e6b]/40 pointer-events-none" />

        {/* Toolbar Header */}
        <div className="px-6 py-4.5 border-b border-[#d4c5a9]/50 bg-[#eae3d2]/40 flex items-center justify-between z-10 select-none">
          <div>
            <h3 className="font-headline font-bold text-lg text-[#155e54]">Risk Analysis Stream</h3>
            <p className="text-[10px] text-[#8c7e6b] font-bold uppercase tracking-wider mt-0.5">
              {activeDoc ? `Scoped: ${activeDoc.name}` : 'Scoped: Multi-Document Unified Context'}
            </p>
          </div>

          <div className="flex items-center gap-2.5 text-xs font-bold">
            <button
              type="button"
              onClick={() => setDocsCollapsed((current) => !current)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] px-3.5 py-1.5 text-xs text-[#155e54] hover:bg-white hover:scale-105 active:scale-95 transition-all shadow-sm"
            >
              {docsCollapsed ? <PanelLeftOpen size={13} /> : <PanelLeftClose size={13} />}
              {docsCollapsed ? 'Show Scope' : 'Hide Scope'}
            </button>

            {hasCompletedChat && (
              <button
                type="button"
                onClick={startNewChatSession}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] px-3.5 py-1.5 text-xs text-[#155e54] hover:bg-white hover:scale-105 active:scale-95 transition-all shadow-sm"
              >
                <RotateCcw size={13} />
                Clear
              </button>
            )}

            {hasCompletedChat && (
              <button
                type="button"
                onClick={() => navigate('/graph')}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] px-3.5 py-1.5 text-xs text-[#155e54] hover:bg-white hover:scale-105 active:scale-95 transition-all shadow-sm"
              >
                <Waypoints size={13} />
                View Graph
              </button>
            )}

            <button
              type="button"
              disabled={isUpdatingProvider}
              onClick={() => void toggleProvider(!isLocalOllama)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] px-3.5 py-1.5 text-xs text-[#155e54] hover:bg-white hover:scale-105 active:scale-95 transition-all disabled:opacity-60 shadow-sm"
              title="Toggle between cloud and local Ollama"
            >
              {isLocalOllama ? <Server size={13} /> : <Cloud size={13} />}
              {isLocalOllama ? 'Local Ollama' : 'Cloud'}
            </button>
          </div>
        </div>

        {/* Messaging Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 space-y-6">
          {chatHistory.length === 0 && (
            <div className="rounded-2xl border border-dashed border-[#d4c5a9] bg-[#fbf9f4] p-8 text-center text-xs text-[#8c7e6b] font-medium leading-relaxed max-w-xl mx-auto">
              📜 Enter a query below to segment liability details. NyayaMitra will retrieve matching sections, calculate risk levels, and present citations automatically.
            </div>
          )}

          {providerStatusText && (
            <div className="rounded-xl border border-[#d4c5a9]/50 bg-[#eae3d2]/25 px-4 py-2 text-[10px] font-bold text-[#8c7e6b] uppercase tracking-wider max-w-fit select-none">
              ⚡ {providerStatusText}
            </div>
          )}

          {chatHistory.map((message) => (
            <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={[
                  'max-w-[90%] sm:max-w-[85%] rounded-2xl p-4 sm:p-5 shadow-[0_3px_10px_rgba(0,0,0,0.015)] border',
                  message.role === 'user'
                    ? 'bg-[#155e54] text-white border-transparent rounded-tr-sm'
                    : 'bg-[#fbf9f4] border-[#d4c5a9]/80 text-[#2d261e] rounded-tl-sm',
                ].join(' ')}
              >
                <div className="prose prose-sm max-w-none text-xs sm:text-sm leading-relaxed font-medium">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.role === 'assistant' && (
                  <div className="mt-4 border-t border-[#d4c5a9]/30 pt-3">
                    {message.risk && (
                      <span
                        className={[
                          'inline-flex text-[9px] font-extrabold uppercase tracking-widest px-3 py-1 rounded-full border',
                          message.risk === 'HIGH'
                            ? 'bg-rose-100 text-rose-800 border-rose-200'
                            : message.risk === 'MEDIUM'
                              ? 'bg-amber-100 text-amber-800 border-amber-200'
                              : message.risk === 'LOW'
                                ? 'bg-lime-100 text-lime-800 border-lime-200 glow-highlight'
                                : 'bg-slate-100 text-slate-700 border-slate-200',
                        ].join(' ')}
                      >
                        🛡️ {message.risk} RISK
                      </span>
                    )}

                    {renderSources(message)}
                    {renderGraphNodes(message)}

                    {message.graphNodes && message.graphNodes.length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          setHighlightedNodes(message.graphNodes ?? []);
                          navigate('/graph');
                        }}
                        className="mt-4 inline-flex items-center gap-1 text-[10px] font-extrabold text-[#155e54] hover:text-[#84cc16] uppercase tracking-wider"
                      >
                        Inspect in Canvas <ArrowRight size={10} />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {pendingQueryCount > 0 && (
            <div className="rounded-2xl border border-[#d4c5a9]/60 bg-[#fbf9f4]/60 p-5 text-xs text-[#8c7e6b] font-bold animate-pulse uppercase tracking-wider">
              ⏳ Simplifying covenants and verifying clauses...
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input Bar */}
        <div className="p-5 bg-gradient-to-t from-[#fbf9f4] via-[#fbf9f4]/80 to-transparent border-t border-[#d4c5a9]/40 z-10">
          {readyDocuments.length === 0 && (
            <p className="max-w-4xl mx-auto mb-3 text-xs font-bold text-rose-800 text-center">
              ⚠ No document is ready. Upload a PDF in the Upload tab to activate querying.
            </p>
          )}
          <form onSubmit={submitQuestion} className="max-w-4xl mx-auto relative group">
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask anything about liabilities, dispute clauses, and safety conditions..."
              className="w-full bg-[#fbf9f4] border border-[#d4c5a9] rounded-full py-4.5 px-6 pr-16 shadow-[0_8px_20px_rgba(45,38,30,0.03)] focus:outline-none focus:ring-1 focus:ring-[#155e54] text-sm text-[#2d261e] placeholder:text-[#8c7e6b]/70 font-semibold"
            />
            <button
              type="submit"
              disabled={!input.trim() || pendingQueryCount > 0 || readyDocuments.length === 0}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 w-11 h-11 bg-[#155e54] rounded-full flex items-center justify-center text-white shadow-md hover:bg-[#84cc16] hover:scale-105 active:scale-95 disabled:bg-[#8c7e6b]/50 disabled:cursor-not-allowed transition-all"
            >
              <Send size={15} strokeWidth={2.3} />
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}