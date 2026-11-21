import React, { useCallback, useState } from 'react';
import { Upload, FileText, Database, Info, CheckCircle2, AlertCircle } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';

type UploadState = 'idle' | 'hovering' | 'selected';

const SUPPORTED_DATASETS = [
  {
    name: 'Elliptic++',
    files: 'txs_features.csv · txs_classes.csv · txs_edgelist.csv',
    status: 'Primary',
    statusColor: '#60a5fa',
    statusBg: 'rgba(59,130,246,0.1)',
  },
  {
    name: 'IBM AMLSim',
    files: 'transactions.csv (synthetic banking)',
    status: 'Planned',
    statusColor: '#64748b',
    statusBg: 'rgba(100,116,139,0.1)',
  },
  {
    name: 'Custom CSV',
    files: 'User-provided transaction data',
    status: 'Supported',
    statusColor: '#34d399',
    statusBg: 'rgba(16,185,129,0.1)',
  },
];

const CONFIG_ROWS = [
  { label: 'Feature Engineering', value: 'Auto-detect' },
  { label: 'Label Column',         value: 'Auto-detect' },
  { label: 'Graph Construction',   value: 'From edgelist' },
];

export const TransactionAnalysis: React.FC = () => {
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file?.name.endsWith('.csv')) {
      setSelectedFile(file);
      setUploadState('selected');
    } else {
      setUploadState('idle');
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setUploadState('selected');
    }
  };

  const dropBorder = uploadState === 'hovering' ? '#3b82f6' : uploadState === 'selected' ? 'rgba(16,185,129,0.5)' : '#263354';
  const dropBg    = uploadState === 'hovering' ? 'rgba(59,130,246,0.05)' : uploadState === 'selected' ? 'rgba(16,185,129,0.05)' : 'rgba(20,29,53,0.3)';

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Transaction Analysis"
        subtitle="Dataset upload and preprocessing workspace"
      />

      {/* Stage notice */}
      <div className="card p-4" style={{ borderLeft: '2px solid #f59e0b' }}>
        <div className="flex items-start gap-3">
          <Info className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-300">Stage 2 Feature</p>
            <p className="text-xs text-slate-400 mt-1">
              Full dataset processing, validation, and feature engineering will be implemented in Stage 2.
              The upload interface below is prepared for integration with the backend pipeline.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload + info panel */}
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-5">
            <p className="section-label mb-4">Dataset Upload</p>
            <div
              onDragOver={e => { e.preventDefault(); setUploadState('hovering'); }}
              onDragLeave={() => { if (uploadState !== 'selected') setUploadState('idle'); }}
              onDrop={handleDrop}
              className="relative rounded-xl p-10 text-center transition-all duration-150"
              style={{ border: `2px dashed ${dropBorder}`, backgroundColor: dropBg }}
            >
              {uploadState === 'selected' && selectedFile ? (
                <div className="space-y-3">
                  <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
                  <div>
                    <p className="text-sm font-medium text-slate-200">{selectedFile.name}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <div className="flex items-center justify-center gap-1.5 text-xs text-amber-400">
                    <AlertCircle className="w-3 h-3" />
                    Backend processing available in Stage 2
                  </div>
                  <button
                    onClick={() => { setSelectedFile(null); setUploadState('idle'); }}
                    className="text-xs text-slate-500 hover:text-slate-300 underline"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="w-10 h-10 mx-auto text-slate-500" />
                  <div>
                    <p className="text-sm font-medium text-slate-300">Drop your CSV file here</p>
                    <p className="text-xs text-slate-500 mt-1">or</p>
                  </div>
                  <label className="btn-primary cursor-pointer">
                    <FileText className="w-4 h-4" />
                    Browse File
                    <input type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
                  </label>
                  <p className="text-xs text-slate-600">Accepted: .csv</p>
                </div>
              )}
            </div>
          </div>

          {/* Dataset info placeholder */}
          <div className="card p-5">
            <p className="section-label mb-4">Dataset Information</p>
            <EmptyState
              icon={<Database className="w-6 h-6" />}
              title="No Dataset Loaded"
              description="Upload a CSV file to view row count, column names, data types, and missing-value statistics."
            />
          </div>

          {/* Transaction summary placeholder */}
          <div className="card p-5">
            <p className="section-label mb-4">Transaction Summary</p>
            <EmptyState
              icon={<FileText className="w-6 h-6" />}
              title="No Summary Available"
              description="A statistical summary of transactions will appear here after processing (Stage 2)."
            />
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Config */}
          <div className="card p-5">
            <p className="section-label mb-3">Analysis Configuration</p>
            <div className="space-y-0">
              {CONFIG_ROWS.map(({ label, value }) => (
                <div
                  key={label}
                  className="flex items-center justify-between py-2.5"
                  style={{ borderBottom: '1px solid #1e2d4a' }}
                >
                  <span className="text-xs text-slate-400">{label}</span>
                  <span className="text-xs text-slate-600 font-mono">{value}</span>
                </div>
              ))}
            </div>
            <div className="pt-4">
              <button disabled className="btn-primary w-full opacity-40 cursor-not-allowed">
                Run Analysis
              </button>
              <p className="text-xs text-center text-slate-600 mt-2">Available in Stage 2</p>
            </div>
          </div>

          {/* Supported datasets */}
          <div className="card p-5">
            <p className="section-label mb-3">Supported Datasets</p>
            <div className="space-y-3">
              {SUPPORTED_DATASETS.map(ds => (
                <div
                  key={ds.name}
                  className="p-3 rounded-lg"
                  style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium text-slate-200">{ds.name}</span>
                    <span
                      className="font-medium flex-shrink-0"
                      style={{
                        fontSize: '0.6rem',
                        padding: '1px 6px',
                        borderRadius: '3px',
                        backgroundColor: ds.statusBg,
                        color: ds.statusColor,
                      }}
                    >
                      {ds.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{ds.files}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Elliptic++ note */}
          <div className="card p-4" style={{ border: '1px solid #263354' }}>
            <p className="text-xs text-slate-500 leading-relaxed">
              <span className="text-slate-300 font-medium">Note:</span> Elliptic++ contains{' '}
              <span className="text-slate-300">cryptocurrency</span> transaction data, not conventional bank
              records. Column schemas are inspected at preprocessing time — no hardcoded assumptions are made.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
