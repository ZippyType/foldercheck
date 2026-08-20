// Scanner — Objective-C++ implementation.
//
// Exposes one method to JS:
//   compare(aPaths, bPaths, deep) → { a: SideStats, b: SideStats, rows: DiffRow[] }
//
// Scanning AND diffing both happen natively in this one call. This matters:
// the per-file "entries" index (one dictionary key per file) used to be
// returned to JS and re-passed into a separate diffSides() call, but Hermes
// caps a single JS object at 196,607 properties — a folder with more files
// than that would blow up with "Property storage exceeds 196607 properties"
// the moment the entries dictionary crossed the bridge. Keeping entries
// native-only and only returning the (array-based, not property-based)
// diff rows avoids that ceiling entirely.
//
// Emits `scanProgress` events during long scans so the UI can show live
// counts. Runs each JS call on a background queue so the UI thread stays
// responsive.

#import "Scanner.h"

#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>

@interface Scanner ()
@property (nonatomic, assign) BOOL hasListeners;
@end

@implementation Scanner {
  dispatch_queue_t _workQueue;
}

RCT_EXPORT_MODULE();

- (instancetype)init {
  if ((self = [super init])) {
    _workQueue = dispatch_queue_create("com.foldercheck.scanner",
                                        DISPATCH_QUEUE_SERIAL);
  }
  return self;
}

+ (BOOL)requiresMainQueueSetup { return NO; }

- (dispatch_queue_t)methodQueue { return _workQueue; }

- (NSArray<NSString *> *)supportedEvents { return @[@"scanProgress"]; }

- (void)startObserving { self.hasListeners = YES; }
- (void)stopObserving  { self.hasListeners = NO; }

- (void)emitProgress:(NSString *)side files:(NSInteger)files bytes:(int64_t)bytes {
  if (!self.hasListeners) return;
  [self sendEventWithName:@"scanProgress"
                     body:@{@"side": side ?: @"",
                            @"files": @(files),
                            @"bytes": @(bytes)}];
}

// ---- helpers ----

static NSString *ExtOfName(NSString *name) {
  NSString *ext = name.pathExtension.lowercaseString;
  return ext.length ? [@"." stringByAppendingString:ext] : @"(none)";
}

static NSString *SHA256OfFileAtPath(NSString *path) {
  NSFileHandle *fh = [NSFileHandle fileHandleForReadingAtPath:path];
  if (!fh) return @"";
  CC_SHA256_CTX ctx;
  CC_SHA256_Init(&ctx);
  const NSUInteger chunk = 1024 * 1024;
  while (true) {
    @autoreleasepool {
      NSData *data = [fh readDataOfLength:chunk];
      if (data.length == 0) break;
      CC_SHA256_Update(&ctx, data.bytes, (CC_LONG)data.length);
    }
  }
  [fh closeFile];
  unsigned char digest[CC_SHA256_DIGEST_LENGTH];
  CC_SHA256_Final(digest, &ctx);
  NSMutableString *out = [NSMutableString stringWithCapacity:CC_SHA256_DIGEST_LENGTH * 2];
  for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; i++) {
    [out appendFormat:@"%02x", digest[i]];
  }
  return out;
}

