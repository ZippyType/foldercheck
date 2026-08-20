import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { FileDialog } from '../native';
import { useApp } from '../store';
import { fs, fw, radii, space, useTheme, Palette } from '../theme';

export function SidePane({ label }: { label: 'A' | 'B' }) {
  const t = useTheme();
  const { state, addPaths, removeAt, clearSide } = useApp();
  const list = label === 'A' ? state.aInputs : state.bInputs;

  const pickFiles = async () => {
    const paths = await FileDialog.openFiles(true);
    if (paths.length) addPaths(label, paths);
  };
  const pickFolder = async () => {
    const p = await FileDialog.openFolder();
    if (p) addPaths(label, [p]);
  };

  return (
    <View
      style={[s.card, { flex: 1, backgroundColor: t.card, borderColor: t.border }]}
    >
      <View style={[s.header, { backgroundColor: t.bgContent, borderBottomColor: t.separator }]}>
        <View style={[s.badge, { backgroundColor: t.hover }]}>
          <Text style={[s.badgeText, { color: t.textSecondary }]}>{label}</Text>
        </View>
        <Text style={{ color: t.textTertiary, fontSize: fs.sm, flex: 1 }}>
          {list.length === 0
            ? 'Nothing selected'
            : `${list.length} ${list.length === 1 ? 'item' : 'items'}`}
        </Text>
        <IconAction t={t} label="＋ File" onPress={pickFiles} />
        <IconAction t={t} label="＋ Folder" onPress={pickFolder} />
        {list.length > 0 && (
          <IconAction t={t} label="Clear" onPress={() => clearSide(label)} />
        )}
      </View>

      {list.length === 0 ? (
        <View style={s.empty}>
          <Text style={{ color: t.textTertiary, fontSize: fs.sm, textAlign: 'center' }}>
            Use ＋ File or ＋ Folder to add sources.
          </Text>
        </View>
      ) : (
        <ScrollView>
          {list.map((path, i) => (
            <PathRow
              key={`${path}-${i}`}
              t={t}
              path={path}
              alt={i % 2 === 1}
              onRemove={() => removeAt(label, i)}
            />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

function PathRow({
  t,
  path,
  alt,
  onRemove,
}: {
  t: Palette;
  path: string;
  alt: boolean;
  onRemove: () => void;
}) {
  const [hover, setHover] = useState(false);
  const name = path.split('/').pop() || path;
  return (
    <Pressable
      onHoverIn={() => setHover(true)}
      onHoverOut={() => setHover(false)}
      style={[
        s.row,
        {
          backgroundColor: hover
            ? t.hover
            : alt
            ? t.bgContent
            : 'transparent',
        },
      ]}
    >
      <Text style={{ color: t.textSecondary, fontSize: fs.xs, width: 16 }}>
        {path.endsWith('/') ? '📁' : '📄'}
      </Text>
      <View style={{ flex: 1 }}>
        <Text
          numberOfLines={1}
          style={{ color: t.text, fontSize: fs.sm, fontWeight: fw.medium }}
        >
          {name}
        </Text>
        <Text
          numberOfLines={1}
          style={{ color: t.textTertiary, fontSize: fs.xs }}
        >
          {path}
        </Text>
      </View>
      {hover && (
        <Pressable onPress={onRemove} style={s.removeBtn}>
          <Text style={{ color: t.textSecondary, fontSize: fs.sm }}>✕</Text>
        </Pressable>
      )}
    </Pressable>
  );
}

function IconAction({
  t,
  label,
  onPress,
}: {
  t: Palette;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed, hovered }: any) => [
        s.iconBtn,
        { backgroundColor: pressed ? t.active : hovered ? t.hover : 'transparent' },
      ]}
    >
      <Text style={{ color: t.textSecondary, fontSize: fs.sm }}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  card: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radii.lg,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    paddingHorizontal: space[3],
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.xs,
  },
  badgeText: {
    fontSize: fs.xs,
    fontWeight: fw.bold,
    letterSpacing: 0.8,
  },
  iconBtn: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.sm,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: space[6],
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    paddingHorizontal: space[3],
    paddingVertical: 6,
  },
  removeBtn: {
    width: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
