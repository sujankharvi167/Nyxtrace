import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppLayout } from '@/layouts/AppLayout';
import {
  Dashboard,
  TransactionAnalysis,
  MoneyFlow,
  RiskIntelligence,
  InvestigationCases,
  Reports,
  About,
} from '@/pages';

const NotFound: React.FC = () => (
  <div className="flex items-center justify-center h-64">
    <div className="text-center">
      <p className="text-5xl font-bold text-slate-700 mb-3">404</p>
      <p className="text-slate-500 text-sm">Page not found</p>
    </div>
  </div>
);

const App: React.FC = () => (
  <Router>
    <AppLayout>
      <Routes>
        <Route path="/"           element={<Dashboard />}           />
        <Route path="/analysis"   element={<TransactionAnalysis />} />
        <Route path="/money-flow" element={<MoneyFlow />}           />
        <Route path="/risk"       element={<RiskIntelligence />}    />
        <Route path="/cases"      element={<InvestigationCases />} />
        <Route path="/reports"    element={<Reports />}             />
        <Route path="/about"      element={<About />}               />
        <Route path="*"           element={<NotFound />}            />
      </Routes>
    </AppLayout>
  </Router>
);

export default App;