// Walk one path (file or directory), adding its stats into the caller's
// mutable aggregate.
- (void)accumulatePath:(NSString *)root
             keyPrefix:(NSString *)keyPrefix
                  side:(NSString *)side
              entries:(NSMutableDictionary *)entries
        onFileCount:(NSMutableDictionary *)counters
        emitProgress:(BOOL)emit {
  NSFileManager *fm = [NSFileManager defaultManager];
  BOOL isDir = NO;
  if (![fm fileExistsAtPath:root isDirectory:&isDir]) {
    NSMutableArray *missing = counters[@"missing"];
    [missing addObject:root];
    return;
  }

  NSString *rootBase = root.lastPathComponent;
  __auto_type addFile = ^(NSString *fullPath, NSString *key, NSString *label) {
    NSError *err = nil;
    NSDictionary *attrs = [fm attributesOfItemAtPath:fullPath error:&err];
    if (!attrs) {
      counters[@"errors"] = @([counters[@"errors"] integerValue] + 1);
      return;
    }
    unsigned long long sz = [attrs[NSFileSize] unsignedLongLongValue];
    NSDate *mtime = attrs[NSFileModificationDate];
    NSString *ext = ExtOfName(fullPath);

    counters[@"files"] = @([counters[@"files"] integerValue] + 1);
    counters[@"size"]  = @([counters[@"size"]  longLongValue] + (long long)sz);

    NSMutableDictionary *exts = counters[@"extensions"];
    exts[ext] = @([exts[ext] integerValue] + 1);

    NSNumber *largestBytes = counters[@"largestBytes"];
    if ((long long)sz > largestBytes.longLongValue) {
      counters[@"largestBytes"] = @((long long)sz);
      counters[@"largestName"]  = label;
    }

    entries[key] = @{
      @"absPath": fullPath,
      @"size":    @((long long)sz),
      @"mtime":   @([mtime timeIntervalSince1970]),
    };
  };

  if (!isDir) {
    counters[@"fileInputs"] = @([counters[@"fileInputs"] integerValue] + 1);
    NSString *key = root.lastPathComponent;
    addFile(root, key, key);
    if (emit) [self emitProgress:side
                           files:[counters[@"files"] integerValue]
                           bytes:[counters[@"size"] longLongValue]];
    return;
  }

  counters[@"folderInputs"] = @([counters[@"folderInputs"] integerValue] + 1);
  NSURL *rootURL = [NSURL fileURLWithPath:root isDirectory:YES];
  NSDirectoryEnumerator *e =
    [fm enumeratorAtURL:rootURL
       includingPropertiesForKeys:@[NSURLIsDirectoryKey,
                                    NSURLFileSizeKey,
                                    NSURLContentModificationDateKey]
                         options:0
                    errorHandler:^BOOL(NSURL *url, NSError *err) {
                      counters[@"errors"] =
                        @([counters[@"errors"] integerValue] + 1);
                      return YES;
                    }];

  NSInteger lastEmitFiles = 0;
  for (NSURL *url in e) {
    @autoreleasepool {
      NSNumber *dir = nil;
      [url getResourceValue:&dir forKey:NSURLIsDirectoryKey error:nil];
      if (dir.boolValue) {
        counters[@"subfolders"] =
          @([counters[@"subfolders"] integerValue] + 1);
        continue;
      }
      NSString *fullPath = url.path;
      NSString *rel = [fullPath stringByReplacingOccurrencesOfString:
                                 [root stringByAppendingString:@"/"]
                                                          withString:@""];
      NSString *key = keyPrefix.length
        ? [NSString stringWithFormat:@"%@/%@", keyPrefix, rel]
        : rel;
      NSString *label = [NSString stringWithFormat:@"%@/%@", rootBase, rel];
      addFile(fullPath, key, label);

      NSInteger n = [counters[@"files"] integerValue];
      if (emit && (n - lastEmitFiles) >= 500) {
        lastEmitFiles = n;
        [self emitProgress:side files:n
                     bytes:[counters[@"size"] longLongValue]];
      }
    }
  }
  if (emit) [self emitProgress:side
                         files:[counters[@"files"] integerValue]
                         bytes:[counters[@"size"] longLongValue]];
}

// ---- internal helper ----

/// Scan one side (paths[] can mix files and folders). Returns the JS-safe
/// stats dictionary (no per-file entries — that stays native-only) via
/// `statsOut`, and the native-only per-file index via `entriesOut`.
- (void)scanSide:(NSArray<NSString *> *)paths
             side:(NSString *)side
        statsOut:(NSDictionary **)statsOut
      entriesOut:(NSDictionary **)entriesOut
{
  NSMutableDictionary *entries  = [NSMutableDictionary dictionary];
  NSMutableDictionary *counters = [@{
    @"fileInputs":   @0,
    @"folderInputs": @0,
    @"files":        @0,
    @"size":         @0LL,
    @"subfolders":   @0,
    @"errors":       @0,
    @"largestBytes": @0LL,
    @"largestName":  @"",
    @"extensions":   [NSMutableDictionary dictionary],
    @"missing":      [NSMutableArray array],
  } mutableCopy];

  BOOL singleFolder = (paths.count == 1);
  if (singleFolder) {
    BOOL isDir = NO;
    [[NSFileManager defaultManager] fileExistsAtPath:paths.firstObject
                                         isDirectory:&isDir];
    singleFolder = isDir;
  }

  for (NSString *p in paths) {
    NSString *prefix = singleFolder ? @"" : p.lastPathComponent;
    [self accumulatePath:p keyPrefix:prefix side:side
                 entries:entries onFileCount:counters
             emitProgress:YES];
  }

  NSString *sha256 = @"";
  if (paths.count == 1) {
    BOOL isDir = NO;
    if ([[NSFileManager defaultManager] fileExistsAtPath:paths.firstObject
                                             isDirectory:&isDir] && !isDir) {
      sha256 = SHA256OfFileAtPath(paths.firstObject);
    }
  }

  *statsOut = @{
    @"fileInputs":   counters[@"fileInputs"],
    @"folderInputs": counters[@"folderInputs"],
    @"files":        counters[@"files"],
    @"size":         counters[@"size"],
    @"subfolders":   counters[@"subfolders"],
    @"errors":       counters[@"errors"],
    @"missing":      counters[@"missing"],
    @"extensions":   counters[@"extensions"],
    @"largestFile":  @{
      @"name": counters[@"largestName"],
      @"size": counters[@"largestBytes"],
    },
    @"sha256":       sha256,
  };
  *entriesOut = entries;
}

