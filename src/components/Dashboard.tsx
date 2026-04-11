import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Upload, Play, Terminal, Shield, Cpu, ExternalLink, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { GoogleGenAI } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

export default function Dashboard() {
  const [resume, setResume] = useState<string>('');
  const [jd, setJd] = useState<string>('');
  const [sessionId] = useState(() => Math.random().toString(36).substring(7));
  const [isGenerating, setIsGenerating] = useState(false);
  const [hints, setHints] = useState<string[]>([]);

  const handleStart = () => {
    // Trigger the custom protocol
    const url = `careercaster://start?id=${sessionId}`;
    window.location.href = url;
  };

  const generateHints = async () => {
    if (!resume || !jd) return;
    setIsGenerating(true);
    try {
      const response = await ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: `Resume: ${resume}\n\nJob Description: ${jd}\n\nProvide 3 short, punchy interview hints for this candidate. Format as a simple list.`,
      });
      const text = response.text || '';
      setHints(text.split('\n').filter(line => line.trim()));
    } catch (error) {
      console.error("Error generating hints:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#E4E3E0] text-[#141414] font-sans p-4 md:p-8">
      <header className="max-w-7xl mx-auto mb-8 flex justify-between items-end border-b border-[#141414] pb-4">
        <div>
          <h1 className="text-4xl font-bold tracking-tighter uppercase flex items-center gap-2">
            <Cpu className="w-8 h-8" />
            CareerCaster
          </h1>
          <p className="font-mono text-xs opacity-60 mt-1">HYBRID INTERVIEW PROTOCOL v1.0.4</p>
        </div>
        <div className="flex gap-4 items-center">
          <Badge variant="outline" className="border-[#141414] font-mono">
            SESSION: {sessionId}
          </Badge>
          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
        </div>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Inputs */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="bg-transparent border-[#141414] rounded-none shadow-none">
            <CardHeader className="border-b border-[#141414]">
              <CardTitle className="font-serif italic text-xl">Input Matrix</CardTitle>
              <CardDescription className="font-mono text-xs">Upload source data for AI analysis</CardDescription>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="resume" className="uppercase text-[10px] font-bold tracking-widest opacity-70">Candidate Resume</Label>
                <textarea
                  id="resume"
                  placeholder="Paste resume text here..."
                  className="w-full h-48 bg-white/50 border border-[#141414] p-4 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-[#141414] resize-none"
                  value={resume}
                  onChange={(e) => setResume(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="jd" className="uppercase text-[10px] font-bold tracking-widest opacity-70">Job Description</Label>
                <textarea
                  id="jd"
                  placeholder="Paste job description here..."
                  className="w-full h-48 bg-white/50 border border-[#141414] p-4 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-[#141414] resize-none"
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter className="border-t border-[#141414] p-4 flex justify-between">
              <Button 
                variant="ghost" 
                className="font-mono text-xs hover:bg-[#141414] hover:text-[#E4E3E0]"
                onClick={() => { setResume(''); setJd(''); }}
              >
                CLEAR_BUFFER
              </Button>
              <Button 
                className="bg-[#141414] text-[#E4E3E0] rounded-none hover:bg-[#141414]/90 px-8"
                onClick={generateHints}
                disabled={isGenerating || !resume || !jd}
              >
                {isGenerating ? 'ANALYZING...' : 'GENERATE_HINTS'}
              </Button>
            </CardFooter>
          </Card>
        </div>

        {/* Right Column: Status & Trigger */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="bg-[#141414] text-[#E4E3E0] rounded-none shadow-none border-none">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="font-serif italic text-xl flex items-center gap-2">
                <Shield className="w-5 h-5 text-green-500" />
                Stealth Protocol
              </CardTitle>
              <CardDescription className="text-white/40 font-mono text-xs">Local Desktop Agent Status</CardDescription>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div className="bg-black/40 p-4 rounded border border-white/5 font-mono text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="opacity-50">PROTOCOL:</span>
                  <span className="text-green-400">careercaster://</span>
                </div>
                <div className="flex justify-between">
                  <span className="opacity-50">HANDSHAKE:</span>
                  <span className="text-green-400">READY</span>
                </div>
                <div className="flex justify-between">
                  <span className="opacity-50">ENCRYPTION:</span>
                  <span className="text-green-400">AES-256-GCM</span>
                </div>
              </div>

              <div className="space-y-4">
                <p className="text-sm opacity-80 leading-relaxed">
                  Clicking <span className="text-green-400 font-bold">INITIATE_AGENT</span> will trigger your local CareerCaster agent via deep link. Ensure the agent is installed and protocol is registered.
                </p>
                <Button 
                  className="w-full bg-green-600 hover:bg-green-500 text-black font-bold h-16 text-lg rounded-none flex items-center justify-center gap-3"
                  onClick={handleStart}
                >
                  <Play className="fill-current" />
                  INITIATE_AGENT
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-transparent border-[#141414] rounded-none shadow-none">
            <CardHeader className="border-b border-[#141414]">
              <CardTitle className="font-serif italic text-xl flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                Hint Preview
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <ScrollArea className="h-48">
                <AnimatePresence mode="wait">
                  {hints.length > 0 ? (
                    <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="space-y-3"
                    >
                      {hints.map((hint, i) => (
                        <div key={i} className="flex gap-3 items-start">
                          <span className="font-mono text-[10px] opacity-40 mt-1">0{i+1}</span>
                          <p className="text-sm font-medium">{hint}</p>
                        </div>
                      ))}
                    </motion.div>
                  ) : (
                    <div className="h-full flex items-center justify-center opacity-30 italic text-sm">
                      No hints generated yet.
                    </div>
                  )}
                </AnimatePresence>
              </ScrollArea>
            </CardContent>
          </Card>

          <div className="p-4 border border-[#141414] border-dashed font-mono text-[10px] opacity-60">
            <p>WARNING: Local agent must be running to receive real-time overlay updates. Screen-share invisibility is active by default in the PyQt6 agent.</p>
          </div>
        </div>
      </main>

      <footer className="max-w-7xl mx-auto mt-12 pt-8 border-t border-[#141414] flex flex-wrap gap-8 justify-between items-center text-[10px] font-mono opacity-50 uppercase tracking-widest">
        <div className="flex gap-6">
          <span>© 2026 CareerCaster Systems</span>
          <span>Security: Verified</span>
        </div>
        <div className="flex gap-6">
          <a href="#" className="hover:underline flex items-center gap-1"><Terminal className="w-3 h-3" /> Documentation</a>
          <a href="#" className="hover:underline flex items-center gap-1"><ExternalLink className="w-3 h-3" /> GitHub</a>
        </div>
      </footer>
    </div>
  );
}
