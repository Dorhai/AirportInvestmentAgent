let isPlaying = false;

export function tryAcquireSpeechLock(): boolean {
  if (isPlaying) {
    return false;
  }
  isPlaying = true;
  return true;
}

export function releaseSpeechLock(): void {
  isPlaying = false;
}
