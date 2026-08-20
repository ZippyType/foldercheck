import React, { useMemo } from 'react';
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { DiffRow, FileDialog, fmtDate, humanSize } from '../native';
import { useApp } from '../store';
import { fs, fw, radii, space, useTheme, Palette } from '../theme';

function toCsv(rows: DiffRow[]): string {
  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const header = 'status,path,a_size,b_size,a_modified,b_modified,note';
  const lines = rows.map(r =>
    [
      r.status,
      esc(r.key),
      r.a ? String(r.a.size) : '',
      r.b ? String(r.b.size) : '',
      r.a ? fmtDate(r.a.mtime) : '',
      r.b ? fmtDate(r.b.mtime) : '',
      esc(r.note),
    ].join(','),
  );
  return [header, ...lines].join('\n');
}

const RANK: Record<string, number> = {
  removed: 0, added: 1, modified: 2, unchanged: 3,
};

export function DiffTab() {
  const t = useTheme();
  const { state, setFilters } = useApp();
  const { rows } = state.result!;

  const visible = useMemo(() => {
    const w = state.filters;
    const filtered = rows.filter(
      r =>
        (r.status === 'added' && w.added) ||
        (r.status === 'removed' && w.removed) ||
        (r.status === 'modified' && w.modified) ||
        (r.status === 'unchanged' && w.unchanged),
    );
    filtered.sort((x, y) => {
      const c = (RANK[x.status] ?? 9) - (RANK[y.status] ?? 9);
      return c !== 0 ? c : x.key.localeCompare(y.key);
    });
    return filtered;
  }, [rows, state.filters]);

  const exportCsv = async () => {
    const path = await FileDialog.saveFile({
      suggestedName: 'foldercheck-diff.csv',
      title: 'Export file differences as CSV',
    });
    if (!path) return;
    await FileDialog.writeTextFile(path, toCsv(rows));
  };

  return (
    <View style={{ flex: 1 }}>
      <View style={[s.filters, { borderBottomColor: t.separator, backgroundColor: t.bgContent }]}>
        <Chip t={t} label="Added" color={t.green} on={state.filters.added}
          onPress={() => setFilters({ ...state.filters, added: !state.filters.added })} />
        <Chip t={t} label="Removed" color={t.red} on={state.filters.removed}
          onPress={() => setFilters({ ...state.filters, removed: !state.filters.removed })} />
        <Chip t={t} label="Modified" color={t.orange} on={state.filters.modified}
          onPress={() => setFilters({ ...state.filters, modified: !state.filters.modified })} />
        <Chip t={t} label="Unchanged" color={t.textTertiary} on={state.filters.unchanged}
          onPress={() => setFilters({ ...state.filters, unchanged: !state.filters.unchanged })} />
        <View style={{ flex: 1 }} />
        <Text style={{ color: t.textTertiary, fontSize: fs.xs }}>
          {visible.length.toLocaleString()} / {rows.length.toLocaleString()}
        </Text>
        <Pressable
          onPress={exportCsv}
          style={({ pressed, hovered }: any) => [
            s.exportBtn,
            {
              backgroundColor: pressed ? t.active : hovered ? t.hover : t.card,
              borderColor: t.border,
            },
          ]}
        >
          <Text style={{ color: t.text, fontSize: fs.sm, fontWeight: fw.medium }}>
            Export CSV…
          </Text>
        </Pressable>
      </View>

      <View style={[s.headerRow, { backgroundColor: t.bgContent, borderBottomColor: t.separator }]}>
        <HeaderCell t={t} label="Status" width={90} />
        <HeaderCell t={t} label="Path" flex={2} />
        <HeaderCell t={t} label="A size" width={90} align="right" />
        <HeaderCell t={t} label="B size" width={90} align="right" />
        <HeaderCell t={t} label="A modified" width={150} />
        <HeaderCell t={t} label="B modified" width={150} />
        <HeaderCell t={t} label="Newer" width={60} align="center" />
        <HeaderCell t={t} label="Change" flex={1} />
      </View>

      <FlatList
        data={visible}
        keyExtractor={(r, i) => `${r.status}-${r.key}-${i}`}
        removeClippedSubviews
        initialNumToRender={40}
        windowSize={10}
        renderItem={({ item, index }) => (
          <RowView t={t} row={item} alt={index % 2 === 1} />
        )}
      />
    </View>
  );
}

