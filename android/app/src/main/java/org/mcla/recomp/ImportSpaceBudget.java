package org.mcla.recomp;

/** Pure capacity check: filesystem free space already excludes allocated game and game.part bytes. */
final class ImportSpaceBudget {
    private ImportSpaceBudget() {}

    static boolean fits(long totalBytes, long usableBytes, long retainedGameAndStageBytes,
                        long additionalBytes) {
        if (totalBytes <= 0 || usableBytes < 0 || usableBytes > totalBytes
                || retainedGameAndStageBytes < 0 || additionalBytes < 0) {
            return false;
        }
        long occupiedBytes = totalBytes - usableBytes;
        long otherAllocatedBytes = Math.max(0, occupiedBytes - retainedGameAndStageBytes);
        if (retainedGameAndStageBytes > Long.MAX_VALUE - otherAllocatedBytes) return false;
        long retainedAndOther = otherAllocatedBytes + retainedGameAndStageBytes;
        return additionalBytes <= totalBytes - retainedAndOther;
    }
}
