import React from 'react';

const GreenRoomPreview: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#0B0D11] p-8 text-[#A0AAB7] font-sans selection:bg-cyan-500/30">
      <div className="max-w-xl mx-auto space-y-8">
        
        {/* Header Section */}
        <header className="mb-10">
          <p className="text-[#00E5FF] font-extrabold text-[11px] tracking-[2.5px] uppercase mb-1">
            Interview Assistant
          </p>
          <h1 className="text-4xl font-black text-white tracking-tighter uppercase">
            CareerCaster
          </h1>
        </header>

        {/* Audio Hardware Card */}
        <div className="bg-[#161A21] border border-[#252A34] rounded-[18px] p-6 space-y-6 hover:border-[#303743] transition-colors shadow-xl">
          <h2 className="text-[#00E5FF] font-extrabold text-[11px] tracking-[1.5px] uppercase">
            System Audio Setup
          </h2>
          
          {/* Recruiter Feed */}
          <div className="space-y-2">
            <label className="text-[11px] font-bold text-[#6B7280] uppercase tracking-wider">
              Interviewer Source (Speakers/Headphones)
            </label>
            <div className="w-full bg-[#1C222D] border border-[#313948] rounded-xl px-4 py-3 flex items-center justify-between text-white text-sm">
              <span>Stereo Mix (Realtek(R) Audio)</span>
              <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <div className="h-[5px] bg-[#0D1014] border border-[#1C222D] rounded-full overflow-hidden">
              <div className="h-full bg-[#00E5FF] w-[45%]" />
            </div>
          </div>

          {/* Mic Feed */}
          <div className="space-y-2">
            <label className="text-[11px] font-bold text-[#6B7280] uppercase tracking-wider">
              Your Microphone Source
            </label>
            <div className="w-full bg-[#1C222D] border border-[#313948] rounded-xl px-4 py-3 flex items-center justify-between text-white text-sm">
              <span>Microphone Array (Intel® Smart Sound)</span>
              <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <div className="h-[5px] bg-[#0D1014] border border-[#1C222D] rounded-full overflow-hidden">
              <div className="h-full bg-[#00E5FF] w-[15%]" />
            </div>
          </div>
        </div>

        {/* Mission Parameters Card */}
        <div className="bg-[#161A21] border border-[#252A34] rounded-[18px] p-6 space-y-4 shadow-xl">
          <h2 className="text-[#00E5FF] font-extrabold text-[11px] tracking-[1.5px] uppercase">
            Interview Data Summary
          </h2>
          <div className="space-y-1">
             <p className="text-[15px] font-semibold text-white">
                IDENTIFIED CANDIDATE: <span className="text-cyan-400 font-bold uppercase ml-2">Pravalika</span>
             </p>
             <p className="text-[15px] font-semibold text-white">
                TARGET POSITION: <span className="text-white font-bold uppercase ml-2">Software Engineer</span>
             </p>
          </div>
          <p className="text-[10px] font-extrabold text-[#10B981] flex items-center gap-2 mt-2">
             <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse" />
             RESUME CONTEXT LOADED
          </p>
        </div>

        {/* AI Setup Card */}
        <div className="bg-[#161A21] border border-[#252A34] rounded-[18px] p-6 space-y-6 shadow-xl">
          <h2 className="text-[#00E5FF] font-extrabold text-[11px] tracking-[1.5px] uppercase">
            AI Co-Pilot Config
          </h2>
          <div className="flex items-center gap-6">
            <div className="flex-1 bg-[#1C222D] border border-[#313948] rounded-xl px-4 py-3 flex items-center justify-between text-white text-sm">
              <span>gemini-3-flash-preview</span>
              <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <div className="flex flex-col gap-1 pr-4">
               <span className="font-mono text-[11px] font-bold text-[#10B981]">SECURE (45ms)</span>
               <div className="w-[35px] h-1 bg-[#00FF7F] rounded-full" />
            </div>
          </div>
          <div className="flex items-center gap-3">
             <div className="w-5 h-5 bg-[#00E5FF] rounded-md flex items-center justify-center">
                <svg className="w-4 h-4 text-black" fill="currentColor" viewBox="0 0 20 20"><path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>
             </div>
             <span className="text-xs text-[#8F9BA8]">HIDE INTERFACE ON START (STEALTH MODE)</span>
          </div>
        </div>

        {/* Final Action */}
        <div className="pt-4 flex flex-col items-center gap-6">
          <button className="w-full bg-gradient-to-r from-[#00E5FF] to-[#00A3FF] py-5 rounded-xl text-black font-extrabold uppercase tracking-widest text-[15px] hover:brightness-110 active:scale-[0.98] transition-all shadow-lg shadow-cyan-500/20">
             Finalize & Start Co-Pilot
          </button>
          <p className="text-[10px] font-black text-[#4B5563] tracking-widest">
            SECURE ENCRYPTED SESSION • v1.8 PRO
          </p>
        </div>

      </div>
    </div>
  );
};

export default GreenRoomPreview;
