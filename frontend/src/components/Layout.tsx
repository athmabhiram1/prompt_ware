import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  UserCircle, 
  Trash2, 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  Layers, 
  FileText, 
  MessageSquare, 
  Network,
  Upload
} from 'lucide-react';
import { cn, listDocuments, deleteDocument, useAppStore, listWorkspaces } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { DocumentProgress } from './DocumentProgress';

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showAddCompany, setShowAddCompany] = useState(false);
  const [newCompanyInput, setNewCompanyInput] = useState('');

  const documents = useAppStore((state) => state.documents);
  const activeDocId = useAppStore((state) => state.activeDocId);
  const companyId = useAppStore((state) => state.companyId);
  const chatHistory = useAppStore((state) => state.chatHistory);
  const workspaceConfigs = useAppStore((state) => state.workspaceConfigs);
  
  const setDocuments = useAppStore((state) => state.setDocuments);
  const setCompanyId = useAppStore((state) => state.setCompanyId);
  const setActiveDoc = useAppStore((state) => state.setActiveDoc);
  const setWorkspaceConfig = useAppStore((state) => state.setWorkspaceConfig);

  const [workspaces, setWorkspaces] = useState<string[]>(["default_company"]);
  const [newCompanyProvider, setNewCompanyProvider] = useState<boolean>(true); // default to local Ollama

  // Auto-collapse sidebar on narrower viewports on initial load
  React.useEffect(() => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  }, []);

  const workspaceKeys = Object.keys(workspaceConfigs).join(",");

  // Fetch workspaces dynamically from the backend
  React.useEffect(() => {
    const cancelled = false;
    const fetchWorkspaces = async () => {
      try {
        const list = await listWorkspaces();
        if (!cancelled) {
          const configured = Object.keys(workspaceConfigs);
          const combined = Array.from(new Set([...list, ...configured, "default_company", companyId]));
          setWorkspaces(combined);
        }
      } catch {
        if (!cancelled) {
          const configured = Object.keys(workspaceConfigs);
          setWorkspaces(Array.from(new Set([...configured, "default_company", companyId])));
        }
      }
    };
    void fetchWorkspaces();
  }, [companyId, documents.length, workspaceKeys]);

  // Poll documents for the current company
  React.useEffect(() => {
    let cancelled = false;
    let timeoutId: number | undefined;

    const refresh = async () => {
      if (cancelled) return;
      try {
        const latestDocs = await listDocuments(companyId);
        if (!cancelled) {
          setDocuments(latestDocs);
        }
      } catch {
        // Safe fallback
      } finally {
        if (!cancelled) {
          const hasIndexing = documents.some((doc) => doc.status === 'indexing');
          timeoutId = window.setTimeout(() => {
            void refresh();
          }, hasIndexing ? 3000 : 15000);
        }
      }
    };

    void refresh();

    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [companyId, setDocuments, documents.length]);

  const handleDelete = async (docId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete this document from ${companyId}?`)) {
      return;
    }
    try {
      const success = await deleteDocument(docId, companyId);
      if (success) {
        if (activeDocId === docId) {
          setActiveDoc(null);
        }
        const updated = await listDocuments(companyId);
        setDocuments(updated);
      }
    } catch {
      alert("Failed to delete document. Ensure the backend is available.");
    }
  };

  const handleNewWorkspaceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = newCompanyInput.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (!clean) return;
    
    // Save configuration in store
    setWorkspaceConfig(clean, { useLocalOllama: newCompanyProvider });
    
    // Switch workspace and update status
    setCompanyId(clean);
    setActiveDoc(null);
    setNewCompanyInput('');
    setShowAddCompany(false);

    navigate('/upload');
  };

  const handleWorkspaceSwitch = async (nextCompanyId: string) => {
    setCompanyId(nextCompanyId);
    setActiveDoc(null);
  };

  const navLinks = [
    { label: 'Overview', path: '/', icon: Layers },
    { label: 'Upload ToS', path: '/upload', icon: Upload },
    { label: 'Risk Chat', path: '/chat', icon: MessageSquare },
    { label: 'Knowledge Graph', path: '/graph', icon: Network },
  ];



  const queryCount = chatHistory.filter((msg) => msg.role === 'user').length;

  return (
    <div className="h-screen relative overflow-hidden flex bg-[#f4f0e6] text-[#2d261e] font-sans selection:bg-lime-200/50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[60] focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-xs focus:font-bold focus:text-[#155e54] focus:outline-2 focus:outline-[#155e54]"
      >
        Skip to main content
      </a>

      {/* Decorative Top Flourish Border */}
      <div aria-hidden="true" className="absolute top-0 left-0 right-0 h-[6px] bg-gradient-to-r from-amber-700 via-yellow-600 to-amber-700 z-50 shadow-md" />

      {/* Side Bar Navigation */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            aria-label="Workspace and documents sidebar"
            className="flex-shrink-0 bg-[#eae3d2] border-r border-[#d4c5a9] flex flex-col h-full overflow-hidden z-40 select-none"
          >
            <div className="w-[300px] flex flex-col h-full p-6 space-y-6">
              
              {/* Header Brand */}
              <header className="flex items-center justify-between border-b border-[#d4c5a9]/50 pb-4">
                <Link to="/" className="text-2xl font-extrabold tracking-tighter text-[#155e54] font-headline flex items-center gap-2">
                  <span className="text-[#84cc16]">📜</span> NyayaMitra
                </Link>
              </header>

              {/* Workspace Selector */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="company-workspace-select" className="text-[10px] font-bold uppercase tracking-wider text-[#8c7e6b]">
                    Active Workspace
                  </label>
                  <button 
                    onClick={() => setShowAddCompany(!showAddCompany)}
                    aria-label="Add new workspace"
                    aria-expanded={showAddCompany}
                    className="text-[#155e54] hover:text-[#84cc16] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54] rounded"
                    title="Add new workspace"
                  >
                    <Plus size={14} strokeWidth={3} aria-hidden="true" />
                  </button>
                </div>

                <select
                  id="company-workspace-select"
                  value={companyId}
                  onChange={(e) => {
                    void handleWorkspaceSwitch(e.target.value);
                  }}
                  className="w-full bg-[#fbf9f4] border border-[#d4c5a9] rounded-xl px-3 py-2 text-xs font-bold text-[#155e54] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
                >
                  {workspaces.map((c) => {
                    const config = workspaceConfigs[c] || { useLocalOllama: false };
                    return (
                      <option key={c} value={c}>
                        💼 {c.toUpperCase()} ({config.useLocalOllama ? 'LOCAL' : 'CLOUD'})
                      </option>
                    );
                  })}
                </select>
              </div>

              {/* Sidebar Links */}
              <nav aria-label="Primary" className="space-y-1">
                {navLinks.map((link) => {
                  const isActive = location.pathname === link.path;
                  const Icon = link.icon;
                  return (
                    <Link
                      key={link.path}
                      to={link.path}
                      className={cn(
                        "flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all border",
                        isActive 
                          ? "bg-[#155e54] text-white border-transparent shadow-md"
                          : "text-[#8c7e6b] border-transparent hover:bg-[#fbf9f4]/50 hover:text-[#155e54]"
                      )}
                    >
                      <Icon size={16} strokeWidth={2.3} aria-hidden="true" className={isActive ? "text-[#84cc16]" : ""} />
                      {link.label}
                    </Link>
                  );
                })}
              </nav>

              {/* Documents Scoped List */}
              <div className="flex-1 flex flex-col min-h-0 space-y-2 border-t border-[#d4c5a9]/50 pt-4">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#8c7e6b]">Documents ({documents.length})</span>
                  <span className="text-[9px] font-bold text-[#155e54] bg-[#fbf9f4] border border-[#d4c5a9] px-2 py-0.5 rounded-full uppercase">
                    {companyId}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                  {documents.length === 0 ? (
                    <div className="p-4 rounded-xl border border-dashed border-[#d4c5a9]/60 text-center text-[10px] text-[#8c7e6b]">
                      No documents. Upload a ToS to start.
                    </div>
                  ) : (
                    documents.map((doc) => {
                      const isSelected = activeDocId === doc.id;
                      return (
                        <div
                          key={doc.name}
                          role="button"
                          tabIndex={doc.status === 'ready' ? 0 : -1}
                          aria-pressed={isSelected}
                          aria-disabled={doc.status !== 'ready'}
                          onClick={() => doc.status === 'ready' && setActiveDoc(isSelected ? null : doc.id)}
                          onKeyDown={(e) => {
                            if (doc.status !== 'ready') return;
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              setActiveDoc(isSelected ? null : doc.id);
                            }
                          }}
                          className={cn(
                            "group flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer shadow-[0_2px_4px_rgba(0,0,0,0.02)]",
                            isSelected
                              ? "bg-white border-[#155e54] border-l-4 border-l-[#84cc16]"
                              : "bg-[#fbf9f4] border-transparent hover:border-[#d4c5a9]"
                          )}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className={cn(
                              "w-7 h-7 rounded-lg flex items-center justify-center text-xs",
                              isSelected ? "bg-[#155e54] text-white" : "bg-[#155e54]/10 text-[#155e54]"
                            )}>
                              <FileText size={14} aria-hidden="true" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-[11px] font-semibold truncate text-[#2d261e]">{doc.name}</p>
                              <p className="text-[9px] text-[#8c7e6b] uppercase tracking-wider font-bold">
                                {doc.status}
                              </p>
                              <DocumentProgress status={doc.status} />
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5">
                            {doc.status === 'ready' && isSelected && (
                              <span className="w-2 h-2 rounded-full bg-[#84cc16] animate-pulse" />
                            )}
                            <button
                              onClick={(e) => handleDelete(doc.id, e)}
                              aria-label={`Delete ${doc.name}`}
                              className="text-[#8c7e6b] hover:text-red-600 p-1 rounded hover:bg-red-50 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 transition-opacity"
                              title="Delete document"
                            >
                              <Trash2 size={12} aria-hidden="true" />
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Lower visual limits container */}
              <footer className="border-t border-[#d4c5a9]/50 pt-4 space-y-3">
                <div className="bg-[#fbf9f4] border border-[#d4c5a9] rounded-2xl p-3.5 space-y-2.5 shadow-sm">
                  <div className="flex justify-between items-center text-[10px] font-bold text-[#8c7e6b]">
                    <span>Documents Limit</span>
                    <span className="text-[#155e54]">{documents.length}/10</span>
                  </div>
                  <div className="h-1.5 w-full bg-[#eae3d2] rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-[#155e54] to-[#84cc16] transition-all duration-500" 
                      style={{ width: `${Math.min((documents.length / 10) * 100, 100)}%` }} 
                    />
                  </div>
                  <div className="flex justify-between items-center text-[10px] font-bold text-[#8c7e6b]">
                    <span>Analysis Queries</span>
                    <span className="text-[#155e54]">{queryCount}/20</span>
                  </div>
                  <div className="h-1.5 w-full bg-[#eae3d2] rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-[#155e54] to-[#84cc16] transition-all duration-500" 
                      style={{ width: `${Math.min((queryCount / 20) * 100, 100)}%` }} 
                    />
                  </div>
                </div>

                <div className="flex items-center gap-3 justify-center text-[#8c7e6b]">
                  <UserCircle size={16} aria-hidden="true" />
                  <span className="text-[10px] font-bold tracking-wider uppercase">{companyId}</span>
                </div>
              </footer>

            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Sidebar Toggle Handle Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        aria-expanded={sidebarOpen}
        className="absolute left-0 top-1/2 -translate-y-1/2 z-50 w-7 h-14 bg-[#eae3d2] border border-[#d4c5a9] border-l-0 rounded-r-2xl shadow-md flex items-center justify-center text-[#8c7e6b] hover:text-[#155e54] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
        style={{ left: sidebarOpen ? '300px' : '0px', transition: 'left 0.2s ease-in-out' }}
      >
        {sidebarOpen ? <ChevronLeft size={16} strokeWidth={2.5} aria-hidden="true" /> : <ChevronRight size={16} strokeWidth={2.5} aria-hidden="true" />}
      </button>

      {/* Main Content Pane */}
      <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 h-full overflow-y-auto relative p-6 md:p-8 lg:p-10 flex flex-col focus-visible:outline-none">
        {/* Gorgeous Mural Flourish Frames */}
        <div aria-hidden="true" className="absolute top-4 left-4 w-6 h-6 border-t-2 border-l-2 border-[#8c7e6b]/30 pointer-events-none" />
        <div aria-hidden="true" className="absolute top-4 right-4 w-6 h-6 border-t-2 border-r-2 border-[#8c7e6b]/30 pointer-events-none" />
        <div aria-hidden="true" className="absolute bottom-4 left-4 w-6 h-6 border-b-2 border-l-2 border-[#8c7e6b]/30 pointer-events-none" />
        <div aria-hidden="true" className="absolute bottom-4 right-4 w-6 h-6 border-b-2 border-r-2 border-[#8c7e6b]/30 pointer-events-none" />

        <div className="flex-grow flex flex-col justify-start relative z-10 max-w-[1400px] w-full mx-auto">
          {children}
        </div>
      </main>

      <AnimatePresence>
        {showAddCompany && (
          <div className="fixed inset-0 bg-[#2d261e]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 select-none">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              role="dialog"
              aria-modal="true"
              aria-labelledby="workspace-dialog-title"
              className="bg-[#fbf9f4] border border-[#d4c5a9] rounded-3xl p-6 shadow-2xl max-w-sm w-full space-y-5 relative"
            >
              {/* Corner Accents */}
              <div aria-hidden="true" className="absolute top-3 left-3 w-3 h-3 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
              <div aria-hidden="true" className="absolute bottom-3 right-3 w-3 h-3 border-b border-r border-[#8c7e6b]/40 pointer-events-none" />

              <div className="space-y-1">
                <h3 id="workspace-dialog-title" className="font-headline font-bold text-lg text-[#155e54] uppercase tracking-wide">Initialize Workspace</h3>
                <p className="text-xs text-[#8c7e6b] font-medium leading-relaxed">
                  Configure the primary LLM model and vector space provider for this custom workspace boundary.
                </p>
              </div>

              <form onSubmit={handleNewWorkspaceSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="workspace-name-input" className="text-[10px] font-extrabold uppercase tracking-wider text-[#8c7e6b]">
                    Workspace Name / ID
                  </label>
                  <input
                    id="workspace-name-input"
                    type="text"
                    required
                    value={newCompanyInput}
                    onChange={(e) => setNewCompanyInput(e.target.value)}
                    placeholder="e.g. zomato, netflix"
                    className="w-full bg-white border border-[#d4c5a9] rounded-xl px-3.5 py-2.5 text-xs font-bold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54] focus:ring-1 focus:ring-[#155e54] text-[#155e54]"
                  />
                </div>

                <div className="space-y-2">
                  <p id="workspace-provider-label" className="text-[10px] font-extrabold uppercase tracking-wider text-[#8c7e6b]">
                    Indexing Provider Config
                  </p>
                  
                  <div className="grid grid-cols-2 gap-2" role="group" aria-labelledby="workspace-provider-label">
                    <button
                      type="button"
                      aria-pressed={newCompanyProvider}
                      onClick={() => setNewCompanyProvider(true)}
                      className={cn(
                        "p-3 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-center",
                        newCompanyProvider
                          ? "bg-[#155e54] text-white border-transparent shadow-md font-bold"
                          : "bg-white text-[#8c7e6b] border-[#d4c5a9] hover:bg-[#eae3d2]/20 font-semibold"
                      )}
                    >
                      <span className="text-base">💻</span>
                      <div className="text-[10px] uppercase tracking-wider font-bold">Local Ollama</div>
                    </button>

                    <button
                      type="button"
                      aria-pressed={!newCompanyProvider}
                      onClick={() => setNewCompanyProvider(false)}
                      className={cn(
                        "p-3 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-center",
                        !newCompanyProvider
                          ? "bg-[#155e54] text-white border-transparent shadow-md font-bold"
                          : "bg-white text-[#8c7e6b] border-[#d4c5a9] hover:bg-[#eae3d2]/20 font-semibold"
                      )}
                    >
                      <span className="text-base">☁️</span>
                      <div className="text-[10px] uppercase tracking-wider font-bold">Cloud Gemini</div>
                    </button>
                  </div>
                </div>

                <div className="flex gap-2.5 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddCompany(false);
                      setNewCompanyInput('');
                    }}
                    className="flex-1 h-10 rounded-full border border-[#d4c5a9] bg-white text-[#8c7e6b] font-bold text-xs uppercase tracking-wider hover:bg-[#eae3d2]/25 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 h-10 rounded-full bg-[#155e54] text-white font-bold text-xs uppercase tracking-wider hover:bg-[#84cc16] hover:scale-105 active:scale-95 transition-all shadow-md"
                  >
                    Create
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
      
    </div>
  );
}
