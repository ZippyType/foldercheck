import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

import { useApp } from '../store';
import { fs, fw, radii, space, useTheme } from '../theme';

export function ScanOverlay() {
  const t = useTheme();
  const { state } = useApp();
  const fade = useRef(new Animated.Value(0)).current;
  const slide = useRef(new Animated.Value(6)).current;
  const barX = useRef(new Animated.Value(-1)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, { toValue: 1, duration: 180, useNativeDriver: true }),
      Animated.timing(slide, { toValue: 0, duration: 220, useNativeDriver: true }),
    ]).start();
    const loop = Animated.loop(
      Animated.timing(barX, {
        toValue: 1,
        duration: 1200,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [fade, slide, barX]);

  return (
    <Animated.View
      pointerEvents="auto"
      style={[
        StyleSheet.absoluteFillObject,
        { alignItems: 'center', justifyContent: 'center', opacity: fade },
      ]}
    >
      <View style={[StyleSheet.absoluteFillObject, { backgroundColor: t.bg, opacity: 0.55 }]} />
      <Animated.View
        style={[
          s.card,
          {
            backgroundColor: t.card,
            borderColor: t.border,
            shadowColor: t.shadow,
            transform: [{ translateY: slide }],
          },
        ]}
      >
        <Text style={[s.title, { color: t.text }]}>Scanning…</Text>
        <Text style={[s.sub, { color: t.textSecondary }]} numberOfLines={2}>
          {state.progressText || 'Preparing…'}
        </Text>
        <View style={[s.bar, { backgroundColor: t.hover }]}>
          <Animated.View
            style={[
              s.barFill,
              {
                backgroundColor: t.accent,
                transform: [
                  {
                    translateX: barX.interpolate({
                      inputRange: [-1, 1],
                      outputRange: [-140, 380],
                    }),
                  },
                ],
              },
            ]}
          />
        </View>
      </Animated.View>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  card: {
    minWidth: 380,
    maxWidth: 480,
    padding: space[5],
    borderRadius: radii.xl,
    borderWidth: StyleSheet.hairlineWidth,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 1,
    shadowRadius: 20,
    gap: 10,
  },
  title: {
    fontSize: fs.lg,
    fontWeight: fw.semi,
  },
  sub: {
    fontSize: fs.sm,
    minHeight: 34,
  },
  bar: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    marginTop: 4,
  },
  barFill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 140,
    borderRadius: 3,
  },
});
