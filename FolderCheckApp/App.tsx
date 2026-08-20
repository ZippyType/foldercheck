/**
 * FolderCheck — cross-platform (macOS + Windows) folder comparison app.
 */

import React from 'react';
import { AppProvider } from './src/store';
import { Shell } from './src/ui/Shell';

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
