import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useApp } from '../store';
import { fonts, fs, fw, radii, sizes, space, useTheme, Palette } from '../theme';
import { SidePane } from './SidePane';
import { SummaryTab } from './SummaryTab';
import { DiffTab } from './DiffTab';
import { ScanOverlay } from './ScanOverlay';

type Tab = 'summary' | 'diff';

export function Shell() {
  const t = useTheme();
  const { state } = useApp();
  const [tab, setTab] = useState<Tab>('summary');

  return (
    <View style={[s.root, { backgroundColor: t.bg }]}>
      {/* Draggable spacer under the transparent titlebar / traffic lights */}
      <View style={s.titlebarSpacer} />

      <Toolbar t={t} />

      <View style={s.content}>
        <View style={s.panes}>
          <SidePane label="A" />
          <View style={{ width: space[3] }} />
          <SidePane label="B" />
        </View>

        <View style={s.resultsWrap}>
          <View style={s.tabRow}>
            <SegBar t={t} tab={tab} onTab={setTab} />
          </View>
          <View
            style={[s.results, { backgroundColor: t.card, borderColor: t.border }]}
          >
            {state.result == null ? (
              <View style={s.empty}>
                <Text style={[s.emptyTitle, { color: t.textSecondary }]}>
                  No comparison yet
                </Text>
                <Text style={[s.emptySub, { color: t.textTertiary }]}>
                  Add sources to A and B, then press Compare.
                </Text>
              </View>
            ) : tab === 'summary' ? (
              <SummaryTab />
            ) : (
              <DiffTab />
            )}
          </View>
        </View>
      </View>

      <View style={[s.statusbar, { borderTopColor: t.separator }]}>
        <Text
          numberOfLines={1}
          style={{ color: t.textTertiary, fontSize: fs.xs, flex: 1 }}
        >
          {state.status}
        </Text>
      </View>

      {state.busy && <ScanOverlay />}
    </View>
  );
}

// ---- toolbar ----

function Toolbar({ t }: { t: Palette }) {
  const { state, compare, swap, clearAll, setDeep } = useApp();
  const disabled = state.busy;
  return (
    <View style={[s.toolbar, { borderBottomColor: t.separator, backgroundColor: t.bgContent }]}>
      <PrimaryButton
        t={t}
        label={state.busy ? 'Scanning…' : 'Compare'}
        onPress={compare}
        disabled={disabled}
      />
      <View style={{ width: space[2] }} />
      <SecondaryButton t={t} label="Swap A ⇄ B" onPress={swap} disabled={disabled} />
      <View style={{ flex: 1 }} />
      <Pressable
        onPress={() => setDeep(!state.deep)}
        style={({ hovered }: any) => [
          s.checkbox,
          { backgroundColor: hovered ? t.hover : 'transparent' },
        ]}
      >
        <View
          style={[
            s.checkboxBox,
            {
              borderColor: state.deep ? t.accent : t.borderStrong,
              backgroundColor: state.deep ? t.accent : 'transparent',
            },
          ]}
        >
          {state.deep && (
            <Text style={{ color: 'white', fontSize: 10, lineHeight: 12 }}>✓</Text>
          )}
        </View>
        <Text style={{ color: t.textSecondary, fontSize: fs.sm }}>Deep compare</Text>
      </Pressable>
      <View style={{ width: space[2] }} />
      <GhostButton t={t} label="Clear" onPress={clearAll} disabled={disabled} />
    </View>
  );
}

// ---- segmented tabs ----

function SegBar({ t, tab, onTab }: { t: Palette; tab: Tab; onTab: (v: Tab) => void }) {
  return (
    <View style={[s.segbar, { backgroundColor: t.hover }]}>
      <SegButton t={t} on={tab === 'summary'} label="Summary" onPress={() => onTab('summary')} />
      <SegButton t={t} on={tab === 'diff'} label="File differences" onPress={() => onTab('diff')} />
    </View>
  );
}

function SegButton({
  t,
  on,
  label,
  onPress,
}: {
  t: Palette;
  on: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        s.seg,
        on && {
          backgroundColor: t.card,
          shadowColor: t.shadow,
          shadowOffset: { width: 0, height: 1 },
          shadowOpacity: 1,
          shadowRadius: 2,
        },
      ]}
    >
      <Text
        style={{
          color: on ? t.text : t.textSecondary,
          fontSize: fs.sm,
          fontWeight: fw.medium,
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}

// ---- buttons ----

function PrimaryButton({
  t,
  label,
  onPress,
  disabled,
}: {
  t: Palette;
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={({ pressed }: any) => [
        s.btn,
        {
          backgroundColor: disabled
            ? t.accentSoft
            : pressed
            ? t.accentHi
            : t.accent,
          borderColor: t.accentHi,
          opacity: disabled ? 0.7 : 1,
        },
      ]}
    >
      <Text style={[s.btnText, { color: 'white', fontWeight: fw.semi }]}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({
  t,
  label,
  onPress,
  disabled,
}: {
  t: Palette;
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={({ pressed, hovered }: any) => [
        s.btn,
        {
          backgroundColor: pressed ? t.active : hovered ? t.hover : t.card,
          borderColor: t.border,
          opacity: disabled ? 0.5 : 1,
        },
      ]}
    >
      <Text style={[s.btnText, { color: t.text }]}>{label}</Text>
    </Pressable>
  );
}

function GhostButton({
  t,
  label,
  onPress,
  disabled,
}: {
  t: Palette;
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={({ pressed, hovered }: any) => [
        s.btn,
        s.btnGhost,
        {
          backgroundColor: pressed ? t.active : hovered ? t.hover : 'transparent',
          opacity: disabled ? 0.5 : 1,
        },
      ]}
    >
      <Text style={[s.btnText, { color: t.textSecondary }]}>{label}</Text>
    </Pressable>
  );
}

// ---- styles ----

const s = StyleSheet.create({
  root: {
    flex: 1,
    fontFamily: fonts.ui as any,
  } as any,

  // Reserves vertical room under the transparent native titlebar so the
  // Compare button doesn't sit under the traffic lights.
  titlebarSpacer: {
    height: sizes.titlebarHeight - 12,
  },

  toolbar: {
    height: sizes.toolbarHeight,
    paddingHorizontal: space[4],
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    alignItems: 'center',
  },

  btn: {
    minHeight: 28,
    paddingHorizontal: 14,
    paddingVertical: 5,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnGhost: {
    borderColor: 'transparent',
  },
  btnText: {
    fontSize: fs.sm,
    fontWeight: fw.medium,
  },

  checkbox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.sm,
  },
  checkboxBox: {
    width: 14,
    height: 14,
    borderRadius: 3,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },

  content: {
    flex: 1,
    padding: space[4],
    gap: space[3],
  },
  panes: {
    flexDirection: 'row',
    minHeight: 200,
    maxHeight: 260,
  },

  resultsWrap: {
    flex: 1,
    gap: space[2],
  },
  tabRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  segbar: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    padding: 2,
    borderRadius: radii.md,
    gap: 2,
  },
  seg: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: radii.sm,
  },
  results: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radii.lg,
    overflow: 'hidden',
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  emptyTitle: {
    fontSize: fs.lg,
    fontWeight: fw.semi,
  },
  emptySub: {
    fontSize: fs.sm,
  },

  statusbar: {
    height: sizes.statusHeight,
    paddingHorizontal: space[4],
    borderTopWidth: StyleSheet.hairlineWidth,
    justifyContent: 'center',
    flexDirection: 'row',
    alignItems: 'center',
  },
});
