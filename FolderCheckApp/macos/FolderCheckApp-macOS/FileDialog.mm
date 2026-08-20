// FileDialog — Objective-C++ implementation. Wraps NSOpenPanel so JS can
// open the standard macOS file/folder picker.
#import "FileDialog.h"

#import <AppKit/AppKit.h>

@implementation FileDialog

RCT_EXPORT_MODULE();

+ (BOOL)requiresMainQueueSetup { return YES; }

- (dispatch_queue_t)methodQueue { return dispatch_get_main_queue(); }

/// Open a picker for files (optionally many). Resolves to an array of paths
/// or an empty array if the user cancelled.
RCT_EXPORT_METHOD(openFiles:(BOOL)allowMultiple
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
{
  NSOpenPanel *panel = [NSOpenPanel openPanel];
  panel.canChooseFiles = YES;
  panel.canChooseDirectories = NO;
  panel.allowsMultipleSelection = allowMultiple;
  panel.resolvesAliases = YES;

  NSInteger res = [panel runModal];
  if (res != NSModalResponseOK) {
    resolve(@[]);
    return;
  }
  NSMutableArray *paths = [NSMutableArray arrayWithCapacity:panel.URLs.count];
  for (NSURL *url in panel.URLs) {
    if (url.path) [paths addObject:url.path];
  }
  resolve(paths);
}

/// Open a picker for a single folder. Resolves to a path or nil.
RCT_EXPORT_METHOD(openFolder:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
{
  NSOpenPanel *panel = [NSOpenPanel openPanel];
  panel.canChooseFiles = NO;
  panel.canChooseDirectories = YES;
  panel.allowsMultipleSelection = NO;
  panel.resolvesAliases = YES;

  NSInteger res = [panel runModal];
  if (res != NSModalResponseOK) {
    resolve([NSNull null]);
    return;
  }
  NSString *path = panel.URLs.firstObject.path;
  resolve(path ?: [NSNull null]);
}

/// Prompt for a save location. Returns the chosen path or nil.
RCT_EXPORT_METHOD(saveFile:(NSDictionary *)opts
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
{
  NSSavePanel *panel = [NSSavePanel savePanel];
  NSString *suggested = opts[@"suggestedName"];
  if ([suggested isKindOfClass:[NSString class]]) {
    panel.nameFieldStringValue = suggested;
  }
  NSString *title = opts[@"title"];
  if ([title isKindOfClass:[NSString class]]) {
    panel.title = title;
  }
  NSInteger res = [panel runModal];
  if (res != NSModalResponseOK) {
    resolve([NSNull null]);
    return;
  }
  resolve(panel.URL.path ?: [NSNull null]);
}

@end
