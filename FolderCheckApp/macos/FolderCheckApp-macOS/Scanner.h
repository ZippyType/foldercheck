// Scanner — walks file/folder inputs and returns aggregate stats + a
// per-file index keyed by relative path. Exposed to JS as `Scanner`.
#import <React/RCTBridgeModule.h>
#import <React/RCTEventEmitter.h>

@interface Scanner : RCTEventEmitter <RCTBridgeModule>
@end
