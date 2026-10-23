package org.mcla.recomp;

public final class LogExportNamingTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        String hash = "0123456789abcdef";
        check(LogExportNaming.isLogArtifact("mcla.log"), "current runtime log is included");
        check(LogExportNaming.isLogArtifact("mcla.log.2"), "rotated runtime log is included");
        check(LogExportNaming.isLogArtifact("performance-v2.csv"), "performance CSV is included");
        check(LogExportNaming.isLogArtifact("performance-v2.csv.1"), "rotated performance CSV is included");
        check(!LogExportNaming.isLogArtifact("diagnostics-latest.txt"), "report is not treated as a log artifact");
        check("log-mcla-0123456789abcdef.log".equals(
                LogExportNaming.stableExportName("mcla.log", hash)), "runtime export name is stable");
        check("log-performance-v2-2-0123456789abcdef.csv".equals(
                LogExportNaming.stableExportName("performance-v2.csv.2", hash)),
                "rotated CSV keeps its sequence in the stable name");
        check("log-mcla-fedcba9876543210.log".equals(
                LogExportNaming.stableExportName("mcla.log", "fedcba9876543210")),
                "changed content gets a distinct name");
        System.out.println("log export naming: PASS");
    }
}
