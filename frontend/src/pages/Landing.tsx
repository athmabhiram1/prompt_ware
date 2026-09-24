import { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, FileText, Upload, HelpCircle, AlertCircle, CheckCircle, Server, Cloud, type LucideIcon } from 'lucide-react';
import {
  ingestDocument,
  type DocumentStatus,
  useAppStore,
  getProviderSettings,
  setProviderSettings,
} from '../lib/utils';
import { DocumentProgress } from '../components/DocumentProgress';

export default function Landing() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [isLocalOllama, setIsLocalOllama] = useState(false);
  const [providerStatusText, setProviderStatusText] = useState('');
  const [isUpdatingProvider, setIsUpdatingProvider] = useState(false);

  const documents = useAppStore((state) => state.documents);
  const activeDocId = useAppStore((state) => state.activeDocId);
  const companyId = useAppStore((state) => state.companyId);
  const upsertDocument = useAppStore((state) => state.upsertDocument);
  const setActiveDoc = useAppStore((state) => state.setActiveDoc);

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
          setProviderStatusText('Ready to index workspaces.');
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

  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Only PDF files are supported.');
      return;
    }

    setUploadError(null);
    setIsUploading(true);

    try {
      // Pass companyId from the Zustand store!
      const { doc_id } = await ingestDocument(file, companyId);
      upsertDocument({ id: doc_id, name: file.name, status: 'indexing', company_id: companyId });
      setActiveDoc(doc_id);
    } catch {
      setUploadError(`Upload failed for workspace "${companyId.toUpperCase()}". Ensure backend is running.`);
    } finally {
      setIsUploading(false);
    }
  };

  const statusStyles: Record<DocumentStatus, { bg: string, icon: LucideIcon }> = {
    indexing: { bg: 'bg-amber-100 text-amber-900 border-amber-200', icon: HelpCircle },
    ready: { bg: 'bg-lime-100 text-lime-900 border-lime-200 glow-highlight', icon: CheckCircle },
    failed: { bg: 'bg-rose-100 text-rose-900 border-rose-200', icon: AlertCircle },
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1 min-h-[calc(100vh-12rem)]">
      
      {/* Left Pane: Ingest Frame */}
      <section className="lg:col-span-7 space-y-6 flex flex-col justify-center">
        <div className="space-y-3">
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-3xl sm:text-4xl md:text-5xl font-headline font-extrabold tracking-tight text-[#1a2e05]"
          >
            Upload. Index. Simplify.
          </motion.h1>
          <p className="text-sm md:text-base text-[#8c7e6b] font-medium max-w-xl">
            Drop a legal document, rental contract, or Terms of Service. NyayaMitra converts thousands of words into instant risk metrics and searchable citations.
          </p>
        </div>

        {/* Dynamic Provider Settings Card */}
        <div className="bg-[#eae3d2]/60 border border-[#d4c5a9]/80 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-sm select-none">
          <div className="space-y-1">
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-[#155e54]">Active Indexing Provider</p>
            <p className="text-[9px] text-[#8c7e6b] font-bold uppercase tracking-wider">
              {providerStatusText || 'Detecting indexing environments...'}
            </p>
          </div>
          <button
            type="button"
            disabled={isUpdatingProvider}
            onClick={() => void toggleProvider(!isLocalOllama)}
            className="inline-flex items-center gap-1.5 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] px-4 py-2 text-xs font-bold text-[#155e54] hover:bg-white hover:scale-105 active:scale-95 transition-all disabled:opacity-60 shadow-sm self-start sm:self-auto"
            title="Toggle between cloud and local Ollama"
          >
            {isLocalOllama ? <Server size={13} aria-hidden="true" /> : <Cloud size={13} aria-hidden="true" />}
            {isLocalOllama ? 'Local Ollama' : 'Cloud'}
          </button>
        </div>

        {/* Parchment styled drop box */}
        <div className="parchment-card p-6 md:p-8 border border-[#d4c5a9] relative overflow-hidden">
          <div className="absolute top-4 left-4 w-4 h-4 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
          <div className="absolute top-4 right-4 w-4 h-4 border-t border-r border-[#8c7e6b]/40 pointer-events-none" />
          <div className="absolute bottom-4 left-4 w-4 h-4 border-b border-l border-[#8c7e6b]/40 pointer-events-none" />
          <div className="absolute bottom-4 right-4 w-4 h-4 border-b border-r border-[#8c7e6b]/40 pointer-events-none" />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full rounded-2xl border-2 border-dashed border-[#d4c5a9] bg-[#fbf9f4]/40 p-12 text-center hover:border-[#155e54] hover:bg-[#eae3d2]/20 transition-all group"
            disabled={isUploading}
          >
            <Upload aria-hidden="true" className="mx-auto text-[#155e54] group-hover:text-[#84cc16] transition-colors" size={32} strokeWidth={2.3} />
            <p className="mt-4 text-[#2d261e] font-bold text-lg">
              {isUploading ? 'Analyzing and segmenting text...' : 'Select a PDF File'}
            </p>
            <p className="text-xs text-[#8c7e6b] font-semibold mt-1.5">
              Only PDF format supported • Workspace: <span className="text-[#155e54] font-bold">{companyId.toUpperCase()}</span>
            </p>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            aria-label="Upload a PDF document"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleUpload(file);
              }
              event.target.value = '';
            }}
          />

          {uploadError && (
            <div role="alert" className="mt-4 bg-rose-50 border border-rose-200 text-rose-800 text-xs px-4 py-2.5 rounded-xl font-bold flex items-center gap-2">
              <AlertCircle size={14} aria-hidden="true" />
              {uploadError}
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => navigate('/chat')}
              className="h-12 px-6 rounded-full bg-[#155e54] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-2 hover:bg-[#84cc16] active:scale-95 transition-all shadow-md"
            >
              Analyze Chat
              <ArrowRight size={14} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => navigate('/graph')}
              className="h-12 px-6 rounded-full border border-[#d4c5a9] bg-[#fbf9f4] text-[#155e54] font-bold text-xs uppercase tracking-wider hover:bg-white active:scale-95 transition-all"
            >
              View Graph
            </button>
          </div>
        </div>
      </section>

      {/* Right Pane: Documents Side Sheet */}
      <aside className="lg:col-span-5 parchment-card p-6 border border-[#d4c5a9] flex flex-col justify-start relative">
        
        {/* Parchment Corner Frames */}
        <div className="absolute top-4 left-4 w-4 h-4 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
        <div className="absolute top-4 right-4 w-4 h-4 border-t border-r border-[#8c7e6b]/40 pointer-events-none" />
        <div className="absolute bottom-4 left-4 w-4 h-4 border-b border-l border-[#8c7e6b]/40 pointer-events-none" />
        <div className="absolute bottom-4 right-4 w-4 h-4 border-b border-r border-[#8c7e6b]/40 pointer-events-none" />

        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-headline font-bold text-[#155e54]">Company Documents</h2>
          <span className="text-xs font-bold text-[#8c7e6b] bg-[#eae3d2] px-2.5 py-0.5 rounded-full">{documents.length} files</span>
        </div>

        <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 flex-1">
          {documents.length === 0 ? (
            <div className="text-center p-8 border border-dashed border-[#d4c5a9]/50 rounded-2xl text-xs text-[#8c7e6b] font-medium">
              No files uploaded yet in this workspace. Upload your first PDF to begin parsing chunks.
            </div>
          ) : (
            documents.map((doc) => {
              const Style = statusStyles[doc.status];
              const StatusIcon = Style.icon;
              return (
                <button
                  key={doc.name}
                  type="button"
                  onClick={() => doc.status === 'ready' && setActiveDoc(doc.id)}
                  className={[
                    'w-full text-left rounded-xl p-4 border transition-all shadow-[0_2px_4px_rgba(0,0,0,0.01)]',
                    activeDocId === doc.id
                      ? 'bg-white border-[#155e54] border-l-4 border-l-[#84cc16]'
                      : 'bg-[#fbf9f4]/80 border-transparent hover:border-[#d4c5a9]',
                  ].join(' ')}
                >
                  <div className="flex justify-between items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-[#2d261e] text-xs sm:text-sm truncate">{doc.name}</p>
                      <p className="text-[10px] text-[#8c7e6b] font-bold mt-1 uppercase tracking-wider truncate">
                        ID: {doc.id}
                      </p>
                      <DocumentProgress status={doc.status} />
                    </div>
                    <span className={`text-[9px] px-2.5 py-1 border rounded-full font-bold uppercase tracking-wider flex items-center gap-1 ${Style.bg}`}>
                      <StatusIcon size={10} aria-hidden="true" />
                      {doc.status}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {activeDocId && (
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="mt-6 w-full h-12 rounded-full bg-[#155e54] text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 hover:bg-[#84cc16] active:scale-95 transition-all shadow-md"
          >
            <FileText size={14} aria-hidden="true" />
            Analyze Active Document
          </button>
        )}
      </aside>
    </div>
  );
}