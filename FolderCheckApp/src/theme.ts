/**
 * Design tokens. Colors follow Apple's system color language (approximate
 * NSColor values), softened slightly so dense tables don't glow. Every
 * consumer uses `useTheme()` which picks the right palette based on
 * `Appearance` and re-renders when the user switches OS-level dark mode.
 */

import { Appearance, Platform, useColorScheme } from 'react-native';

// ---- palette ----

const light = {
  bg:             '#ececec',
  bgContent:      '#f5f5f7',
  card:           '#ffffff',
  cardElevated:   '#ffffff',
  sidebar:        '#eaecef',
  hover:          'rgba(0,0,0,0.045)',
  active:         'rgba(0,0,0,0.08)',
  border:         'rgba(0,0,0,0.10)',
  borderStrong:   'rgba(0,0,0,0.16)',
  separator:      'rgba(0,0,0,0.08)',

  text:           '#1d1d1f',
  textSecondary:  'rgba(60,60,67,0.68)',
  textTertiary:   'rgba(60,60,67,0.45)',
  textQuaternary: 'rgba(60,60,67,0.28)',
  textInverse:    '#ffffff',

  blue:   '#3b7dd8',
  blueHi: '#2e6ac9',
  green:  '#2ea15b',
  red:    '#d64545',
  orange: '#dd7a1c',
  yellow: '#d69c1a',
  purple: '#7a5fd3',
  gray:   '#8a8a8e',

  accent:      '#3b7dd8',
  accentHi:    '#2e6ac9',
  accentSoft:  'rgba(59,125,216,0.15)',

  selection:         'rgba(59,125,216,0.28)',
  selectionInactive: 'rgba(0,0,0,0.08)',

  shadow: 'rgba(0,0,0,0.10)',
};

const dark: typeof light = {
  bg:             '#1e1e1f',
  bgContent:      '#232324',
  card:           '#2a2a2c',
  cardElevated:   '#303032',
  sidebar:        '#232326',
  hover:          'rgba(255,255,255,0.05)',
  active:         'rgba(255,255,255,0.09)',
  border:         'rgba(255,255,255,0.09)',
  borderStrong:   'rgba(255,255,255,0.16)',
  separator:      'rgba(255,255,255,0.08)',

  text:           '#f5f5f7',
  textSecondary:  'rgba(235,235,245,0.68)',
  textTertiary:   'rgba(235,235,245,0.45)',
  textQuaternary: 'rgba(235,235,245,0.28)',
  textInverse:    '#ffffff',

  blue:   '#5c92e5',
  blueHi: '#7aa8ee',
  green:  '#4dc07a',
  red:    '#ff6a60',
  orange: '#eb9a3d',
  yellow: '#e6b23a',
  purple: '#9c85e6',
  gray:   '#98989d',

  accent:     '#5c92e5',
  accentHi:   '#7aa8ee',
  accentSoft: 'rgba(92,146,229,0.22)',

  selection:         'rgba(92,146,229,0.42)',
  selectionInactive: 'rgba(255,255,255,0.09)',

  shadow: 'rgba(0,0,0,0.45)',
};

export type Palette = typeof light;

// ---- scales ----

export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40 };
export const radii = { xs: 4, sm: 6, md: 8, lg: 10, xl: 14, xxl: 18, pill: 999 };
export const fs = { xs: 11, sm: 12, md: 13, lg: 15, xl: 18, xxl: 22, xxxl: 28 };
export const fw = {
  regular: '400' as const,
  medium:  '500' as const,
  semi:    '600' as const,
  bold:    '700' as const,
};

// ---- fonts ----

export const fonts = Platform.select({
  macos: {
    ui:      'System',
    display: 'System',
    mono:    'Menlo',
  },
  ios: {
    ui:      'System',
    display: 'System',
    mono:    'Menlo',
  },
  windows: {
    ui:      'Segoe UI',
    display: 'Segoe UI',
    mono:    'Consolas',
  },
  default: {
    ui:      'System',
    display: 'System',
    mono:    'Menlo',
  },
})!;

// ---- hook ----

export function useTheme(): Palette {
  const scheme = useColorScheme();
  return scheme === 'dark' ? dark : light;
}

// Non-reactive read (for one-off callers).
export function currentTheme(): Palette {
  return Appearance.getColorScheme() === 'dark' ? dark : light;
}

// Sizes
export const sizes = {
  titlebarHeight: 44,
  toolbarHeight:  48,
  statusHeight:   26,
};
