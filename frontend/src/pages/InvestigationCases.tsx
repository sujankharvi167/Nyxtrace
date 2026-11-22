import React, { useEffect, useState } from 'react';
import { BriefcaseBusiness, Loader2, Plus } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';
import { api } from '@/services/api';
import type { InvestigationCase } from '@/types';

export const InvestigationCases: React.FC = () => {
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [selected, setSelected] = useState<InvestigationCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'critical' | 'high' | 'medium' | 'low'>('medium');
  const [primaryTransaction, setPrimaryTransaction] = useState('');
  const [newTransaction, setNewTransaction] = useState('');
  const [note, setNote] = useState('');

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.risk.cases({ page: 1, pageSize: 100 });
      setCases(response.data?.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load investigation cases.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const openCase = async (caseId: string) => {
    try {
      const response = await api.risk.case(caseId);
      setSelected(response.data ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load case details.');
    }
  };

  const createCase = async () => {
    if (!title.trim()) {
      setError('Case title is required.');
      return;
    }
    setError(null);
    try {
      const response = await api.risk.createCase({
        title: title.trim(),
        description: description.trim(),
        priority,
        status: 'open',
        primary_transaction_id: primaryTransaction.trim() || undefined,
        transaction_ids: primaryTransaction.trim() ? [primaryTransaction.trim()] : [],
      });
      setSelected(response.data ?? null);
      setCreating(false);
      setTitle('');
      setDescription('');
      setPrimaryTransaction('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create case.');
    }
  };

  const updateSelected = async (updates: {
    priority?: 'critical' | 'high' | 'medium' | 'low';
    status?: 'open' | 'under_review' | 'escalated' | 'resolved' | 'closed';
  }) => {
    if (!selected) return;
    try {
      const response = await api.risk.updateCase(selected.case_id, updates);
      setSelected(response.data ?? null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update case.');
    }
  };

  const addTransaction = async () => {
    if (!selected || !newTransaction.trim()) return;
    try {
      const response = await api.risk.addCaseTransaction(selected.case_id, newTransaction.trim());
      setSelected(response.data ?? null);
      setNewTransaction('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add transaction.');
    }
  };

  const removeTransaction = async (transactionId: string) => {
    if (!selected) return;
    try {
      const response = await api.risk.removeCaseTransaction(selected.case_id, transactionId);
      setSelected(response.data ?? null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove transaction.');
    }
  };

  const addNote = async () => {
    if (!selected || !note.trim()) return;
    try {
      const response = await api.risk.addCaseNote(selected.case_id, note.trim());
      setSelected(response.data ?? null);
      setNote('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add note.');
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Investigation Cases"
        subtitle="Persistent analyst case management and evidence tracking"
        actions={
          <button type="button" className="btn-primary" onClick={() => setCreating(value => !value)}>
            <Plus className="w-4 h-4" /> New case
          </button>
        }
      />

      {error && <div className="card p-3 text-xs text-red-300" style={{ borderLeft: '2px solid #ef4444' }}>{error}</div>}

      {creating && (
        <div className="card p-5 space-y-3">
          <p className="section-label">Create investigation case</p>
          <input value={title} onChange={event => setTitle(event.target.value)} placeholder="Case title" className="case-input" />
          <textarea value={description} onChange={event => setDescription(event.target.value)} placeholder="Case description" className="case-input min-h-24" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select value={priority} onChange={event => setPriority(event.target.value as typeof priority)} className="case-input">
              <option value="critical">Critical priority</option>
              <option value="high">High priority</option>
              <option value="medium">Medium priority</option>
              <option value="low">Low priority</option>
            </select>
            <input value={primaryTransaction} onChange={event => setPrimaryTransaction(event.target.value)} placeholder="Primary transaction ID (optional)" className="case-input" />
          </div>
          <button type="button" className="btn-primary" onClick={createCase}>Create case</button>
        </div>
      )}

      {loading ? (
        <div className="card p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400" /></div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
          <div className="card p-4">
            <p className="section-label mb-3">Cases</p>
            {cases.length ? (
              <div className="space-y-2">
                {cases.map(item => (
                  <button
                    type="button"
                    key={item.case_id}
                    onClick={() => void openCase(item.case_id)}
                    className="w-full text-left rounded-lg p-3"
                    style={{
                      backgroundColor: selected?.case_id === item.case_id ? 'rgba(59,130,246,0.1)' : '#141d35',
                      border: `1px solid ${selected?.case_id === item.case_id ? '#3b82f6' : '#1e2d4a'}`,
                    }}
                  >
                    <p className="text-xs text-slate-200 font-medium">{item.title}</p>
                    <p className="text-[10px] text-slate-500 mt-1 font-mono">{item.case_id}</p>
                    <p className="text-[10px] text-slate-400 mt-2">{item.priority} · {item.status.replace('_', ' ')}</p>
                  </button>
                ))}
              </div>
            ) : <EmptyState icon={<BriefcaseBusiness className="w-6 h-6" />} title="No investigation cases" description="Create a case from a suspicious transaction or analyst investigation." />}
          </div>

          <div className="card p-5">
            {!selected ? (
              <EmptyState icon={<BriefcaseBusiness className="w-7 h-7" />} title="No case selected" description="Select or create an investigation case." />
            ) : (
              <div className="space-y-5">
                <div>
                  <p className="section-label">{selected.case_id}</p>
                  <h2 className="text-lg font-semibold text-slate-100 mt-2">{selected.title}</h2>
                  <p className="text-xs text-slate-400 mt-2">{selected.description || 'No description provided.'}</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <select value={selected.priority} onChange={event => updateSelected({ priority: event.target.value as typeof selected.priority })} className="case-input">
                    <option value="critical">Critical priority</option>
                    <option value="high">High priority</option>
                    <option value="medium">Medium priority</option>
                    <option value="low">Low priority</option>
                  </select>
                  <select value={selected.status} onChange={event => updateSelected({ status: event.target.value as typeof selected.status })} className="case-input">
                    <option value="open">Open</option>
                    <option value="under_review">Under review</option>
                    <option value="escalated">Escalated</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>

                <div>
                  <p className="section-label mb-3">Associated transactions</p>
                  <div className="flex gap-2 mb-3">
                    <input value={newTransaction} onChange={event => setNewTransaction(event.target.value)} placeholder="Transaction ID" className="case-input flex-1" />
                    <button type="button" className="btn-primary" onClick={addTransaction}>Add</button>
                  </div>
                  {selected.associated_transaction_ids?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {selected.associated_transaction_ids.map(transactionId => (
                        <span key={transactionId} className="text-xs font-mono px-2 py-1 rounded" style={{ backgroundColor: '#141d35', border: '1px solid #263354' }}>
                          {transactionId}
                          <button type="button" className="ml-2 text-red-400" onClick={() => removeTransaction(transactionId)}>×</button>
                        </span>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-500">No associated transactions.</p>}
                </div>

                <div>
                  <p className="section-label mb-3">Notes</p>
                  <textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add an investigation note" className="case-input min-h-20" />
                  <button type="button" className="btn-primary mt-3" onClick={addNote}>Add note</button>
                  {selected.notes?.length ? (
                    <div className="mt-4 space-y-2">
                      {selected.notes.map(item => (
                        <div key={item.note_id} className="rounded-lg p-3" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                          <p className="text-xs text-slate-300">{item.content}</p>
                          <p className="text-[10px] text-slate-500 mt-2">{item.author ? `${item.author} · ` : ''}{item.created_at}</p>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-500 mt-3">No investigation notes.</p>}
                </div>

                <div>
                  <p className="section-label mb-3">Activity history</p>
                  {selected.activity?.length ? (
                    <div className="space-y-2">
                      {[...selected.activity].reverse().map(item => (
                        <div key={item.activity_id} className="text-xs flex justify-between gap-3 py-2" style={{ borderBottom: '1px solid #1e2d4a' }}>
                          <span className="text-slate-300">{item.details}</span>
                          <span className="text-slate-500 whitespace-nowrap">{item.created_at}</span>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-500">No activity recorded.</p>}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
