import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  MarkerType,
  useReactFlow,
  type Node,
  type Edge,
  type NodeMouseHandler,
} from '@xyflow/react';
import { Download, Focus, X, ZoomIn, ZoomOut, Compass } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import '@xyflow/react/dist/style.css';
import { fetchGraph, fetchNodeDetails, fetchSubgraph, type NodeDetail, useAppStore } from '../lib/utils';

function buildRadialNodes(
  rawNodes: Array<{ id: string; label: string; type?: string }>,
  highlighted: Set<string>,
): Node[] {
  const n = rawNodes.length;
  const radius = 250;
  const cx = 400;
  const cy = 300;
  return rawNodes.map((node, index) => {
    const angle = (index / n) * Math.PI * 2 - Math.PI / 2;
    const isHighlighted = highlighted.has(node.id);
    return {
      id: node.id,
      position: { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius },
      data: { label: node.label || node.id },
      style: {
        borderRadius: 999,
        border: `1.5px solid ${isHighlighted ? '#155e54' : '#d4c5a9'}`,
        background: isHighlighted ? '#eae3d2' : '#fbf9f4',
        color: '#2d261e',
        fontSize: '11px',
        fontWeight: 700,
        boxShadow: isHighlighted
          ? '0 0 15px rgba(132, 204, 22, 0.25), inset 0 0 10px rgba(21, 94, 84, 0.1)'
          : '0 4px 10px rgba(0,0,0,0.02)',
        padding: '12px 16px',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      },
    };
  });
}

type FlowInnerProps = {
  nodes: Node[];
  edges: Edge[];
  highlightedNodes: string[];
  isLoading: boolean;
  stats: { node_count: number; edge_count: number };
};

