import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import Home from './pages/Home';
import Landing from './pages/Landing';
import Chat from './pages/Chat';
import './index.css';

// Route-split: @xyflow/react is only needed on /graph; keep it out of the entry chunk.
const KnowledgeGraph = lazy(() => import('./pages/KnowledgeGraph'));

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Landing />} />
          <Route path="/chat" element={<Chat />} />
          <Route
            path="/graph"
            element={
              <Suspense
                fallback={
                  <div role="status" className="p-8 text-xs font-bold uppercase tracking-wider">
                    Loading graph…
                  </div>
                }
              >
                <KnowledgeGraph />
              </Suspense>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
