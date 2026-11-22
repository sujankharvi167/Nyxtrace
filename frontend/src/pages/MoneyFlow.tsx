import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Loader2,
  Network,
  RefreshCw,
  Route,
  Search,
  ZoomIn,
} from 'lucide-react';
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { SectionHeader, EmptyState } from '@/components/ui';
import { api } from '@/services/api';
import type {
  GraphCluster,
  GraphCycle,
  GraphFanResult,
  GraphNode,
  GraphStatus,
  GraphStatistics,
} from '@/types';

const riskColor = (node: GraphNode) => {
  if (node.predicted_class === 'illicit') {
    const risk = node.illicit_probability ?? 0;
    return risk >= 0.8 ? '#ef4444' : '#f59e0b';
  }
  if (node.predicted_class === 'licit') return '#34d399';
  return '#64748b';
};

export const MoneyFlow: React.FC = () => {
  const [status, setStatus] = useState<GraphStatus | null>(null);
  const [statistics, setStatistics] = useState<GraphStatistics | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [depth, setDepth] = useState(2);
  const [direction, setDirection] = useState<'all' | 'upstream' | 'downstream'>('all');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [building, setBuilding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pathText, setPathText] = useState<string | null>(null);
  const [fanIn, setFanIn] = useState<GraphFanResult | null>(null);
  const [fanOut, setFanOut] = useState<GraphFanResult | null>(null);
  const [cycles, setCycles] = useState<GraphCycle[] | null>(null);
  const [clusters, setClusters] = useState<GraphCluster[] | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const statusResponse = await api.graph.status();
      const graphStatus = statusResponse.data ?? null;
      setStatus(graphStatus);
      if (graphStatus?.status === 'ready') {
        const [statsResponse, fanInResponse, fanOutResponse, cyclesResponse, clustersResponse] =
          await Promise.all([
            api.graph.statistics(),
            api.graph.fanIn(10),
            api.graph.fanOut(10),
            api.graph.cycles(25),
            api.graph.clusters(25),
          ]);
        setStatistics(statsResponse.data ?? null);
        setFanIn(fanInResponse.data ?? null);
        setFanOut(fanOutResponse.data ?? null);
        setCycles(cyclesResponse.data?.items ?? []);
        setClusters(clustersResponse.data?.items ?? []);
      } else {
        setStatistics(null);
        setFanIn(null);
        setFanOut(null);
        setCycles(null);
        setClusters(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load graph status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const renderNeighborhood = useCallback((neighborhood: {
    nodes: GraphNode[];
    edges: Array<{ source: string; target: string }>;
  }, highlighted: string[] = []) => {
    const ids = neighborhood.nodes.map(node => node.transaction_id);
    const center = ids.length ? Math.ceil(ids.length / 2) : 0;
    const flowNodes: Node[] = neighborhood.nodes.map((node, index) => {
      const ring = 1 + Math.floor(index / 12);
      const angle = (2 * Math.PI * index) / Math.max(neighborhood.nodes.length, 1);
      const x = 420 + Math.cos(angle) * Math.min(300, ring * 90);
      const y = 260 + Math.sin(angle) * Math.min(220, ring * 70);
      const highlightedNode = highlighted.includes(node.transaction_id);
      return {
        id: node.transaction_id,
        position: { x, y },
        data: {
          label: (
            <div className="text-center min-w-[92px]">
              <p className="text-[10px] font-mono text-slate-100">{node.transaction_id}</p>
              <p className="text-[9px] mt-1" style={{ color: riskColor(node) }}>
                {node.predicted_class ? `${node.predicted_class} · ${node.illicit_probability != null ? `${(node.illicit_probability * 100).toFixed(1)}%` : 'N/A'}` : 'No ML prediction'}
              </p>
            </div>
          ),
        },
        style: {
          background: highlightedNode ? '#172554' : '#111a2e',
          border: `2px solid ${highlightedNode ? '#60a5fa' : riskColor(node)}`,
          borderRadius: 10,
          padding: 8,
          color: '#e2e8f0',
        },
      };
    });
    const flowEdges: Edge[] = neighborhood.edges
      .filter(edge => ids.includes(edge.source) && ids.includes(edge.target))
      .map(edge => ({
        id: `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        animated: highlighted.includes(edge.source) || highlighted.includes(edge.target),
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: '#64748b' },
        style: { stroke: '#64748b' },
      }));
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [setEdges, setNodes]);

  const selectNode = useCallback(async (transactionId: string) => {
    setError(null);
    setPathText(null);
    try {
      const response = await api.graph.node(transactionId);
      setSelected(response.data ?? null);
      const neighborhood = await api.graph.neighborhood(transactionId, depth, 100, direction);
      renderNeighborhood(neighborhood.data ?? { nodes: [], edges: [] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the transaction.');
    }
  }, [depth, direction, renderNeighborhood]);

  const searchTransaction = async () => {
    const transactionId = search.trim();
    if (!transactionId) {
      setError('Enter a transaction ID.');
      return;
    }
    await selectNode(transactionId);
  };

  const trace = async (traceDirection: 'upstream' | 'downstream') => {
    const transactionId = selected?.transaction_id ?? search.trim();
    if (!transactionId) {
      setError('Select or enter a transaction ID first.');
      return;
    }
    setError(null);
    try {
      const response = traceDirection === 'upstream'
        ? await api.graph.upstream(transactionId, depth, 100)
        : await api.graph.downstream(transactionId, depth, 100);
      renderNeighborhood(response.data ?? { nodes: [], edges: [] });
      setDirection(traceDirection);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not trace transaction relationships.');
    }
  };

  const findPath = async () => {
    if (!source.trim() || !destination.trim()) {
      setError('Enter both source and destination transaction IDs.');
      return;
    }
    setError(null);
    setPathText(null);
    try {
      const response = await api.graph.path(source.trim(), destination.trim(), 100);
      const result = response.data;
      if (!result?.path_found) {
        setPathText('No valid directed relationship path exists between these transaction IDs.');
        setNodes([]);
        setEdges([]);
      } else {
        setPathText(`${result.hops} hop${result.hops === 1 ? '' : 's'} · ${result.transaction_ids.join(' → ')}`);
        const neighborhood = {
          nodes: result.nodes ?? [],
          edges: result.transaction_ids.slice(0, -1).map((node, index) => ({
            source: node,
            target: result.transaction_ids[index + 1],
          })),
        };
        renderNeighborhood(neighborhood, result.ml_flagged_transaction_ids);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not find a transaction path.');
    }
  };

  const buildGraph = async () => {
    setBuilding(true);
    setError(null);
    try {
      await api.graph.build();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the graph.');
    } finally {
      setBuilding(false);
    }
  };

  const onNodeClick = (_event: React.MouseEvent, node: Node) => {
    void selectNode(String(node.id));
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Money Flow Intelligence"
        subtitle="Actual transaction relationships, bounded tracing, and ML-linked graph investigation"
        actions={
          <button type="button" onClick={buildGraph} disabled={building} className="btn-primary">
            {building ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {building ? 'Building graph' : 'Build / rebuild graph'}
          </button>
        }
      />

      {error && (
        <div className="card p-3 flex items-start gap-2" style={{ borderLeft: '2px solid #ef4444' }}>
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5" />
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="card p-8 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400" /></div>
      ) : status?.status !== 'ready' ? (
        <div className="card p-4" style={{ borderLeft: '2px solid #f59e0b' }}>
          <p className="text-sm font-medium text-amber-300">
            {status?.status === 'stale' ? 'Graph is stale' : status?.status === 'error' ? 'Graph build error' : 'Graph not built'}
          </p>
          <p className="text-xs text-slate-400 mt-1">{status?.message ?? 'Build the graph from the latest uploaded edgelist.'}</p>
          {status?.status === 'stale' && <p className="text-xs text-slate-500 mt-1">Rebuild after the latest dataset has been uploaded.</p>}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Kpi label="Graph nodes" value={statistics?.nodes.toLocaleString() ?? '—'} />
            <Kpi label="Graph edges" value={statistics?.edges.toLocaleString() ?? '—'} />
            <Kpi label="Connected components" value={statistics?.connected_components.toLocaleString() ?? '—'} />
            <Kpi label="ML-linked flagged" value={statistics?.ml_flagged_transactions.toLocaleString() ?? '0'} tone="amber" />
          </div>

          {!status.ml_predictions_available && (
            <div className="card p-3 text-xs text-amber-300">
              The graph is ready, but ML predictions are unavailable because the latest dataset and saved model belong to different batches.
            </div>
          )}

          <div className="card p-5 space-y-4">
            <p className="section-label">Transaction search and tracing</p>
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_auto] gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  value={search}
                  onChange={event => setSearch(event.target.value)}
                  onKeyDown={event => { if (event.key === 'Enter') void searchTransaction(); }}
                  placeholder="Search by transaction ID"
                  className="w-full rounded-lg py-2.5 pl-10 pr-4 text-sm text-slate-200"
                  style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}
                />
              </div>
              <button type="button" onClick={searchTransaction} className="btn-primary">
                <Search className="w-4 h-4" /> Select transaction
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_auto_auto] gap-3">
              <input value={source} onChange={event => setSource(event.target.value)} placeholder="Source transaction ID" className="graph-input" />
              <input value={destination} onChange={event => setDestination(event.target.value)} placeholder="Destination transaction ID" className="graph-input" />
              <label className="flex items-center gap-2 text-xs text-slate-400">
                Depth
                <input type="number" min="1" max="10" value={depth} onChange={event => setDepth(Math.min(10, Math.max(1, Number(event.target.value))))} className="w-16 graph-input" />
              </label>
              <select value={direction} onChange={event => setDirection(event.target.value as 'all' | 'upstream' | 'downstream')} className="graph-input">
                <option value="all">Neighborhood</option>
                <option value="upstream">Upstream</option>
                <option value="downstream">Downstream</option>
              </select>
              <button type="button" onClick={findPath} className="btn-primary">
                <Route className="w-4 h-4" /> Find path
              </button>
            </div>
            {pathText && <p className="text-xs text-cyan-300 break-words">{pathText}</p>}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_320px] gap-4">
            <div className="card overflow-hidden" style={{ height: 520 }}>
              <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid #1e2d4a' }}>
                <p className="section-label">Transaction network</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => trace('upstream')} className="text-xs px-2 py-1 rounded-md text-slate-300" style={{ border: '1px solid #263354' }}>Trace upstream</button>
                  <button type="button" onClick={() => trace('downstream')} className="text-xs px-2 py-1 rounded-md text-slate-300" style={{ border: '1px solid #263354' }}>Trace downstream</button>
                </div>
              </div>
              {nodes.length ? (
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={onNodeClick}
                  fitView
                  fitViewOptions={{ padding: 0.18 }}
                  minZoom={0.15}
                  attributionPosition="bottom-left"
                >
                  <Background color="#263354" gap={18} />
                  <Controls showInteractive={false} />
                  <MiniMap
                    nodeColor={node => String(node.style?.border ?? '#64748b').replace('2px solid ', '')}
                    maskColor="rgba(10,14,26,0.75)"
                  />
                </ReactFlow>
              ) : (
                <EmptyState
                  icon={<Network className="w-8 h-8" />}
                  title="No transaction subgraph selected"
                  description="Enter a transaction ID or find a path to inspect actual relationships."
                  className="py-28"
                />
              )}
            </div>

            <div className="card p-5">
              <p className="section-label mb-4">Transaction details</p>
              {!selected ? (
                <EmptyState icon={<ZoomIn className="w-5 h-5" />} title="No transaction selected" description="Select a node or search by transaction ID." />
              ) : (
                <div className="space-y-2">
                  <Detail label="Transaction ID" value={selected.transaction_id} mono />
                  <Detail label="ML prediction" value={selected.predicted_class ?? 'Unavailable'} />
                  <Detail label="Illicit risk" value={selected.illicit_probability != null ? `${(selected.illicit_probability * 100).toFixed(2)}%` : 'Unavailable'} />
                  <Detail label="Confidence" value={selected.confidence != null ? `${(selected.confidence * 100).toFixed(2)}%` : 'Unavailable'} />
                  <Detail label="Ground truth" value={selected.ground_truth_label} />
                  <Detail label="Incoming" value={String(selected.incoming_count ?? 0)} />
                  <Detail label="Outgoing" value={String(selected.outgoing_count ?? 0)} />
                  {selected.incoming_transaction_ids?.length ? <Detail label="Incoming IDs" value={selected.incoming_transaction_ids.slice(0, 10).join(', ')} mono /> : null}
                  {selected.outgoing_transaction_ids?.length ? <Detail label="Outgoing IDs" value={selected.outgoing_transaction_ids.slice(0, 10).join(', ')} mono /> : null}
                  {selected.predicted_class === 'illicit' && <p className="text-xs text-amber-300 mt-3">Statistical model flag only; it is not evidence of wrongdoing.</p>}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <PatternCard title="Fan-in" items={fanIn?.items.map(item => ({
              primary: item.transaction_id,
              secondary: `${item.incoming_count ?? 0} incoming · risk ${item.illicit_probability != null ? `${(item.illicit_probability * 100).toFixed(1)}%` : 'N/A'}`,
            })) ?? []} empty="No fan-in patterns found." />
            <PatternCard title="Fan-out" items={fanOut?.items.map(item => ({
              primary: item.transaction_id,
              secondary: `${item.outgoing_count ?? 0} outgoing · risk ${item.illicit_probability != null ? `${(item.illicit_probability * 100).toFixed(1)}%` : 'N/A'}`,
            })) ?? []} empty="No fan-out patterns found." />
            <PatternCard title="Cycles" items={cycles?.map(item => ({
              primary: item.cycle.join(' → '),
              secondary: `${item.cycle_length} hops · ${item.ml_flagged ? 'contains ML flag' : 'no ML flag'}`,
            })) ?? []} empty="No bounded cycles found." />
            <PatternCard title="Suspicious clusters" items={clusters?.map(item => ({
              primary: item.cluster_id,
              secondary: `${item.flagged_count} flagged of ${item.transaction_count} transactions · highest risk ${item.highest_illicit_probability != null ? `${(item.highest_illicit_probability * 100).toFixed(1)}%` : 'N/A'}`,
            })) ?? []} empty="No connected groups with multiple ML flags." />
          </div>
        </>
      )}
    </div>
  );
};

const Kpi: React.FC<{ label: string; value: string; tone?: 'amber' }> = ({ label, value, tone }) =>
  <div className="card p-4">
    <p className="text-[0.62rem] uppercase tracking-wider text-slate-500">{label}</p>
    <p className={`text-lg font-semibold mt-1 ${tone === 'amber' ? 'text-amber-300' : 'text-slate-100'}`}>{value}</p>
  </div>;

const Detail: React.FC<{ label: string; value: string; mono?: boolean }> = ({ label, value, mono }) =>
  <div className="flex items-start justify-between gap-3 py-2" style={{ borderBottom: '1px solid #1e2d4a' }}>
    <span className="text-xs text-slate-500">{label}</span>
    <span className={`text-xs text-right text-slate-200 ${mono ? 'font-mono break-all' : ''}`}>{value}</span>
  </div>;

const PatternCard: React.FC<{ title: string; items: Array<{ primary: string; secondary: string }>; empty: string }> =
  ({ title, items, empty }) =>
    <div className="card p-5">
      <p className="section-label">{title}</p>
      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.slice(0, 10).map((item, index) =>
            <div key={`${item.primary}-${index}`} className="rounded-lg p-2" style={{ backgroundColor: '#141d35', border: '1px solid #1e2d4a' }}>
              <p className="text-xs text-slate-200 font-mono break-all">{item.primary}</p>
              <p className="text-[10px] text-slate-500 mt-1">{item.secondary}</p>
            </div>
          )}
        </div>
      ) : <p className="text-xs text-slate-500 mt-3">{empty}</p>}
    </div>;
