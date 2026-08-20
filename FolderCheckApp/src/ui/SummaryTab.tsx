import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { humanSize } from '../native';
import { useApp } from '../store';
import { fs, fw, radii, space, useTheme, Palette } from '../theme';

export function SummaryTab() {
  const t = useTheme();
  const { state } = useApp();
  const r = state.result!;
  const { a, b, rows } = r;

  const added = rows.filter(x => x.status === 'added').length;
  const removed = rows.filter(x => x.status === 'removed').length;
  const modified = rows.filter(x => x.status === 'modified').length;
  const unchanged = rows.filter(x => x.status === 'unchanged').length;

  return (
    <ScrollView>
      <View style={s.stats}>
        <StatCard t={t} label="Total files" value={fmt(a.files + b.files)}
          hint={`A ${fmt(a.files)}  ·  B ${fmt(b.files)}`} accent={t.accent} />
        <StatCard t={t} label="Total size" value={humanSize(a.size + b.size)}
          hint={`A ${humanSize(a.size)}  ·  B ${humanSize(b.size)}`} accent={t.accent} />
        <StatCard t={t} label="Added"    value={fmt(added)}    accent={t.green} />
        <StatCard t={t} label="Removed"  value={fmt(removed)}  accent={t.red} />
        <StatCard t={t} label="Modified" value={fmt(modified)} accent={t.orange} />
      </View>

      <SectionHeader t={t} label="Totals" />
      <NumRow t={t} label="Total size" a={a.size} b={b.size} format={humanSize} />
      <NumRow t={t} label="Total files" a={a.files} b={b.files} />
      <NumRow t={t} label="Subfolders" a={a.subfolders} b={b.subfolders} />
      <NumRow t={t} label="Files + subfolders" a={a.files + a.subfolders} b={b.files + b.subfolders} />
      <NumRow t={t} label="Read errors" a={a.errors} b={b.errors} />

      <SectionHeader t={t} label="Changes" />
      <TextRow t={t} label="Added (only in B)" a="—" b={fmt(added)}
        comparison={added ? `${added} added to B` : 'None'}
        color={added ? t.green : undefined} />
      <TextRow t={t} label="Removed (only in A)" a={fmt(removed)} b="—"
        comparison={removed ? `${removed} removed from A` : 'None'}
        color={removed ? t.red : undefined} />
      <TextRow t={t} label="Modified" a="—" b="—"
        comparison={modified ? `${modified} file(s) changed` : 'None'}
        color={modified ? t.orange : undefined} />
      <TextRow t={t} label="Unchanged" a="—" b="—"
        comparison={`${unchanged} file(s) identical`}
        color={t.textTertiary} />

      <SectionHeader t={t} label="Largest file" />
      <TextRow t={t} label="Name"
        a={a.largestFile.name || '—'} b={b.largestFile.name || '—'} />
      <NumRow t={t} label="Size" a={a.largestFile.size} b={b.largestFile.size} format={humanSize} />

      {(a.sha256 || b.sha256) && (
        <>
          <SectionHeader t={t} label="File hash (single-file sides)" />
          <TextRow t={t} label="SHA-256"
            a={a.sha256 || '—'} b={b.sha256 || '—'}
            comparison={
              a.sha256 && b.sha256
                ? a.sha256 === b.sha256 ? 'Identical' : 'Differs'
                : 'n/a'
            }
            color={a.sha256 && b.sha256 && a.sha256 === b.sha256 ? t.green : t.red}
          />
        </>
      )}
    </ScrollView>
  );
}

function StatCard({
  t,
  label,
  value,
  hint,
  accent,
}: {
  t: Palette;
  label: string;
  value: string;
  hint?: string;
  accent: string;
}) {
  return (
    <View style={[s.card, { backgroundColor: t.card, borderColor: t.border }]}>
      <View style={[s.cardStripe, { backgroundColor: accent }]} />
      <View style={s.cardInner}>
        <Text style={[s.cardLabel, { color: t.textSecondary }]} numberOfLines={1}>
          {label.toUpperCase()}
        </Text>
        <Text style={[s.cardValue, { color: accent }]} numberOfLines={1}>
          {value}
        </Text>
        {hint ? (
          <Text style={[s.cardHint, { color: t.textTertiary }]} numberOfLines={1}>
            {hint}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

function SectionHeader({ t, label }: { t: Palette; label: string }) {
  return (
    <View style={[s.section, { backgroundColor: t.bgContent, borderBottomColor: t.separator }]}>
      <Text style={[s.sectionText, { color: t.textSecondary }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function TextRow({
  t,
  label,
  a,
  b,
  comparison,
  color,
}: {
  t: Palette;
  label: string;
  a: string;
  b: string;
  comparison?: string;
  color?: string;
}) {
  return (
    <View style={[s.row, { borderBottomColor: t.separator }]}>
      <Text style={[s.cell, { color: t.text, flex: 1.4 }]} numberOfLines={1}>
        {label}
      </Text>
      <Text style={[s.cell, { color: t.textSecondary, flex: 1.2 }]} numberOfLines={1}>
        {a}
      </Text>
      <Text style={[s.cell, { color: t.textSecondary, flex: 1.2 }]} numberOfLines={1}>
        {b}
      </Text>
      <Text
        style={[s.cell, { color: color ?? t.textTertiary, flex: 1.4 }]}
        numberOfLines={1}
      >
        {comparison || (a === b ? 'Same' : 'Differs')}
      </Text>
    </View>
  );
}

function NumRow({
  t,
  label,
  a,
  b,
  format,
}: {
  t: Palette;
  label: string;
  a: number;
  b: number;
  format?: (n: number) => string;
}) {
  const f = format ?? fmt;
  let comparison = 'Same';
  let color: string | undefined = t.green;
  if (a !== b) {
    const diff = Math.abs(a - b);
    if (a > b) {
      comparison = `A larger by ${f(diff)}`;
      color = t.accent;
    } else {
      comparison = `B larger by ${f(diff)}`;
      color = t.orange;
    }
  }
  return (
    <TextRow t={t} label={label} a={f(a)} b={f(b)} comparison={comparison} color={color} />
  );
}

function fmt(n: number): string {
  return n.toLocaleString();
}

const s = StyleSheet.create({
  stats: {
    flexDirection: 'row',
    padding: space[3],
    gap: space[3],
  },
  card: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radii.md,
    overflow: 'hidden',
    minWidth: 120,
  },
  cardStripe: {
    height: 3,
  },
  cardInner: {
    padding: space[3],
    gap: 4,
  },
  cardLabel: {
    fontSize: fs.xs,
    fontWeight: fw.bold,
    letterSpacing: 0.8,
  },
  cardValue: {
    fontSize: fs.xxl,
    fontWeight: fw.bold,
  },
  cardHint: {
    fontSize: fs.xs,
  },
  section: {
    paddingHorizontal: space[4],
    paddingVertical: space[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  sectionText: {
    fontSize: fs.xs,
    fontWeight: fw.bold,
    letterSpacing: 0.8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space[4],
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: space[3],
  },
  cell: {
    fontSize: fs.sm,
  },
});