function FlowInner({ nodes, edges, highlightedNodes, isLoading, stats }: FlowInnerProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [isFetchingDetail, setIsFetchingDetail] = useState(false);

  const handleNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    setSelectedNodeId(node.id);
    setNodeDetail(null);
    setIsFetchingDetail(true);
    fetchNodeDetails(node.id)
      .then((detail) => setNodeDetail(detail))
      .catch(() =>
        setNodeDetail({
          id: node.id,
          label: node.id,
          description: 'Details unavailable.',
          type: 'entity',
          source_files: [],
        })
      )
      .finally(() => setIsFetchingDetail(false));
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setNodeDetail(null);
  }, []);

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={handleNodeClick}
        className="[&_.react-flow__attribution]:hidden"
      >
        <Background gap={38} size={1.2} color="rgba(212, 197, 169, 0.45)" />
      </ReactFlow>

      {/* Sepia Styled Sidebar Panel */}
      <aside className="absolute right-6 top-1/2 -translate-y-1/2 z-20 parchment-card p-5 w-[290px] shadow-[0_16px_32px_rgba(45,38,30,0.06)] border border-[#d4c5a9] hidden md:block select-none">
        <div className="absolute top-3 left-3 w-3 h-3 border-t border-l border-[#8c7e6b]/40 pointer-events-none" />
        <div className="absolute bottom-3 right-3 w-3 h-3 border-b border-r border-[#8c7e6b]/40 pointer-events-none" />

        {selectedNodeId ? (
          <div className="select-text">
            <div className="flex items-center justify-between border-b border-[#d4c5a9]/50 pb-2">
              <h3 className="font-headline font-bold text-sm text-[#155e54] uppercase tracking-wider">Entity Details</h3>
              <button
                type="button"
                onClick={clearSelection}
                aria-label="Close entity details"
                className="text-[#8c7e6b] hover:text-[#155e54] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54] rounded"
              >
                <X size={15} aria-hidden="true" />
              </button>
            </div>

            {isFetchingDetail ? (
              <p role="status" className="mt-4 text-xs text-[#8c7e6b] font-bold animate-pulse uppercase tracking-wider">Loading details…</p>
            ) : nodeDetail ? (
              <div className="mt-4 space-y-3.5 text-xs text-[#2d261e] font-semibold">
                <p className="font-bold text-[#1a2e05] text-sm break-words uppercase tracking-wide">{nodeDetail.label}</p>
                {nodeDetail.type && nodeDetail.type !== 'entity' && (
                  <span className="inline-block text-[9px] font-extrabold uppercase tracking-widest bg-[#155e54]/10 text-[#155e54] border border-[#d4c5a9]/40 px-2 py-0.5 rounded-full">
                    {nodeDetail.type}
                  </span>
                )}
                <div className="prose prose-sm max-w-none text-[#8c7e6b] leading-relaxed font-medium">
                  <ReactMarkdown>{nodeDetail.description || 'No description found in vector space.'}</ReactMarkdown>
                </div>
                <div className="pt-2 border-t border-[#d4c5a9]/30">
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-[#155e54]">Covenant Chunks</p>
                  {nodeDetail.source_files.length > 0 ? (
                    <ul className="mt-1.5 space-y-1">
                      {nodeDetail.source_files.map((file) => (
                        <li key={file} className="text-[10px] text-[#8c7e6b] break-all list-disc list-inside">
                          {file}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-[10px] text-[#8c7e6b] italic font-medium">No linked metadata.</p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <>
            <h3 className="font-headline font-bold text-sm text-[#155e54] uppercase tracking-wider flex items-center gap-1">
              <Compass size={14} aria-hidden="true" className="text-[#84cc16]" /> Graph Insights
            </h3>
            <div className="mt-4 space-y-2 text-xs text-[#8c7e6b] font-bold uppercase tracking-wide leading-relaxed">
              <p>🟢 {stats.node_count} legal entities</p>
              <p>🔗 {stats.edge_count} relationship links</p>
              {highlightedNodes.length > 0 && (
                <p className="text-[#155e54] font-extrabold animate-pulse">🎯 Subgraph mode active</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => fitView({ duration: 300 })}
              className="mt-6 w-full rounded-full bg-[#155e54] text-white py-3 text-[10px] font-extrabold tracking-[0.14em] uppercase flex items-center justify-center gap-2 hover:bg-[#84cc16] active:scale-95 transition-all shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
            >
              <Download size={13} aria-hidden="true" />
              Re-center view
            </button>
          </>
        )}
      </aside>

      {/* Styled Circle Controls */}
      <div className="absolute right-8 bottom-8 z-20 bg-[#eae3d2] border border-[#d4c5a9] rounded-full p-2 flex flex-col gap-2 shadow-lg">
        <button
          type="button"
          onClick={() => zoomIn({ duration: 300 })}
          aria-label="Zoom in on graph"
          className="w-10 h-10 rounded-full hover:bg-white flex items-center justify-center text-[#155e54] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
        >
          <ZoomIn size={16} strokeWidth={2.3} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => zoomOut({ duration: 300 })}
          aria-label="Zoom out of graph"
          className="w-10 h-10 rounded-full hover:bg-white flex items-center justify-center text-[#155e54] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
        >
          <ZoomOut size={16} strokeWidth={2.3} aria-hidden="true" />
        </button>
        <div aria-hidden="true" className="w-6 h-px bg-[#d4c5a9] mx-auto" />
        <button
          type="button"
          onClick={() => fitView({ duration: 300 })}
          aria-label="Re-center graph view"
          className="w-10 h-10 rounded-full hover:bg-white flex items-center justify-center text-[#155e54] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
        >
          <Focus size={16} strokeWidth={2.3} aria-hidden="true" />
        </button>
      </div>

      {isLoading && (
        <div role="status" className="absolute inset-0 z-30 bg-[#fbf9f4]/85 backdrop-blur-[2px] flex items-center justify-center text-[#155e54] font-extrabold uppercase text-xs tracking-wider select-none">
          ✨ Extracting relationship coordinates...
        </div>
      )}
    </>
  );
}

export default function KnowledgeGraph() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  
  const documents = useAppStore((state) => state.documents);
  const activeDocId = useAppStore((state) => state.activeDocId);
  const companyId = useAppStore((state) => state.companyId);
  const graphData = useAppStore((state) => state.graphData);
  const highlightedNodes = useAppStore((state) => state.highlightedNodes);
  const chatHistory = useAppStore((state) => state.chatHistory);
  
  const setActiveDoc = useAppStore((state) => state.setActiveDoc);
  const setGraphData = useAppStore((state) => state.setGraphData);
  
  const readyDocuments = useMemo(
    () => documents.filter((doc) => doc.status === 'ready'),
    [documents]
  );

  const hasCompletedChat = useMemo(
    () => chatHistory.some((message) => message.role === 'assistant') || readyDocuments.length > 0,
    [chatHistory, readyDocuments]
  );

  const lastQueryNodes = useMemo(() => {
    const last = [...chatHistory]
      .reverse()
      .find((m) => m.role === 'assistant' && m.graphNodes && m.graphNodes.length > 0);
    return last?.graphNodes ?? [];
  }, [chatHistory]);

  const effectiveNodes = highlightedNodes.length > 0 ? highlightedNodes : lastQueryNodes;

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      if (!hasCompletedChat) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        // Pass the companyId here so the Neo4j/NetworkX query is isolated!
        const nextData =
          effectiveNodes.length > 0
            ? await fetchSubgraph(effectiveNodes, companyId)
            : await fetchGraph(companyId);
        if (mounted) {
          setGraphData(nextData);
        }
      } catch {
        // Handle gracefully
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [hasCompletedChat, effectiveNodes, setGraphData, companyId]);

  const highlightedSet = useMemo(() => new Set(effectiveNodes), [effectiveNodes]);

  const nodes: Node[] = useMemo(
    () => buildRadialNodes(graphData.nodes, highlightedSet),
    [graphData.nodes, highlightedSet]
  );

  const edges: Edge[] = useMemo(
    () =>
      graphData.edges.map((edge, index) => {
        const emphasized = highlightedSet.has(edge.source) || highlightedSet.has(edge.target);
        return {
          id: `${edge.source}-${edge.target}-${index}`,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: emphasized ? '#155e54' : '#d4c5a9',
          },
          style: {
            stroke: emphasized ? '#155e54' : '#d4c5a9',
            strokeWidth: emphasized ? 2 : 1,
          },
        };
      }),
    [graphData.edges, highlightedSet]
  );

  if (!hasCompletedChat) {
    return (
      <div className="h-[calc(100vh-12rem)] rounded-[2rem] shadow-[0_20px_40px_rgba(45,38,30,0.04)] parchment-card p-8 flex items-center justify-center">
        <div className="max-w-xl text-center space-y-5">
          <h1 className="font-headline font-extrabold text-xl sm:text-2xl md:text-3xl text-[#155e54]">Complete chat to unlock graph</h1>
          <p className="text-xs text-[#8c7e6b] font-medium leading-relaxed">
            NyayaMitra builds the knowledge map dynamically based on your contract analyses. Complete at least one query in the Risk Chat to activate the interactive canvas.
          </p>
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="h-11 px-6 rounded-full bg-[#155e54] text-white font-bold text-xs uppercase tracking-wider hover:bg-[#84cc16] active:scale-95 transition-all shadow-md"
          >
            Go to Risk Chat
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-[calc(100vh-12rem)] rounded-[2rem] overflow-hidden border border-[#d4c5a9] shadow-[0_20px_40px_rgba(45,38,30,0.05)] bg-[#fbf9f4]">
      <h1 className="sr-only">Knowledge graph</h1>
      
      {/* Top Scope bar */}
      <div className="absolute left-6 top-6 z-20 parchment-card rounded-2xl p-3 border border-[#d4c5a9] select-none">
        <p className="text-[9px] font-extrabold uppercase tracking-wider text-[#155e54]">Active Document Target</p>
        <select
          value={activeDocId ?? ''}
          aria-label="Active document target"
          onChange={(event) => setActiveDoc(event.target.value || null)}
          className="mt-1 bg-white border border-[#d4c5a9] rounded-lg px-2.5 py-1 text-xs text-[#155e54] font-bold min-w-[220px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
        >
          <option value="">All indexed documents</option>
          {readyDocuments.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.name}
            </option>
          ))}
        </select>
      </div>

      <ReactFlowProvider>
        <FlowInner
          nodes={nodes}
          edges={edges}
          highlightedNodes={effectiveNodes}
          isLoading={isLoading}
          stats={graphData.stats}
        />
      </ReactFlowProvider>
    </div>
  );
}
