#import "AppDelegate.h"

#import <React/RCTBundleURLProvider.h>
#import <ReactAppDependencyProvider/RCTAppDependencyProvider.h>

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification
{
  self.moduleName = @"FolderCheckApp";
  self.initialProps = @{};
  self.dependencyProvider = [RCTAppDependencyProvider new];

  [super applicationDidFinishLaunching:notification];

  // Native macOS look: transparent titlebar, hidden title text, content
  // flows behind the traffic-light zone. Also give the window sensible
  // default dimensions and center it.
  dispatch_async(dispatch_get_main_queue(), ^{
    for (NSWindow *w in [NSApplication sharedApplication].windows) {
      w.titlebarAppearsTransparent = YES;
      w.titleVisibility = NSWindowTitleHidden;
      w.styleMask |= NSWindowStyleMaskFullSizeContentView;
      w.movableByWindowBackground = YES;
      NSRect frame = w.frame;
      frame.size = NSMakeSize(1120, 760);
      [w setFrame:frame display:YES animate:NO];
      [w center];
    }
  });
}

- (NSURL *)sourceURLForBridge:(RCTBridge *)bridge
{
  return [self bundleURL];
}

- (NSURL *)bundleURL
{
#if DEBUG
  return [[RCTBundleURLProvider sharedSettings] jsBundleURLForBundleRoot:@"index"];
#else
  return [[NSBundle mainBundle] URLForResource:@"main" withExtension:@"jsbundle"];
#endif
}

/// This method controls whether the `concurrentRoot`feature of React18 is turned on or off.
///
/// @see: https://reactjs.org/blog/2022/03/29/react-v18.html
/// @note: This requires to be rendering on Fabric (i.e. on the New Architecture).
/// @return: `true` if the `concurrentRoot` feature is enabled. Otherwise, it returns `false`.
- (BOOL)concurrentRootEnabled
{
#ifdef RN_FABRIC_ENABLED
  return true;
#else
  return false;
#endif
}

@end
