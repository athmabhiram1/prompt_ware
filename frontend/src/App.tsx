import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import Home from './pages/Home';
import Landing from './pages/Landing';
import Chat from './pages/Chat';
import KnowledgeGraph from './pages/KnowledgeGraph';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Landing />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
