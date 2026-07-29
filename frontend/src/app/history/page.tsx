'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  History, 
  Plus, 
  AlertCircle, 
  Calendar, 
  RefreshCw,
  Inbox,
  Clock,
  Zap
} from 'lucide-react';
import { api, ensureAuth } from '@/lib/api';

interface HistoryRecord {
  id: string;
  category: string;
  title: string;
  description: string;
  diagnosedDate: string;
  status: string;
}

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [filter, setFilter] = useState<string>('All');
  const [loading, setLoading] = useState(true);
  const [patientId, setPatientId] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [newRec, setNewRec] = useState({ category: 'Condition', title: '', description: '', date: '' });

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      await ensureAuth();
      let pid = patientId;
      const pList = await api.patients.list();
      if (pList.items && pList.items.length > 0) {
        pid = pList.items[0].id;
      } else {
        const newP = await api.patients.create({
          full_name: 'Patient User',
          gender: 'male',
          date_of_birth: '1990-01-01',
          blood_group: 'O+',
        });
        pid = newP.id;
      }
      setPatientId(pid);

      const res = await api.patients.getHistory(pid);
      if (res.items && Array.isArray(res.items)) {
        const mapped: HistoryRecord[] = res.items.map((i: any) => ({
          id: i.id,
          category: i.category || 'Condition',
          title: i.condition_name || i.title || 'Medical Record',
          description: i.notes || i.description || 'Clinical history entry.',
          diagnosedDate: i.diagnosis_date || (i.created_at ? i.created_at.split('T')[0] : 'Recently'),
          status: i.status || 'Active',
        }));
        setRecords(mapped);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRec.title) return;

    try {
      await ensureAuth();
      let pid = patientId;
      if (!pid) {
        const pList = await api.patients.list();
        if (pList.items && pList.items.length > 0) {
          pid = pList.items[0].id;
        } else {
          const newP = await api.patients.create({
            full_name: 'Patient User',
            gender: 'male',
            date_of_birth: '1990-01-01',
            blood_group: 'O+',
          });
          pid = newP.id;
        }
        setPatientId(pid);
      }

      await api.patients.addHistory(pid, {
        category: newRec.category,
        condition_name: newRec.title,
        notes: newRec.description || 'Clinical notes recorded.',
        diagnosis_date: newRec.date || new Date().toISOString().split('T')[0],
      });

      fetchHistory();
    } catch (err) {
      console.error('Failed to add medical history:', err);
    }

    setNewRec({ category: 'Condition', title: '', description: '', date: '' });
    setShowModal(false);
  };

  const filteredRecords = filter === 'All' ? records : records.filter((r) => r.category.toLowerCase().includes(filter.toLowerCase()));

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
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 shadow-md shadow-amber-500/20">
              <History className="h-5 w-5 text-white" />
            </div>
            Medical History Timeline
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Chronological audit trail of diagnoses, allergies, surgeries &amp; vaccinations
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchHistory}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl bg-secondary hover:bg-secondary/80 px-3 py-2 text-xs font-semibold border text-foreground transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white hover:from-amber-400 hover:to-orange-400 px-4 py-2 text-xs font-bold transition-all shadow-md shadow-amber-500/20"
          >
            <Plus className="h-4 w-4" />
            Add Medical Event
          </motion.button>
        </div>
      </motion.div>

      {/* Filter Tabs */}
      <div className="flex gap-2 flex-wrap">
        {['All', 'Condition', 'Allergy', 'Surgery', 'Vaccination'].map((cat) => (
          <motion.button
            key={cat}
            onClick={() => setFilter(cat)}
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.96 }}
            className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all border ${
              filter === cat
                ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white border-transparent shadow-md shadow-amber-500/20'
                : 'bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground border-border/50'
            }`}
          >
            {cat}s
          </motion.button>
        ))}
      </div>

      {/* Timeline List */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-xs text-muted-foreground gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" /> Fetching history timeline from FastAPI...
        </div>
      ) : filteredRecords.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-xs text-muted-foreground gap-2 border border-dashed rounded-2xl bg-card max-w-4xl">
          <Inbox className="h-10 w-10 text-muted-foreground/40" />
          <span className="font-medium text-foreground">No medical records found in FastAPI database.</span>
          <p className="text-[11px] text-muted-foreground">Click "Add Medical Event" to log a diagnosis, allergy, or surgery.</p>
        </div>
      ) : (
        <div className="space-y-4 max-w-4xl">
          <AnimatePresence>
          {filteredRecords.map((r, idx) => (
            <motion.div
              key={r.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ delay: idx * 0.06, type: 'spring', stiffness: 300, damping: 28 }}
              className="relative pl-7 border-l-2 border-amber-500/30 space-y-2"
            >
              <div className="absolute -left-2 top-2 h-4 w-4 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 ring-4 ring-background shadow-md" />
              <div className="rounded-2xl border border-border/60 bg-card/80 p-5 space-y-3 shadow-sm hover:shadow-md hover:border-border transition-all">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-lg bg-amber-500/10 text-amber-500 text-[10px] font-black border border-amber-500/20">
                        {r.category}
                      </span>
                      <h3 className="font-bold text-foreground text-base">{r.title}</h3>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5" />
                      <span>Recorded on {r.diagnosedDate}</span>
                    </div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                    {r.status}
                  </span>
                </div>
                <p className="text-xs text-foreground/80 leading-relaxed border-t border-border/50 pt-2">
                  {r.description}
                </p>
              </div>
            </motion.div>
          ))}
          </AnimatePresence>
        </div>
      )}

      {/* Add Record Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <History className="h-5 w-5 text-indigo-500" />
              Add Medical Record Event to FastAPI
            </h2>
            <form onSubmit={handleAddRecord} className="space-y-3 text-xs">
              <div>
                <label className="font-medium text-foreground">Category</label>
                <select
                  value={newRec.category}
                  onChange={(e) => setNewRec({ ...newRec, category: e.target.value })}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  <option value="Condition">Medical Condition</option>
                  <option value="Allergy">Allergy / Sensitivity</option>
                  <option value="Surgery">Surgical Procedure</option>
                  <option value="Vaccination">Vaccination / Immunization</option>
                </select>
              </div>
              <div>
                <label className="font-medium text-foreground">Title / Diagnosis Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Hypertension"
                  value={newRec.title}
                  onChange={(e) => setNewRec({ ...newRec, title: e.target.value })}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
              <div>
                <label className="font-medium text-foreground">Date</label>
                <input
                  type="date"
                  value={newRec.date}
                  onChange={(e) => setNewRec({ ...newRec, date: e.target.value })}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
              <div>
                <label className="font-medium text-foreground">Clinical Notes / Details</label>
                <textarea
                  rows={3}
                  placeholder="Additional context or treatment summary..."
                  value={newRec.description}
                  onChange={(e) => setNewRec({ ...newRec, description: e.target.value })}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border px-4 py-1.5 text-xs font-medium hover:bg-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs font-medium hover:bg-primary/90"
                >
                  Save Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
