// jsdom has no AnimationEvent. Without it React DOM listens for `webkitAnimationEnd`, so
// onAnimationEnd misses fireEvent.animationEnd. React DOM reads this once, when it loads.
const scope = window as { AnimationEvent?: unknown }
scope.AnimationEvent ??= class extends Event {}
