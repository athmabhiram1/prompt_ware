import { motion } from 'framer-motion';
import { ArrowRight, FileText, Sparkles, ShieldCheck, HelpCircle } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '../lib/utils';

export default function Home() {
  const navigate = useNavigate();
  const companyId = useAppStore((state) => state.companyId);

  return (
    <div className="space-y-16 flex-1 flex flex-col justify-center select-none">
      
      {/* Premium Hero Card Container with Custom Image Background */}
      <section 
        className="relative overflow-hidden p-8 md:p-14 lg:p-20 border-2 border-[#8c7e6b]/40 rounded-[2.5rem] shadow-[0_20px_50px_rgba(45,38,30,0.08)]"
        style={{
          backgroundImage: "linear-gradient(135deg, rgba(251,249,244,0.75) 0%, rgba(244,240,230,0.8) 100%), url('/hero.webp')",
          backgroundSize: "cover",
          backgroundPosition: "center",
          boxShadow: "inset 0 0 80px rgba(139,94,60,0.15), 0 20px 40px rgba(45,38,30,0.08)"
        }}
      >
        {/* Subtle Inner Frame Accent */}
        <div className="absolute top-4 left-4 w-4 h-4 border-t border-l border-[#8c7e6b]/35 pointer-events-none" />
        <div className="absolute top-4 right-4 w-4 h-4 border-t border-r border-[#8c7e6b]/35 pointer-events-none" />
        <div className="absolute bottom-4 left-4 w-4 h-4 border-b border-l border-[#8c7e6b]/35 pointer-events-none" />
        <div className="absolute bottom-4 right-4 w-4 h-4 border-b border-r border-[#8c7e6b]/35 pointer-events-none" />

        {/* Main Content centered beautifully */}
        <div className="relative max-w-4xl mx-auto text-center z-10 space-y-8 py-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-[#8c7e6b]/45 bg-[#eae3d2]/70 px-5 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-[#155e54] shadow-sm"
          >
            <Sparkles size={13} className="text-[#84cc16]" />
            LEGAL INTELLIGENCE • ACTIVE WORKSPACE: {companyId.toUpperCase()}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.02 }}
            className="font-black text-3xl sm:text-4xl md:text-5xl lg:text-6xl tracking-tight text-[#155e54] uppercase font-serif drop-shadow-[0_4px_8px_rgba(0,0,0,0.1)] select-none border-b-2 border-[#8c7e6b]/30 pb-4 max-w-2xl mx-auto"
            style={{ fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif" }}
          >
            NyayaMitra
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="font-headline font-extrabold text-lg sm:text-xl md:text-2xl lg:text-3xl leading-[1.2] text-[#1a2e05] font-serif drop-shadow-[0_2px_2px_rgba(255,255,255,0.7)]"
          >
            Know exactly what you are agreeing to.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="max-w-2xl mx-auto text-xs sm:text-sm md:text-base text-[#5a4e3f] font-medium leading-relaxed drop-shadow-[0_1px_1px_rgba(255,255,255,0.5)]"
          >
            Upload Terms of Service, identify hidden traps, search clauses instantly, and map interactive legal relationship nodes on our canvas. Fully containerized & private.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="flex flex-wrap items-center justify-center gap-4 pt-4"
          >
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="inline-flex h-13 items-center gap-2.5 rounded-full bg-[#155e54] px-8 font-bold text-xs uppercase tracking-wider text-white shadow-lg hover:bg-[#84cc16] hover:scale-105 active:scale-95 transition-all"
            >
              Start With Upload
              <ArrowRight size={14} />
            </button>
            <Link
              to="/chat"
              className="inline-flex h-13 items-center gap-2.5 rounded-full border-2 border-[#8c7e6b]/40 bg-[#fbf9f4] px-8 font-bold text-xs uppercase tracking-wider text-[#155e54] shadow-sm hover:bg-white hover:scale-105 active:scale-95 transition-all"
            >
              Analyze Clauses
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Product Feature Bento Grid */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Feature Card 1 */}
        <div className="parchment-card p-8 space-y-4 hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden group select-text">
          <div className="w-12 h-12 rounded-2xl bg-[#155e54]/10 text-[#155e54] flex items-center justify-center">
            <FileText size={22} strokeWidth={2.3} />
          </div>
          <h3 className="font-headline font-bold text-lg text-[#2d261e]">Clinical Ingestion</h3>
          <p className="text-xs text-[#8c7e6b] leading-relaxed font-medium">
            Upload PDFs in a single click. LightRAG indexes relationships cleanly and isolates documents under company workspaces with no memory leaks.
          </p>
        </div>

        {/* Feature Card 2 */}
        <div className="parchment-card p-8 space-y-4 hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden group select-text">
          <div className="w-12 h-12 rounded-2xl bg-[#155e54]/10 text-[#155e54] flex items-center justify-center">
            <ShieldCheck size={22} strokeWidth={2.3} className="text-[#84cc16]" />
          </div>
          <h3 className="font-headline font-bold text-lg text-[#2d261e]">Risk Leveling</h3>
          <p className="text-xs text-[#8c7e6b] leading-relaxed font-medium">
            Identifies legal liabilities in standard contracts. Displays a bright lime-green or red tag detailing data leaks, arbitration traps, or termination conditions.
          </p>
        </div>

        {/* Feature Card 3 */}
        <div className="parchment-card p-8 space-y-4 hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden group select-text">
          <div className="w-12 h-12 rounded-2xl bg-[#155e54]/10 text-[#155e54] flex items-center justify-center">
            <HelpCircle size={22} strokeWidth={2.3} />
          </div>
          <h3 className="font-headline font-bold text-lg text-[#2d261e]">Verbatim Citations</h3>
          <p className="text-xs text-[#8c7e6b] leading-relaxed font-medium">
            Every AI response maps to precise legal sentences retrieved directly from the PDF. No hallucinations. Complete transparency.
          </p>
        </div>

      </section>
      
    </div>
  );
}
