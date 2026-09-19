import { describe, it, expect, beforeEach } from "vitest";
import { tryAcquireSpeechLock, releaseSpeechLock } from "@/lib/speechSession";

describe("speechSession", () => {
  beforeEach(() => {
    // Reset state before each test
    releaseSpeechLock();
  });

  it("acquires lock successfully when idle", () => {
    expect(tryAcquireSpeechLock()).toBe(true);
  });

  it("fails to acquire lock when already playing", () => {
    expect(tryAcquireSpeechLock()).toBe(true);
    expect(tryAcquireSpeechLock()).toBe(false);
  });

  it("can acquire lock again after release", () => {
    expect(tryAcquireSpeechLock()).toBe(true);
    releaseSpeechLock();
    expect(tryAcquireSpeechLock()).toBe(true);
  });
});