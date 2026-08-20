/**
 * Compare state. A React context + reducer is plenty for this app's scope.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from 'react';

import {
  DiffRow,
  Scanner,
  ScanProgress,
  SideResult,
  onScanProgress,
} from './native';

export interface Filters {
  added: boolean;
  removed: boolean;
  modified: boolean;
  unchanged: boolean;
}

export interface CompareResult {
  a: SideResult;
  b: SideResult;
  rows: DiffRow[];
}

interface State {
  aInputs: string[];
  bInputs: string[];
  deep: boolean;
  filters: Filters;
  busy: boolean;
  status: string;
  progressText: string;
  result: CompareResult | null;
}

type Action =
  | { type: 'add'; side: 'A' | 'B'; paths: string[] }
  | { type: 'remove'; side: 'A' | 'B'; index: number }
  | { type: 'clearSide'; side: 'A' | 'B' }
  | { type: 'clearAll' }
  | { type: 'swap' }
  | { type: 'deep'; value: boolean }
  | { type: 'filters'; value: Filters }
  | { type: 'busy'; value: boolean }
  | { type: 'status'; value: string }
  | { type: 'progress'; value: string }
  | { type: 'result'; value: CompareResult | null };

const initial: State = {
  aInputs: [],
  bInputs: [],
  deep: false,
  filters: { added: true, removed: true, modified: true, unchanged: false },
  busy: false,
  status: 'Add sources to A and B, then press Compare.',
  progressText: '',
  result: null,
};

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'add': {
      const key = a.side === 'A' ? 'aInputs' : 'bInputs';
      const seen = new Set(s[key]);
      const merged = [...s[key], ...a.paths.filter(p => !seen.has(p))];
      return { ...s, [key]: merged };
    }
    case 'remove': {
      const key = a.side === 'A' ? 'aInputs' : 'bInputs';
      return { ...s, [key]: s[key].filter((_, i) => i !== a.index) };
    }
    case 'clearSide':
      return { ...s, [a.side === 'A' ? 'aInputs' : 'bInputs']: [] };
    case 'clearAll':
      return {
        ...s,
        aInputs: [],
        bInputs: [],
        result: null,
        status: 'Cleared.',
      };
    case 'swap':
      return { ...s, aInputs: s.bInputs, bInputs: s.aInputs };
    case 'deep':
      return { ...s, deep: a.value };
    case 'filters':
      return { ...s, filters: a.value };
    case 'busy':
      return { ...s, busy: a.value };
    case 'status':
      return { ...s, status: a.value };
    case 'progress':
      return { ...s, progressText: a.value };
    case 'result':
      return { ...s, result: a.value };
  }
}

// ---- context ----

interface Ctx {
  state: State;
  addPaths: (side: 'A' | 'B', paths: string[]) => void;
  removeAt: (side: 'A' | 'B', index: number) => void;
  clearSide: (side: 'A' | 'B') => void;
  clearAll: () => void;
  swap: () => void;
  setDeep: (v: boolean) => void;
  setFilters: (v: Filters) => void;
  compare: () => Promise<void>;
}

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);

  useEffect(() => {
    const off = onScanProgress((p: ScanProgress) => {
      dispatch({
        type: 'progress',
        value: `Scanning ${p.side}: ${p.files.toLocaleString()} files, ${formatBytes(p.bytes)}…`,
      });
    });
    return off;
  }, []);

  const compare = useCallback(async () => {
    if (state.busy) return;
    if (state.aInputs.length === 0 || state.bInputs.length === 0) {
      dispatch({ type: 'status', value: 'Add at least one item to each side.' });
      return;
    }
    dispatch({ type: 'busy', value: true });
    dispatch({ type: 'result', value: null });
    dispatch({ type: 'progress', value: 'Preparing…' });
    dispatch({ type: 'status', value: 'Scanning…' });
    try {
      const a = await Scanner.scanPaths(state.aInputs, 'A');
      const b = await Scanner.scanPaths(state.bInputs, 'B');
      dispatch({ type: 'progress', value: 'Comparing files…' });
      const rows = await Scanner.diffSides(a, b, state.deep);
      dispatch({ type: 'result', value: { a, b, rows } });
      const added = rows.filter(r => r.status === 'added').length;
      const removed = rows.filter(r => r.status === 'removed').length;
      const modified = rows.filter(r => r.status === 'modified').length;
      dispatch({
        type: 'status',
        value:
          `Done. A: ${a.files.toLocaleString()} files / ${formatBytes(a.size)}   ` +
          `B: ${b.files.toLocaleString()} files / ${formatBytes(b.size)}   ` +
          `(+${added} added, -${removed} removed, ${modified} modified)`,
      });
    } catch (e: any) {
      dispatch({ type: 'status', value: `Error: ${e?.message ?? e}` });
    } finally {
      dispatch({ type: 'busy', value: false });
      dispatch({ type: 'progress', value: '' });
    }
  }, [state.aInputs, state.bInputs, state.busy, state.deep]);

  const value: Ctx = useMemo(
    () => ({
      state,
      addPaths: (side, paths) => dispatch({ type: 'add', side, paths }),
      removeAt: (side, index) => dispatch({ type: 'remove', side, index }),
      clearSide: (side) => dispatch({ type: 'clearSide', side }),
      clearAll: () => dispatch({ type: 'clearAll' }),
      swap: () => dispatch({ type: 'swap' }),
      setDeep: (v) => dispatch({ type: 'deep', value: v }),
      setFilters: (v) => dispatch({ type: 'filters', value: v }),
      compare,
    }),
    [state, compare],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside <AppProvider>');
  return ctx;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let x = n / 1024;
  for (const u of units) {
    if (x < 1024 || u === units[units.length - 1]) return `${x.toFixed(2)} ${u}`;
    x /= 1024;
  }
  return `${n} B`;
}

export type { DiffRow, SideResult };
