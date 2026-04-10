import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Lab } from '@/pages/Lab';
import { Evolution } from '@/pages/Evolution';
import { Library } from '@/pages/Library';
import { Data } from '@/pages/Data';
import { SettingsPage } from '@/pages/Settings';

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/lab" element={<Lab />} />
        <Route path="/evolution" element={<Evolution />} />
        <Route path="/library" element={<Library />} />
        <Route path="/data" element={<Data />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/data" replace />} />
      </Route>
    </Routes>
  );
}
