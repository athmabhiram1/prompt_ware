import { useState, useRef, useEffect } from "react";
import { Send, FileText, CheckCircle2, ChevronLeft, ChevronRight, Bookmark, Share2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import KnowledgeGraph from "./KnowledgeGraph"; // We'll update the Graph to support light mode

type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: string;
};

export default function Dashboard({ activeTab = "Chat" }: { activeTab?: string }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "ai",
      content: "I have fully analyzed your Platform_ToS.pdf document. What specific clauses or liabilities would you like me to clarify?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [input, setInput] = useState("");
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTab]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, newMsg]);
    setInput("");

    // Mock AI response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "ai",
          content: "Under Section 4.2 Data Monetization, the legal entity retains absolute rights to process your metadata. However, Section 9.1 allows you to request full deletion upon account termination, creating a contradiction that favors your right to eventual privacy.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      ]);
    }, 1000);
  };

  const docs = [
    { title: "Service_Level_Agmt.pdf", status: "PROCESSED", active: false },
    { title: "Privacy_Policy_v2.docx", status: "ACTIVE ANALYSIS", active: true },
    { title: "Terms_of_Use.pdf", status: "PROCESSED", active: false },
    { title: "Employment_Clause.pdf", status: "PROCESSED", active: false },
  ];

  return (
    <main className="pt-32 pb-24 px-6 lg:px-20 max-w-[1500px] mx-auto min-h-[calc(100vh-80px)] flex gap-8">
      
      {/* Collapsible Sidebar */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 320, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="flex-shrink-0 flex flex-col space-y-8 overflow-hidden"
          >
            <div className="w-[320px] space-y-8 pr-4">
              <div className="space-y-1">
                <h1 className="text-2xl font-extrabold tracking-tight text-[#004541]">Active Documents</h1>
                <p className="text-gray-500 text-sm font-medium">4 files currently being analyzed</p>
              </div>

              <div className="space-y-3">
                {docs.map((doc, idx) => (
                  <div
                    key={idx}
                    className={`group flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer shadow-sm border
                      ${doc.active 
                        ? 'bg-[#004541]/5 border-[#004541]/20 shadow-md border-l-4 border-l-[#004541]' 
                        : 'bg-white hover:bg-gray-50 border-transparent hover:shadow-md'
                      }
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center
                        ${doc.active ? 'bg-[#004541] text-white' : 'bg-[#004541]/5 text-[#004541]'}
                      `}>
                        <FileText size={18} aria-hidden="true" />
                      </div>
                      <div>
                        <p className={`text-sm font-semibold ${doc.active ? 'text-[#004541]' : 'text-gray-900'}`}>
                          {doc.title}
                        </p>
                        <p className={`text-[10px] uppercase tracking-widest font-bold ${doc.active ? 'text-[#004541]' : 'text-gray-400'}`}>
                          {doc.status}
                        </p>
                      </div>
                    </div>
                    <CheckCircle2 size={18} aria-hidden="true" className={doc.active ? 'text-[#004541]' : 'text-green-600/60'} />
                  </div>
                ))}
              </div>

              {/* Decorative Image Container */}
              <div className="rounded-2xl overflow-hidden aspect-video shadow-sm bg-gradient-to-br from-[#004541] to-emerald-900 relative group cursor-pointer">
                 <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors" />
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main Content Area (Chat + Graph Toggle) */}
      <section className="flex-1 flex flex-col relative h-[78vh] min-h-[600px]">
        {/* Sidebar Toggle Button */}
        <button 
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-expanded={sidebarOpen}
          className="absolute -left-4 top-1/2 -translate-y-1/2 z-20 w-8 h-8 bg-white border border-gray-200 rounded-full shadow-md flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004541]"
        >
          {sidebarOpen ? <ChevronLeft size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}
        </button>

        <div className="flex-1 glass-panel bg-white/70 rounded-[24px] shadow-[0_20px_40px_rgba(17,24,39,0.03)] flex flex-col overflow-hidden relative border border-white">
          
          {activeTab === 'Knowledge Graph' ? (
             <div className="flex-1 bg-gray-50/50">
               <KnowledgeGraph />
             </div>
          ) : (
            <>
              {/* Chat Feed */}
              <div className="flex-grow overflow-y-auto p-8 lg:p-12 space-y-10 scrollbar-thin">
                
                {/* Intro AI Response matching screenshot */}
                <div className="flex justify-start items-start gap-4">
                  <div className="w-10 h-10 rounded-full bg-[#004541] flex items-center justify-center text-white shrink-0 shadow-lg">
                    <span className="material-symbols-outlined text-lg">SP</span>{/* Placeholder icon */}
                  </div>
                  <div className="space-y-4 max-w-[85%]">
                    <div className="glass-panel bg-white/90 p-8 rounded-[1.5rem] rounded-tl-sm shadow-sm border border-emerald-50/50">
                      <div className="flex items-center gap-3 mb-6">
                        <span className="bg-[#FFF1F2] text-[#9F1239] text-[10px] font-bold tracking-[0.1em] px-3 py-1 rounded-sm uppercase">
                          High Risk
                        </span>
                        <span className="text-gray-400 text-xs font-medium">Analysis complete • 1.2s</span>
                      </div>
                      
                      <div className="space-y-4 text-gray-800 leading-relaxed text-[15px]">
                        <p>I have analyzed <strong>Section 4.2: Limitation of Liability</strong> in your uploaded <em>Privacy_Policy_v2.docx</em>. I found a critical clause that significantly shifts burden onto the user.</p>
                        <div className="bg-gray-50 p-5 rounded-xl border-l-2 border-red-500">
                          <p className="text-sm italic text-gray-600">
                            "The Company shall not be held liable for any data breaches resulting from third-party vendor negligence, even if such vendors were vetted by the Company."
                          </p>
                        </div>
                        <p><strong>Impact:</strong> This effectively waives your right to seek damages if a subcontractor leaks your sensitive data. Most standard policies include a reasonable care backstop which is missing here.</p>
                      </div>

                      <div className="mt-8 pt-6 border-t border-gray-100 flex gap-4">
                        <button className="flex items-center gap-2 text-xs font-bold text-[#004541] hover:opacity-70 transition-opacity uppercase">
                          <Bookmark size={14} aria-hidden="true" /> Save to Report
                        </button>
                        <button className="flex items-center gap-2 text-xs font-bold text-[#004541] hover:opacity-70 transition-opacity uppercase">
                          <Share2 size={14} aria-hidden="true" /> Share with Legal
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Iterate over actual messages */}
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start items-start gap-4'}`}>
                    {msg.role === 'ai' && (
                      <div className="w-10 h-10 rounded-full bg-[#004541] flex items-center justify-center text-white shrink-0 shadow-lg">
                        <span className="text-sm font-bold">PS</span>
                      </div>
                    )}
                    <div className={`
                      ${msg.role === 'user' 
                        ? 'bg-gray-100 text-gray-800 px-6 py-4 rounded-[2rem] rounded-tr-sm max-w-[70%] text-[15px] font-medium'
                        : 'glass-panel bg-white/90 p-6 rounded-[1.5rem] rounded-tl-sm shadow-sm border border-emerald-50/50 max-w-[85%] text-gray-800 text-[15px] leading-relaxed'
                      }
                    `}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                <div ref={endOfMessagesRef} />
              </div>

              {/* Input Box */}
              <div className="p-6 bg-gradient-to-t from-white via-white/90 to-transparent">
                <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative group">
                  <input
                    type="text"
                    aria-label="Ask NyayaMitra about your documents"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask NyayaMitra anything about your documents..."
                    className="w-full bg-white border border-gray-200 rounded-full py-5 px-8 pr-16 shadow-[0_10px_30px_rgba(0,0,0,0.04)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004541] focus:ring-2 focus:ring-[#004541]/20 text-gray-800 placeholder:text-gray-400 text-[15px] transition-all"
                  />
                  <button
                    type="submit"
                    aria-label="Send message"
                    disabled={!input.trim()}
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-11 h-11 bg-[#004541] disabled:bg-gray-300 rounded-full flex items-center justify-center text-white shadow-lg hover:scale-105 transition-transform focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004541]"
                  >
                    <Send size={18} aria-hidden="true" className="-ml-0.5" />
                  </button>
                </form>
              </div>
            </>
          )}

        </div>
      </section>
    </main>
  );
}
