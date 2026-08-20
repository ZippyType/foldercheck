/**
 * Typed wrappers around our native macOS modules (FileDialog + Scanner).
 * When we add the Windows platform later, these paths get platform-specific
 * implementations but the JS API here stays the same.
 */

import { NativeEventEmitter, NativeModules } from 'react-native';

// ---- File / folder pickers ----

interface FileDialogModule {
  openFiles(allowMultiple: boolean): Promise<string[]>;
  openFolder(): Promise<string | null>;
  saveFile(opts: { suggestedName?: string; title?: string }): Promise<string | null>;
  writeTextFile(path: string, contents: string): Promise<boolean>;
}

const FileDialogNM = NativeModules.FileDialog as FileDialogModule;

export const FileDialog = {
  openFiles: (allowMultiple = true) => FileDialogNM.openFiles(allowMultiple),
  openFolder: () => FileDialogNM.openFolder(),
  saveFile: (opts: { suggestedName?: string; title?: string } = {}) =>
    FileDialogNM.saveFile(opts),
  writeTextFile: (path: string, contents: string) =>
    FileDialogNM.writeTextFile(path, contents),
};

// ---- Scanner ----

export interface FileEntry {
  absPath: string;
  size: number;
  mtime: number; // unix seconds
}

// Aggregate stats for one side. Note: no per-file `entries` here — that
// index stays native-only (see Scanner.mm) because a folder with more than
// ~196,607 files would exceed Hermes' per-object property ceiling if we
// tried to ship it across the bridge as a plain JS object.
export interface SideStats {
  fileInputs: number;
  folderInputs: number;
  files: number;
  size: number;
  subfolders: number;
  errors: number;
  missing: string[];
  extensions: Record<string, number>;
  largestFile: { name: string; size: number };
  sha256: string;
}

export type DiffStatus = 'added' | 'removed' | 'modified' | 'unchanged';

export interface DiffRow {
  status: DiffStatus;
  key: string;
  a: FileEntry | null;
  b: FileEntry | null;
  note: string;
}

export interface CompareResult {
  a: SideStats;
  b: SideStats;
  rows: DiffRow[];
}

interface ScannerModule {
  compare(aPaths: string[], bPaths: string[], deep: boolean): Promise<CompareResult>;
}

const ScannerNM = NativeModules.Scanner as ScannerModule;

export const Scanner = {
  compare: (aPaths: string[], bPaths: string[], deep: boolean) =>
    ScannerNM.compare(aPaths, bPaths, deep),
};

const scannerEvents = new NativeEventEmitter(NativeModules.Scanner);

export interface ScanProgress {
  side: string;
  files: number;
  bytes: number;
}

export function onScanProgress(cb: (p: ScanProgress) => void) {
  const sub = scannerEvents.addListener('scanProgress', cb);
  return () => sub.remove();
}

// ---- helpers ----

export function humanSize(n: number): string {
  if (n < 0) return `-${humanSize(-n)}`;
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let x = n;
  for (const u of units) {
    if (x < 1024 || u === units[units.length - 1]) {
      return u === 'B' ? `${Math.round(x)} B` : `${x.toFixed(2)} ${u}`;
    }
    x /= 1024;
  }
  return `${n} B`;
}

export function fmtDate(ts?: number): string {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  const p = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
         `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
