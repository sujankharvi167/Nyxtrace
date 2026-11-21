import React, { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import { Upload, FileText, Database, Info, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';
import { api } from '@/services/api';
import type { APIResponse, ProcessedDataset } from '@/types';

const MLIntelligencePanel = lazy(() =>
  import('@/components/MLIntelligencePanel').then(module => ({
    default: module.MLIntelligencePanel,
  })),
);

type UploadState = 'idle' | 'hovering' | 'selected';
const MAX_FILE_SIZE_BYTES = 750 * 1024 * 1024;
const MAX_TOTAL_SIZE_BYTES = 800 * 1024 * 1024;
const MAX_FILES = 3;

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

function validateSelectedFiles(files: File[]): string | null {
  if (files.length > MAX_FILES) {
    return `A maximum of ${MAX_FILES} CSV files is allowed.`;
  }
  const oversized = files.find(file => file.size > MAX_FILE_SIZE_BYTES);
  if (oversized) {
    return `${oversized.name} exceeds the 750 MB individual file limit.`;
  }
  const totalSize = files.reduce((total, file) => total + file.size, 0);
  if (totalSize > MAX_TOTAL_SIZE_BYTES) {
    return 'The combined upload exceeds the 800 MB total size limit.';
  }
  return null;
}

export const TransactionAnalysis: React.FC = () => {
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dataset, setDataset] = useState<ProcessedDataset | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.analysis.getDataset().then((response) => {
      const result = response as APIResponse<ProcessedDataset>;
      if (result.data) setDataset(result.data);
    }).catch(() => undefined);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files).filter(file => file.name.toLowerCase().endsWith('.csv'));
    if (files.length) {
      const validationError = validateSelectedFiles(files);
      if (validationError) {
        setSelectedFiles([]);
        setUploadState('idle');
        setError(validationError);
      } else {
        setSelectedFiles(files.slice(0, MAX_FILES));
        setUploadState('selected');
        setError(null);
      }
    } else {
      setUploadState('idle');
      setError('Please select CSV files only.');
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter(file => file.name.toLowerCase().endsWith('.csv'));
    if (files.length) {
      const validationError = validateSelectedFiles(files);
      if (validationError) {
        setSelectedFiles([]);
        setUploadState('idle');
        setError(validationError);
      } else {
        setSelectedFiles(files.slice(0, MAX_FILES));
        setUploadState('selected');
        setError(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFiles.length) return;
    const validationError = validateSelectedFiles(selectedFiles);
    if (validationError) {
      setError(validationError);
      return;
    }
    setUploading(true);
    setProgress(0);
    setError(null);
    try {
      const response = await api.analysis.uploadDataset(selectedFiles, setProgress) as APIResponse<ProcessedDataset>;
      if (response.data) setDataset(response.data);
      setUploadState('selected');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dataset upload failed.');
    } finally {
      setUploading(false);
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
            <p className="text-sm font-medium text-amber-300">Stage 2 · Dataset Processing</p>
            <p className="text-xs text-slate-400 mt-1">
              Upload and preprocess Elliptic++ CSV files below. Stage 3 compares supervised models using licit
              and illicit labels; unknown labels are never treated as licit.
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
              {uploadState === 'selected' && selectedFiles.length ? (
                <div className="space-y-3">
                  <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
                  <div className="space-y-1">
                    {selectedFiles.map(file => (
                      <div key={file.name}>
                        <p className="text-sm font-medium text-slate-200">{file.name}</p>
                        <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    ))}
                  </div>
                  {uploading ? (
                    <div className="max-w-xs mx-auto">
                      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div className="h-full bg-blue-500 transition-all" style={{ width: `${progress}%` }} />
                      </div>
                      <p className="text-xs text-blue-400 mt-2 flex items-center justify-center gap-1.5">
                        <Loader2 className="w-3 h-3 animate-spin" /> Processing {progress}%
                      </p>
                    </div>
                  ) : (
                    <button onClick={handleUpload} className="btn-primary mx-auto">
                      <Upload className="w-4 h-4" />
                      Upload &amp; Process
                    </button>
                  )}
                  <button
                    onClick={() => { setSelectedFiles([]); setUploadState('idle'); setProgress(0); }}
                    className="text-xs text-slate-500 hover:text-slate-300 underline"
                    disabled={uploading}
                  >
                    Remove files
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
                    <input type="file" accept=".csv" multiple onChange={handleFileChange} className="hidden" />
                  </label>
                  <p className="text-xs text-slate-600">Accepted: CSV · 750 MB per file · 800 MB total</p>
                </div>
              )}
            </div>
            {error && (
              <div className="mt-4 flex items-start gap-2 rounded-lg p-3" style={{ backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-red-300">{error}</p>
              </div>
            )}
          </div>

          {/* Dataset information */}
          <div className="card p-5">
            <p className="section-label mb-4">Dataset Information</p>
            {!dataset ? (
              <EmptyState
                icon={<Database className="w-6 h-6" />}
                title="No Dataset Loaded"
                description="Upload a CSV file to view row count, column names, data types, and missing-value statistics."
              />
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    ['Transactions', dataset.total_transactions],
                    ['Edges', dataset.total_edges],
                    ['Missing Values', dataset.missing_values],
                    ['Duplicate Rows', dataset.duplicate_rows],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-lg p-3" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                      <p className="text-[0.65rem] uppercase tracking-wider text-slate-500">{label}</p>
                      <p className="text-lg font-semibold text-slate-200 mt-1">{Number(value).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
                {dataset.files.map(file => (
                  <div key={file.filename} className="rounded-lg overflow-hidden" style={{ border: '1px solid #1e2d4a' }}>
                    <div className="flex items-center justify-between p-3" style={{ backgroundColor: '#141d35' }}>
                      <div>
                        <p className="text-sm text-slate-200">{file.filename}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{file.role} · {file.processed_rows.toLocaleString()} rows · {file.total_columns} columns</p>
                      </div>
                      <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Valid</span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-slate-500" style={{ borderBottom: '1px solid #1e2d4a' }}>
                            <th className="text-left p-2.5">Column</th>
                            <th className="text-left p-2.5">Type</th>
                            <th className="text-right p-2.5">Missing</th>
                            <th className="text-right p-2.5">Unique</th>
                          </tr>
                        </thead>
                        <tbody>
                          {file.column_info.map(column => (
                            <tr key={column.name} style={{ borderBottom: '1px solid #1e2d4a' }}>
                              <td className="p-2.5 text-slate-300 font-mono">{column.name}</td>
                              <td className="p-2.5 text-slate-500">{column.dtype}</td>
                              <td className="p-2.5 text-right text-slate-400">{column.missing}</td>
                              <td className="p-2.5 text-right text-slate-400">{column.unique}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Transaction summary and validation */}
          <div className="card p-5">
            <p className="section-label mb-4">Transaction Summary</p>
            {!dataset ? (
              <EmptyState
                icon={<FileText className="w-6 h-6" />}
                title="No Summary Available"
                description="A statistical summary of transactions will appear here after processing."
              />
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  {(['licit', 'illicit', 'unknown'] as const).map(label => (
                    <div key={label} className="rounded-lg p-3" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                      <p className="text-xs capitalize text-slate-500">{label}</p>
                      <p className="text-base font-semibold text-slate-200 mt-1">{dataset.label_counts[label]?.toLocaleString() ?? 0}</p>
                    </div>
                  ))}
                </div>
                {dataset.files.map(file => (
                  <div key={file.filename}>
                    <p className="text-xs font-medium text-slate-300 mb-2">{file.filename} preview</p>
                    {file.preview.length ? (
                      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid #1e2d4a' }}>
                        <table className="w-full text-xs">
                          <thead>
                            <tr style={{ borderBottom: '1px solid #1e2d4a' }}>
                              {file.columns.slice(0, 8).map(column => (
                                <th key={column} className="text-left p-2.5 text-slate-500 whitespace-nowrap">{column}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {file.preview.slice(0, 5).map((row, index) => (
                              <tr key={index} style={{ borderBottom: '1px solid #1e2d4a' }}>
                                {file.columns.slice(0, 8).map(column => (
                                  <td key={column} className="p-2.5 text-slate-400 whitespace-nowrap">
                                    {row[column] === null || row[column] === undefined ? '—' : String(row[column]).slice(0, 24)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">No preview rows available.</p>
                    )}
                  </div>
                ))}
              </div>
            )}
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
              <div className="rounded-lg p-3 text-center" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
                <p className="text-xs text-slate-400">Validation &amp; preprocessing</p>
                <p className="text-xs text-emerald-400 mt-1">{dataset ? 'Complete' : 'Ready'}</p>
              </div>
              <p className="text-xs text-center text-slate-600 mt-2">Stage 3 training is available below</p>
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
      <Suspense fallback={<div className="card p-6 text-center text-xs text-slate-500">Loading ML intelligence panel…</div>}>
        <MLIntelligencePanel />
      </Suspense>
    </div>
  );
};