function Chip({
  t, label, color, on, onPress,
}: {
  t: Palette;
  label: string;
  color: string;
  on: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ hovered }: any) => [
        s.chip,
        {
          backgroundColor: hovered ? t.hover : 'transparent',
          borderColor: t.border,
          opacity: on ? 1 : 0.5,
        },
      ]}
    >
      <View style={[s.dot, { backgroundColor: color }]} />
      <Text style={{ color: t.textSecondary, fontSize: fs.sm }}>{label}</Text>
    </Pressable>
  );
}

function HeaderCell({
  t,
  label,
  width,
  flex,
  align,
}: {
  t: Palette;
  label: string;
  width?: number;
  flex?: number;
  align?: 'left' | 'center' | 'right';
}) {
  const styles: any = {
    color: t.textTertiary,
    fontSize: fs.xs,
    fontWeight: fw.bold,
    letterSpacing: 0.6,
    textAlign: align ?? 'left',
  };
  return (
    <Text
      style={[styles, s.cell, width != null ? { width } : { flex }]}
      numberOfLines={1}
    >
      {label.toUpperCase()}
    </Text>
  );
}

function RowView({ t, row, alt }: { t: Palette; row: DiffRow; alt: boolean }) {
  const color = statusColor(t, row.status);
  const newer =
    row.a && row.b
      ? Math.abs(row.a.mtime - row.b.mtime) <= 1
        ? '='
        : row.a.mtime > row.b.mtime
        ? 'A'
        : 'B'
      : row.a
      ? 'A'
      : row.b
      ? 'B'
      : '';
  return (
    <View
      style={[
        s.row,
        {
          backgroundColor: alt ? t.bgContent : 'transparent',
          borderBottomColor: t.separator,
        },
      ]}
    >
      <Text style={[{ color, width: 90 }, s.cell]} numberOfLines={1}>
        {row.status}
      </Text>
      <Text style={[{ color: t.text, flex: 2 }, s.cell]} numberOfLines={1}>
        {row.key}
      </Text>
      <Text style={[{ color: t.textSecondary, width: 90, textAlign: 'right' }, s.cell]} numberOfLines={1}>
        {row.a ? humanSize(row.a.size) : '—'}
      </Text>
      <Text style={[{ color: t.textSecondary, width: 90, textAlign: 'right' }, s.cell]} numberOfLines={1}>
        {row.b ? humanSize(row.b.size) : '—'}
      </Text>
      <Text style={[{ color: t.textTertiary, width: 150 }, s.cell]} numberOfLines={1}>
        {fmtDate(row.a?.mtime)}
      </Text>
      <Text style={[{ color: t.textTertiary, width: 150 }, s.cell]} numberOfLines={1}>
        {fmtDate(row.b?.mtime)}
      </Text>
      <Text style={[{ color: t.textSecondary, width: 60, textAlign: 'center' }, s.cell]} numberOfLines={1}>
        {newer}
      </Text>
      <Text style={[{ color: t.textTertiary, flex: 1 }, s.cell]} numberOfLines={1}>
        {row.note}
      </Text>
    </View>
  );
}

function statusColor(t: Palette, status: string): string {
  switch (status) {
    case 'added': return t.green;
    case 'removed': return t.red;
    case 'modified': return t.orange;
    default: return t.textTertiary;
  }
}

const s = StyleSheet.create({
  exportBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    marginLeft: space[2],
  },
  filters: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space[3],
    paddingVertical: 8,
    gap: space[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space[3],
    paddingVertical: 8,
    gap: space[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space[3],
    paddingVertical: 5,
    gap: space[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  cell: {
    fontSize: fs.sm,
  },
});