/// Diff two native-only entries dictionaries into a JS-safe array of rows.
/// An array has no per-object property-count ceiling the way a dictionary
/// does, so this is safe to return even for huge folders.
- (NSArray *)diffEntries:(NSDictionary *)ea b:(NSDictionary *)eb deep:(BOOL)deep {
  NSMutableSet *keys = [NSMutableSet setWithArray:ea.allKeys];
  [keys addObjectsFromArray:eb.allKeys];
  NSArray *sortedKeys = [keys.allObjects
    sortedArrayUsingSelector:@selector(caseInsensitiveCompare:)];

  NSMutableArray *rows = [NSMutableArray arrayWithCapacity:sortedKeys.count];
  for (NSString *k in sortedKeys) {
    NSDictionary *va = ea[k];
    NSDictionary *vb = eb[k];
    NSString *status;
    NSString *note = @"";
    if (va && !vb) { status = @"removed"; note = @"only in A"; }
    else if (vb && !va) { status = @"added"; note = @"only in B"; }
    else {
      long long sa = [va[@"size"] longLongValue];
      long long sb = [vb[@"size"] longLongValue];
      double ma = [va[@"mtime"] doubleValue];
      double mb = [vb[@"mtime"] doubleValue];
      BOOL sizeDiff = sa != sb;
      BOOL mtimeDiff = fabs(ma - mb) > 1.0;
      NSMutableArray *notes = [NSMutableArray array];
      if (sizeDiff) [notes addObject:
        [NSString stringWithFormat:@"size %lld → %lld", sa, sb]];
      if (mtimeDiff && !sizeDiff) [notes addObject:@"mtime changed"];

      if (deep && !sizeDiff) {
        NSString *ha = SHA256OfFileAtPath(va[@"absPath"]);
        NSString *hb = SHA256OfFileAtPath(vb[@"absPath"]);
        if (ha.length && hb.length) {
          if ([ha isEqualToString:hb]) {
            [notes removeAllObjects];
          } else {
            [notes addObject:@"content differs"];
          }
        }
      }
      if (notes.count == 0) { status = @"unchanged"; }
      else { status = @"modified"; note = [notes componentsJoinedByString:@"; "]; }
    }
    [rows addObject:@{
      @"status": status,
      @"key":    k,
      @"a":      va ?: [NSNull null],
      @"b":      vb ?: [NSNull null],
      @"note":   note,
    }];
  }
  return rows;
}

// ---- exported methods ----

/// Scan both sides and diff them, entirely natively. Only the aggregate
/// stats and the (array-based) diff rows cross the bridge — the per-file
/// entries index never does, so there's no risk of hitting Hermes' per-
/// object property ceiling on very large folders.
RCT_EXPORT_METHOD(compare:(NSArray<NSString *> *)aPaths
                    bPaths:(NSArray<NSString *> *)bPaths
                      deep:(BOOL)deep
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
{
  NSDictionary *statsA = nil, *entriesA = nil;
  NSDictionary *statsB = nil, *entriesB = nil;
  [self scanSide:aPaths side:@"A" statsOut:&statsA entriesOut:&entriesA];
  [self scanSide:bPaths side:@"B" statsOut:&statsB entriesOut:&entriesB];

  NSArray *rows = [self diffEntries:entriesA b:entriesB deep:deep];

  resolve(@{
    @"a":    statsA,
    @"b":    statsB,
    @"rows": rows,
  });
}

@end
