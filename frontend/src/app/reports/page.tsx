'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, 
  UploadCloud, 
  CheckCircle2, 
  AlertCircle, 
  Search, 
  Sparkles,
  TrendingUp,
  RefreshCw,
  Inbox,
  BrainCircuit,
  X,
  Zap
} from 'lucide-react';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import { api, ensureAuth } from '@/lib/api';

interface Report {
  id: string;
  filename: string;
  type: string;
  date: string;
  status: string;
  labValues: { name: string; value: string; range: string; status: 'normal' | 'high' | 'low' }[];
  summary: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [holisticAnalysis, setHolisticAnalysis] = useState<string | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      await ensureAuth();
      const data = await api.reports.list();
      if (Array.isArray(data)) {
        const mapped: Report[] = data.map((r: any) => ({
          id: r.id,
          filename: r.filename || 'Medical_Report.pdf',
          type: r.report_type || 'Lab Test',
          date: r.created_at ? r.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
          status: r.status || 'Analyzed',
          labValues: r.extracted_values || [],
          summary: r.summary || 'FastAPI Tesseract OCR analysis complete.',
        }));
        setReports(mapped);
        if (mapped.length > 0) setSelectedReport(mapped[0]);
      }
    } catch (err: any) {
      console.error('Failed to fetch reports from backend:', err);
      setErrorMsg('Could not fetch reports from FastAPI backend. Ensure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setErrorMsg(null);
    const file = files[0];

    try {
      await ensureAuth();
      // Fetch or create active patient profile ID
      let patientId = '';
      const pList = await api.patients.list();
      if (pList.items && pList.items.length > 0) {
        patientId = pList.items[0].id;
      } else {
        const newP = await api.patients.create({
          full_name: 'Patient User',
          gender: 'male',
          date_of_birth: '1990-01-01',
          blood_group: 'O+',
        });
        patientId = newP.id;
      }

      let uploadRes;
      try {
        // Step 1: Write file to Puter FS for Puter AI
        const fileName = `report_upload_${Date.now()}.${file.name.split('.').pop()}`;
        const puterFile = await (window as any).puter.fs.write(fileName, file);
        
        // Step 2: Use Puter LLM to analyze the document
        const prompt = `Please read this medical report and return a JSON object with the following structure. Act as an expert in Indian medical and diagnostic standards (e.g., using ICMR guidelines, Indian reference ranges where applicable).
{
  "summary": "A neatly formatted markdown summary of the clinical findings, using bullet points and bold text for easy reading. Ensure you contextualize the findings against standard Indian clinical practices.",
  "raw_text": "A full raw text extraction of all important contents in the document",
  "extracted_values": [
    { "name": "Test Name", "value": "12.3", "range": "10-15", "status": "normal/high/low" }
  ]
}
Return only the raw JSON without any markdown formatting.`;

        const chatHistory = [
          {
            role: 'user',
            content: [
              { type: 'file', puter_path: puterFile.path },
              { type: 'text', text: prompt }
            ]
          }
        ];

        const res = await (window as any).puter.ai.chat(chatHistory);
        await (window as any).puter.fs.delete(puterFile.path);

        let responseText = '';
        if (typeof res === 'string') responseText = res;
        else if (res?.message?.content) responseText = Array.isArray(res.message.content) ? res.message.content.map((c: any) => c.text || '').join('') : res.message.content;
        else responseText = String(res);

        let parsedData = { summary: 'Analysis completed.', raw_text: 'Text extraction unavailable.', extracted_values: [] };
        try {
          const jsonStr = responseText.replace(/```json/g, '').replace(/```/g, '').trim();
          parsedData = JSON.parse(jsonStr);
        } catch (e) {
          console.warn('Failed to parse LLM JSON response:', responseText);
        }

        // Step 3: Save to Database (uploads the physical file AND the AI response)
        uploadRes = await api.reports.createFromLLM({
          file: file,
          patient_id: patientId,
          raw_text: parsedData.raw_text,
          summary: parsedData.summary,
          extracted_values: parsedData.extracted_values,
        });
      } catch (puterErr) {
        console.warn('Puter AI failed, falling back to backend upload:', puterErr);
        // Fallback to standard FastAPI backend upload endpoint
        uploadRes = await api.reports.upload(file, patientId);
      }

      const newReport: Report = {
        id: uploadRes.id || `rep-${Date.now()}`,
        filename: file.name,
        type: uploadRes.report_type || 'Medical Report',
        date: new Date().toISOString().split('T')[0],
        status: uploadRes.status || 'Analyzed',
        labValues: uploadRes.extracted_values || [],
        summary: uploadRes.summary || `Analysis completed for ${file.name}.`,
      };

      setReports((prev) => [newReport, ...prev]);
      setSelectedReport(newReport);
    } catch (err: any) {
      console.error('Failed to analyze report:', err);
      setErrorMsg(`Upload & Analysis failed: ${err.message || 'Error communicating with AI or backend'}`);
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyzeAll = async () => {
    setAnalyzingAll(true);
    setErrorMsg(null);
    try {
      const res = await api.reports.analyzeAll();
      if (res && res.suggestion) {
        setHolisticAnalysis(res.suggestion);
      }
    } catch (err: any) {
      console.error('Failed to run holistic analysis:', err);
      setErrorMsg(`Analysis failed: ${err.message || 'FastAPI server error'}`);
    } finally {
      setAnalyzingAll(false);
    }
  };

  const filteredReports = reports.filter(
    (r) => r.filename.toLowerCase().includes(search.toLowerCase()) || r.type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-background p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between border-b border-border/50 pb-5"
      >
        <div>
          <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-md shadow-violet-500/20">
              <FileText className="h-5 w-5 text-white" />
            </div>
            Medical Reports &amp; OCR Analysis
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            AI-powered document parsing with Puter LLM &amp; Tesseract OCR lab value extraction
          </p>
        </div>
        <div className="flex gap-3">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleAnalyzeAll}
            disabled={analyzingAll || reports.length === 0}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 px-4 py-2 text-xs font-bold text-white shadow-md shadow-blue-500/20 transition-all disabled:opacity-50"
          >
            <BrainCircuit className={`h-4 w-4 ${analyzingAll ? 'animate-pulse' : ''}`} />
            {analyzingAll ? 'Analyzing...' : 'Analyze All Reports'}
          </motion.button>
          <button
            onClick={fetchReports}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl bg-secondary hover:bg-secondary/80 px-3 py-1.5 text-xs font-semibold border text-foreground transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </motion.div>

      {errorMsg && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload & List Column */}
        <div className="space-y-6">
          <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
            <h2 className="font-bold text-foreground flex items-center gap-2 text-sm">
              <UploadCloud className="h-5 w-5 text-violet-500" />
              Upload Medical Report
            </h2>
            <motion.label
              whileHover={{ scale: 1.01 }}
              className="flex flex-col items-center justify-center border-2 border-dashed border-muted-foreground/30 hover:border-violet-500/60 rounded-2xl p-7 cursor-pointer bg-secondary/20 hover:bg-violet-500/5 transition-all text-center group"
            >
              <motion.div
                animate={{ y: uploading ? [-2, 2, -2] : 0 }}
                transition={{ duration: 1, repeat: uploading ? Infinity : 0 }}
              >
                <UploadCloud className="h-12 w-12 text-muted-foreground/50 group-hover:text-violet-400 mb-3 transition-colors" />
              </motion.div>
              <span className="text-sm font-semibold text-foreground">{uploading ? 'Processing with AI...' : 'Click to upload or drag & drop'}</span>
              <span className="text-xs text-muted-foreground mt-1">PDF, PNG, JPG, or TIFF (Up to 20MB)</span>
              <input type="file" onChange={handleFileUpload} className="hidden" accept=".pdf,.png,.jpg,.jpeg,.tiff" />
            </motion.label>
            {uploading && (
              <div className="flex items-center gap-2 text-xs text-violet-400 font-medium">
                <Sparkles className="h-4 w-4 animate-spin" />
                <span>Processing with Puter AI LLM &amp; extracting lab values...</span>
              </div>
            )}
          </div>

          <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-foreground text-sm">Uploaded Reports</h2>
              <span className="text-xs text-muted-foreground">{reports.length} Reports</span>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search reports..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg border bg-background pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
            <div className="space-y-2.5 max-h-[350px] overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center p-6 text-xs text-muted-foreground gap-2">
                  <RefreshCw className="h-4 w-4 animate-spin" /> Loading reports...
                </div>
              ) : filteredReports.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-6 text-xs text-muted-foreground gap-2 border border-dashed rounded-xl">
                  <Inbox className="h-8 w-8 text-muted-foreground/50" />
                  <span>No medical reports uploaded yet.</span>
                </div>
              ) : (
                filteredReports.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReport(r)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      selectedReport?.id === r.id
                        ? 'border-primary bg-primary/10 shadow-sm'
                        : 'hover:bg-secondary/60 bg-card'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-foreground line-clamp-1">{r.filename}</div>
                        <div className="text-[11px] text-muted-foreground">{r.type}</div>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 text-[10px] font-medium border border-emerald-500/20">
                        {r.status}
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-2">{r.date}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Selected Report Column */}
        <div className="lg:col-span-2 space-y-6">
          {selectedReport ? (
            <div className="rounded-2xl border bg-card p-6 space-y-6 shadow-sm">
              <div className="flex items-start justify-between border-b pb-4">
                <div>
                  <h2 className="text-xl font-bold text-foreground">{selectedReport.filename}</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">{selectedReport.type} • Uploaded on {selectedReport.date}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 text-xs font-semibold border border-emerald-500/20">
                    <CheckCircle2 className="h-4 w-4" />
                    OCR Verified
                  </span>
                </div>
              </div>

              <div className="rounded-xl border bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-violet-500/20 p-4 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-violet-400 text-sm">
                  <Sparkles className="h-4 w-4" />
                  AI Clinical Summary
                </div>
                <div className="prose prose-sm dark:prose-invert max-w-none text-xs">
                  <MarkdownRenderer content={selectedReport.summary} />
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  Extracted Lab Parameters
                </h3>
                {selectedReport.labValues.length === 0 ? (
                  <div className="p-4 border rounded-xl text-xs text-muted-foreground">
                    No discrete lab values extracted.
                  </div>
                ) : (
                  <div className="rounded-xl border overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-secondary/60 border-b font-semibold text-muted-foreground">
                        <tr>
                          <th className="p-3">Parameter Name</th>
                          <th className="p-3">Result Value</th>
                          <th className="p-3">Reference Range</th>
                          <th className="p-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {selectedReport.labValues.map((v, idx) => (
                          <tr key={idx} className="hover:bg-secondary/30">
                            <td className="p-3 font-medium text-foreground">{v.name}</td>
                            <td className="p-3 font-semibold text-foreground">{v.value}</td>
                            <td className="p-3 text-muted-foreground">{v.range}</td>
                            <td className="p-3">
                              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-medium text-[11px]">
                                {v.status || 'Normal'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-64 flex-col items-center justify-center rounded-2xl border bg-card p-6 text-muted-foreground text-sm gap-2">
              <Inbox className="h-10 w-10 text-muted-foreground/40" />
              <span>Select a report from the list to view extracted lab values and analysis.</span>
            </div>
          )}
        </div>
      </div>

      {/* Holistic Analysis Modal */}
      <AnimatePresence>
      {holisticAnalysis && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="bg-card w-full max-w-3xl rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] border border-border/60"
          >
            <div className="p-6 border-b border-border/50 flex items-center justify-between bg-gradient-to-r from-blue-600/10 to-indigo-600/10">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-md">
                  <BrainCircuit className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-black text-foreground">Comprehensive AI Health Summary</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">Based on all your uploaded medical reports</p>
                </div>
              </div>
              <button
                onClick={() => setHolisticAnalysis(null)}
                className="p-2 rounded-full hover:bg-secondary text-muted-foreground transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto">
              <MarkdownRenderer content={holisticAnalysis} />
            </div>
            <div className="p-4 border-t border-border/50 bg-secondary/30 flex justify-end">
              <button
                onClick={() => setHolisticAnalysis(null)}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-sm shadow-md hover:from-blue-500 hover:to-indigo-500 transition-all"
              >
                Done
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>
    </div>
  );
}
