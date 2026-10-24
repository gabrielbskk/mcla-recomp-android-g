package org.mcla.recomp;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Filename rules for exported runtime logs and their rotations. */
final class LogExportNaming {
    private static final Pattern ARTIFACT = Pattern.compile("^(.*)\\.(log|csv)(?:\\.([0-9]+))?$");
    private static final Pattern HASH_PREFIX = Pattern.compile("^[0-9a-fA-F]{16}$");

    private LogExportNaming() {}

    static boolean isLogArtifact(String name) {
        return name != null && ARTIFACT.matcher(name).matches();
    }

    static String stableExportName(String originalName, String sha256Prefix) {
        Matcher matcher = originalName == null ? null : ARTIFACT.matcher(originalName);
        if (matcher == null || !matcher.matches()) {
            throw new IllegalArgumentException("Unsupported log artifact name");
        }
        if (sha256Prefix == null || !HASH_PREFIX.matcher(sha256Prefix).matches()) {
            throw new IllegalArgumentException("A 16-character SHA-256 prefix is required");
        }
        String rotatedStem = matcher.group(1);
        if (matcher.group(3) != null) rotatedStem += "-" + matcher.group(3);
        return "log-" + rotatedStem + "-" + sha256Prefix.toLowerCase(Locale.ROOT)
                + "." + matcher.group(2);
    }
}
