import React, { useEffect, useState } from 'react';
import { Download, FileText, Loader2, Search } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/components/ui';
import { api } from '@/services/api';
import type {
  GeneratedReport,
  InvestigationCase,
  ReportType,
} from '@/types';

export const Reports: React.FC = () => {
  const [reportTypes, setReportTypes] = useState<ReportType[]>([]);
  const [reports, setReports] = useState<GeneratedReport[]>([]);
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [selectedType, setSelectedType] = useState<ReportType['type']>('transaction_summary');
  const [reportName, setReportName] = useState('');
  const [caseId, setCaseId] = useState('');
  const [transactionIds, setTransactionIds] = useState('');
  const [selectedReport, setSelectedReport] = useState<GeneratedReport | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [typesResponse, reportsResponse, casesResponse] = await Promise.all([
        api.reports.types(),
        api.reports.list({ page: 1, pageSize: 100 }),
        api.risk.cases({ page: 1, pageSize: 100 }),
      ]);
      setReportTypes(typesResponse.data?.types ?? []);
      setReports(reportsResponse.data?.items ?? []);
      setCases(casesResponse.data?.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load report data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const generateReport = async () => {
    if (!reportName.trim()) {
      setError('Enter a report name.');
      return;
    }
    if (selectedType === 'investigation_brief' && !caseId) {
      setError('Select an investigation case for an Investigation Brief.');
      return;
    }
    const transactionIdList = transactionIds
      .split(/[,\n\s]+/)
      .map(value => value.trim())
      .filter(Boolean);
    if (transactionIdList.length > 500) {
      setError('A maximum of 500 transaction IDs is supported per report.');
      return;
    }

    setGenerating(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await api.reports.generate({
        report_name: reportName.trim(),
        report_type: selectedType,
        investigation_case_id: selectedType === 'investigation_brief' ? caseId : undefined,
        transaction_ids: transactionIdList,
      });
      if (response.data) {
        setSelectedReport(response.data);
        setSuccess(`Generated ${response.data.report_name}.`);
        await refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate report.');
    } finally {
      setGenerating(false);
    }
  };

  const inspectReport = async (reportId: string) => {
    setError(null);
    try {
      const response = await api.reports.metadata(reportId);
      setSelectedReport(response.data ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load report metadata.');
    }
  };

  const filteredReports = reports.filter(report => {
    if (!search.trim()) return true;
    const needle = search.trim().toLowerCase();
    return (
      report.report_name.toLowerCase().includes(needle)
      || report.report_id.toLowerCase().includes(needle)
      || report.report_title.toLowerCase().includes(needle)
    );
  });

  const selectedTypeData = reportTypes.find(item => item.type === selectedType);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Investigation Reports"
        subtitle="Generate professional PDF reports from persisted Stage 2–5 evidence"
      />

      {error && (
        <div className="card p-3 text-xs text-red-300" style={{ borderLeft: '2px solid #ef4444' }}>{error}</div>
      )}
      {success && (
        <div className="card p-3 text-xs text-emerald-300" style={{ borderLeft: '2px solid #10b981' }}>{success}</div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
        <div className="card p-5 space-y-4">
          <p className="section-label">Generate report</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-2">
              <span className="text-xs text-slate-500">Report name</span>
              <input
                value={reportName}
                onChange={event => setReportName(event.target.value)}
                placeholder="e.g. Elliptic++ transaction review"
                className="report-input"
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs text-slate-500">Report type</span>
              <select
                value={selectedType}
                onChange={event => setSelectedType(event.target.value as ReportType['type'])}
                className="report-input"
              >
                {reportTypes.map(item => (
                  <option key={item.type} value={item.type}>{item.title}</option>
                ))}
              </select>
            </label>
          </div>

          {selectedTypeData && (
            <p className="text-xs text-slate-500">{selectedTypeData.description}</p>
          )}

          {selectedType === 'investigation_brief' && (
            <label className="block space-y-2">
              <span className="text-xs text-slate-500">Investigation case</span>
              <select value={caseId} onChange={event => setCaseId(event.target.value)} className="report-input">
                <option value="">Select a case</option>
                {cases.map(item => (
                  <option key={item.case_id} value={item.case_id}>
                    {item.case_id} · {item.title}
                  </option>
                ))}
              </select>
            </label>
          )}

          {['ml_detection', 'network_analysis', 'risk_dashboard', 'compliance_export'].includes(selectedType) && (
            <label className="block space-y-2">
              <span className="text-xs text-slate-500">Relevant transaction IDs (optional)</span>
              <textarea
                value={transactionIds}
                onChange={event => setTransactionIds(event.target.value)}
                placeholder="Separate IDs with commas or new lines"
                className="report-input min-h-20"
              />
            </label>
          )}

          <button type="button" className="btn-primary" disabled={generating} onClick={generateReport}>
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            {generating ? 'Generating PDF' : 'Generate PDF'}
          </button>
        </div>

        <div className="card p-5">
          <p className="section-label mb-4">Report details</p>
          {selectedReport ? (
            <div className="space-y-2">
              <Detail label="Report ID" value={selectedReport.report_id} mono />
              <Detail label="Name" value={selectedReport.report_name} />
              <Detail label="Type" value={selectedReport.report_title} />
              <Detail label="Status" value={selectedReport.status} />
              <Detail label="Created" value={selectedReport.created_at} />
              <Detail label="Dataset batch" value={selectedReport.dataset_batch ?? 'Unavailable'} mono />
              <Detail label="Model batch" value={selectedReport.model_batch ?? 'Unavailable'} mono />
              <Detail label="Graph batch" value={selectedReport.graph_batch ?? 'Unavailable'} mono />
              <Detail label="Case" value={selectedReport.investigation_case_id ?? 'Not applicable'} mono />
              {selectedReport.error_message && (
                <p className="text-xs text-red-300 pt-2">{selectedReport.error_message}</p>
              )}
              {selectedReport.status === 'completed' && (
                <a
                  href={api.reports.downloadUrl(selectedReport.report_id)}
                  download
                  className="btn-primary mt-3"
                >
                  <Download className="w-4 h-4" /> Download PDF
                </a>
              )}
            </div>
          ) : (
            <EmptyState
              icon={<FileText className="w-6 h-6" />}
              title="No report selected"
              description="Generate a report or select a report from history."
            />
          )}
        </div>
      </div>

      <div className="card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 pb-4 mb-4" style={{ borderBottom: '1px solid #1e2d4a' }}>
          <p className="section-label">Generated reports</p>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search report name or ID"
              className="report-input pl-10"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400" /></div>
        ) : filteredReports.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 text-left">
                  <th className="py-2 pr-4">Report</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Created</th>
                  <th className="py-2 pr-4">Dataset batch</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredReports.map(report => (
                  <tr key={report.report_id} style={{ borderTop: '1px solid #1e2d4a' }}>
                    <td className="py-3 pr-4">
                      <p className="text-slate-200">{report.report_name}</p>
                      <p className="text-[10px] text-slate-500 font-mono mt-1">{report.report_id}</p>
                    </td>
                    <td className="py-3 pr-4 text-slate-400">{report.report_title}</td>
                    <td className="py-3 pr-4 text-slate-400 whitespace-nowrap">{report.created_at}</td>
                    <td className="py-3 pr-4 font-mono text-slate-400 whitespace-nowrap">{report.dataset_batch ?? 'Unavailable'}</td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={report.status} />
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-3">
                        <button type="button" className="text-blue-400 hover:text-blue-300" onClick={() => inspectReport(report.report_id)}>Details</button>
                        {report.status === 'completed' && (
                          <a className="text-emerald-400 hover:text-emerald-300" href={api.reports.downloadUrl(report.report_id)} download>
                            Download
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={<FileText className="w-7 h-7" />}
            title="No Reports Generated"
            description="Generate a report using available dataset, ML, graph, risk, or case evidence."
          />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {reportTypes.map(item => (
          <button
            type="button"
            key={item.type}
            onClick={() => setSelectedType(item.type)}
            className="card p-5 text-left hover:border-blue-500 transition-colors"
          >
            <FileText className="w-5 h-5 text-blue-400 mb-3" />
            <p className="text-sm font-medium text-slate-200">{item.title}</p>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">{item.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
};

const Detail: React.FC<{ label: string; value: string; mono?: boolean }> = ({ label, value, mono }) => (
  <div className="flex items-start justify-between gap-3 py-2" style={{ borderBottom: '1px solid #1e2d4a' }}>
    <span className="text-xs text-slate-500">{label}</span>
    <span className={`text-xs text-right text-slate-200 ${mono ? 'font-mono break-all' : ''}`}>{value}</span>
  </div>
);

const StatusBadge: React.FC<{ status: GeneratedReport['status'] }> = ({ status }) => (
  <span className={`text-[0.65rem] px-2 py-1 rounded border ${
    status === 'completed'
      ? 'text-emerald-300 border-emerald-900'
      : status === 'failed'
        ? 'text-red-300 border-red-900'
        : 'text-amber-300 border-amber-900'
  }`}>{status}</span>
);
